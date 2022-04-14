# All modification made by Kneron Corp.: Copyright (c) 2022 Kneron Corp.
# Copyright (c) OpenMMLab. All rights reserved.
import argparse
import os.path as osp
import warnings
from functools import partial

import numpy as np
import onnx
import torch
from mmcv import Config, DictAction

from mmdet.core.export import build_model_from_cfg, preprocess_example_input
from mmdet.core.export.model_wrappers import ONNXRuntimeDetector

from optimizer_scripts.tools import other
from optimizer_scripts.pytorch_exported_onnx_preprocess import (
    torch_exported_onnx_flow,
)


def pytorch2onnx(
    model,
    input_img,
    input_shape,
    normalize_cfg,
    opset_version=11,
    show=False,
    output_file="tmp.onnx",
    verify=False,
    test_img=None,
    do_simplify=False,
    dynamic_export=None,
    skip_postprocess=False,
    in_model_preprocess=False,
):

    input_config = {
        "input_shape": input_shape,
        "input_path": input_img,
        "normalize_cfg": normalize_cfg,
    }
    # prepare input
    one_img, one_meta = preprocess_example_input(input_config)
    img_list, img_meta_list = [one_img], [[one_meta]]

    if skip_postprocess:
        warnings.warn(
            "Not all models support export onnx without post "
            "process, especially two stage detectors!"
        )
        model.forward = model.forward_dummy
        torch.onnx.export(
            model,
            one_img,
            output_file,
            input_names=["input"],
            export_params=True,
            keep_initializers_as_inputs=False,
            do_constant_folding=False,
            verbose=show,
            opset_version=11,
        )

        print(
            "Successfully exported ONNX model without "
            f"post process: {output_file}"
        )

        import onnxsim
        from mmdet import digit_version

        min_required_version = "0.3.0"
        assert digit_version(onnxsim.__version__) >= digit_version(
            min_required_version
        ), f"Requires to install onnx-simplify>={min_required_version}"

        input_dic = {"input": img_list[0].detach().cpu().numpy()}
        model_opt, check_ok = onnxsim.simplify(
            output_file, input_data=input_dic,
            dynamic_input_shape=dynamic_export
        )
        if check_ok:
            onnx.save(model_opt, output_file)
            print(f"Successfully simplified ONNX model: {output_file}")
        else:
            warnings.warn("Failed to simplify ONNX model.")
        print(f"Successfully exported ONNX model: {output_file}")
        # print(normalize_cfg)
        m = onnx.load(output_file)
        print(len(m.graph.input))
        m = torch_exported_onnx_flow(m, disable_fuse_bn=False)

        if len(m.graph.input) > 1:
            raise ValueError(
                "'--pixel-bias-value' and '--pixel-scale-value' "
                "only support one input node model currently"
            )

        if in_model_preprocess:
            print(
                "adding BN for doing input data normalization".center(79, '-')
            )

            mean = normalize_cfg["mean"]
            std = normalize_cfg["std"]

            i_n = m.graph.input[0]
            if i_n.type.tensor_type.shape.dim[1].dim_value != len(
                mean
            ) or i_n.type.tensor_type.shape.dim[1].dim_value != len(std):
                raise ValueError(
                    "--pixel-bias-value ("
                    + str(mean)
                    + ") and --pixel-scale-value ("
                    + str(std)
                    + ") should be same as input dimension:"
                    + str(i_n.type.tensor_type.shape.dim[1].dim_value)
                )

            # add 128 for changing input range from 0~255 to -128~127 (int8)
            # due to quantization limitation
            norm_bn_bias = [
                -1 * cm / cs + 128. / cs for cm, cs in zip(mean, std)
            ]
            norm_bn_scale = [1 / cs for cs in std]

            other.add_bias_scale_bn_after(
                m.graph, i_n.name, norm_bn_bias, norm_bn_scale
            )
            m = other.polish_model(m)

        onnx_out = output_file
        onnx.helper.set_model_props(
            m,
            {
                "Kn. T.P. version": " MMDetection_KN v0.1.0",
                "in-model-preproc": str(in_model_preprocess),
            },
        )
        onnx.save(m, onnx_out)
        print("exported success: ", onnx_out)

        if verify:
            import onnxruntime as ort

            onnx_model = onnx.load(output_file)
            onnx.checker.check_model(onnx_model)
            with torch.no_grad():
                if in_model_preprocess:
                    bn = torch.nn.BatchNorm2d(3)
                    bn.weight[:] = torch.as_tensor(
                        norm_bn_scale, dtype=bn.weight.dtype
                    )
                    bn.bias[:] = torch.as_tensor(
                        norm_bn_bias, dtype=bn.bias.dtype
                    )
                    model = torch.nn.Sequential(bn, model).eval()

                pth_outs = model(one_img)

                def recursive_numpy(ctxs):
                    if isinstance(ctxs, torch.Tensor):
                        return ctxs.numpy()
                    ctxs = [recursive_numpy(ctx) for ctx in ctxs]
                    return ctxs

                pth_outs = recursive_numpy(pth_outs)

                # NOTE: flatten if nested structure
                if not isinstance(pth_outs[0], torch.Tensor):
                    pth_outs = [pth_out for _ in pth_outs for pth_out in _]

            input_all = [node.name for node in onnx_model.graph.input]
            input_initializer = [
                node.name for node in onnx_model.graph.initializer
            ]
            net_feed_input = list(set(input_all) - set(input_initializer))
            assert len(net_feed_input) == 1
            sess = ort.InferenceSession(
                output_file, providers=["CPUExecutionProvider"]
            )
            ort_outs = sess.run(
                None, {net_feed_input[0]: one_img.detach().numpy()}
            )
            err_msg = (
                "The numerical values are different between Pytorch"
                + " and ONNX, but it does not necessarily mean the"
                + " exported ONNX model is problematic."
            )
            for ort_out, pth_out in zip(ort_outs, pth_outs):
                np.testing.assert_allclose(
                    ort_out, pth_out, rtol=1e-02, atol=1e-04, err_msg=err_msg
                )
            print("The numerical values are the same between Pytorch and ONNX")

        return

    # replace original forward function
    origin_forward = model.forward
    model.forward = partial(
        model.forward, img_metas=img_meta_list,
        return_loss=False, rescale=False
    )

    output_names = ["dets", "labels"]
    if model.with_mask:
        output_names.append("masks")
    input_name = "input"
    dynamic_axes = None
    if dynamic_export:
        dynamic_axes = {
            input_name: {0: "batch", 2: "height", 3: "width"},
            "dets": {
                0: "batch",
                1: "num_dets",
            },
            "labels": {
                0: "batch",
                1: "num_dets",
            },
        }
        if model.with_mask:
            dynamic_axes["masks"] = {0: "batch", 1: "num_dets"}

    torch.onnx.export(
        model,
        img_list,
        output_file,
        input_names=[input_name],
        output_names=output_names,
        export_params=True,
        keep_initializers_as_inputs=True,
        do_constant_folding=True,
        verbose=show,
        opset_version=opset_version,
        dynamic_axes=dynamic_axes,
    )

    model.forward = origin_forward

    # get the custom op path
    ort_custom_op_path = ""
    try:
        from mmcv.ops import get_onnxruntime_op_path

        ort_custom_op_path = get_onnxruntime_op_path()
    except (ImportError, ModuleNotFoundError):
        warnings.warn(
            "If input model has custom op from mmcv, \
            you may have to build mmcv with ONNXRuntime from source."
        )

    if do_simplify:
        import onnxsim

        from mmdet import digit_version

        min_required_version = "0.3.0"
        assert digit_version(onnxsim.__version__) >= digit_version(
            min_required_version
        ), f"Requires to install onnx-simplify>={min_required_version}"

        input_dic = {"input": img_list[0].detach().cpu().numpy()}
        model_opt, check_ok = onnxsim.simplify(
            output_file,
            input_data=input_dic,
            custom_lib=ort_custom_op_path,
            dynamic_input_shape=dynamic_export,
        )
        if check_ok:
            onnx.save(model_opt, output_file)
            print(f"Successfully simplified ONNX model: {output_file}")
        else:
            warnings.warn("Failed to simplify ONNX model.")
    print(f"Successfully exported ONNX model: {output_file}")

    if verify:
        # check by onnx
        onnx_model = onnx.load(output_file)
        onnx.checker.check_model(onnx_model)

        # wrap onnx model
        onnx_model = ONNXRuntimeDetector(output_file, model.CLASSES, 0)
        if dynamic_export:
            # scale up to test dynamic shape
            h, w = [int((_ * 1.5) // 32 * 32) for _ in input_shape[2:]]
            h, w = min(1344, h), min(1344, w)
            input_config["input_shape"] = (1, 3, h, w)

        if test_img is None:
            input_config["input_path"] = input_img

        # prepare input once again
        one_img, one_meta = preprocess_example_input(input_config)
        img_list, img_meta_list = [one_img], [[one_meta]]

        # get pytorch output
        with torch.no_grad():
            pytorch_results = model(
                img_list, img_metas=img_meta_list,
                return_loss=False, rescale=True
            )[0]

        img_list = [_.cuda().contiguous() for _ in img_list]
        if dynamic_export:
            img_list = img_list + [_.flip(-1).contiguous() for _ in img_list]
            img_meta_list = img_meta_list * 2
        # get onnx output
        onnx_results = onnx_model(
                img_list, img_metas=img_meta_list, return_loss=False
        )[0]
        # visualize predictions
        score_thr = 0.3
        if show:
            out_file_ort, out_file_pt = None, None
        else:
            out_file_ort, out_file_pt = "show-ort.png", "show-pt.png"

        show_img = one_meta["show_img"]
        model.show_result(
            show_img,
            pytorch_results,
            score_thr=score_thr,
            show=True,
            win_name="PyTorch",
            out_file=out_file_pt,
        )
        onnx_model.show_result(
            show_img,
            onnx_results,
            score_thr=score_thr,
            show=True,
            win_name="ONNXRuntime",
            out_file=out_file_ort,
        )

        # compare a part of result
        if model.with_mask:
            compare_pairs = list(zip(onnx_results, pytorch_results))
        else:
            compare_pairs = [(onnx_results, pytorch_results)]
        err_msg = (
            "The numerical values are different between Pytorch"
            + " and ONNX, but it does not necessarily mean the"
            + " exported ONNX model is problematic."
        )
        # check the numerical value
        for onnx_res, pytorch_res in compare_pairs:
            for o_res, p_res in zip(onnx_res, pytorch_res):
                np.testing.assert_allclose(
                    o_res, p_res, rtol=1e-03, atol=1e-05, err_msg=err_msg
                )
        print("The numerical values are the same between Pytorch and ONNX")


def parse_normalize_cfg(test_pipeline):
    transforms = None
    for pipeline in test_pipeline:
        if "transforms" in pipeline:
            transforms = pipeline["transforms"]
            break
    assert transforms is not None, "Failed to find `transforms`"
    norm_config_li = [_ for _ in transforms if _["type"] == "Normalize"]
    assert len(norm_config_li) == 1, "`norm_config` should only have one"
    norm_config = norm_config_li[0]
    return norm_config


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert MMDetection models to ONNX"
    )
    parser.add_argument("config", help="test config file path")
    parser.add_argument("checkpoint", help="checkpoint file")
    parser.add_argument("--input-img", type=str, help="Images for input")
    parser.add_argument(
        "--show", action="store_true",
        help="Show onnx graph and detection outputs"
    )
    parser.add_argument("--output-file", type=str, default="tmp.onnx")
    parser.add_argument("--opset-version", type=int, default=11)
    parser.add_argument("--test-img", type=str, default=None,
                        help="Images for test")
    parser.add_argument(
        "--dataset",
        type=str,
        default="coco",
        help="Dataset name. This argument is deprecated and will be removed \
        in future releases.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="verify the onnx model output against pytorch output",
    )
    parser.add_argument(
        "--simplify", action="store_true",
        help="Whether to simplify onnx model."
    )
    parser.add_argument(
        "--shape", type=int, nargs="+",
        default=None, help="input image size"
    )
    parser.add_argument(
        "--cfg-options",
        nargs="+",
        action=DictAction,
        help="Override some settings in the used config, the key-value pair "
        "in xxx=yyy format will be merged into config file. If the value to "
        'be overwritten is a list, it should be like key="[a,b]" or key=a,b '
        'It also allows nested list/tuple values, e.g. key="[(a,b),(c,d)]" '
        "Note that the quotation marks are necessary and that no white space "
        "is allowed.",
    )
    parser.add_argument(
        "--dynamic-export",
        action="store_true",
        help="Whether to export onnx with dynamic axis.",
    )
    parser.add_argument(
        "--skip-postprocess",
        action="store_true",
        help="Whether to export model without post process. Experimental "
        "option. We do not guarantee the correctness of the exported "
        "model.",
    )
    parser.add_argument(
        "--in-model-preprocess",
        action="store_true",
        help="Add batchnormalization layer in front of model as a role of "
        "data preprocessing (noramlization) according to the "
        "normalization value in config. ",
    )
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_args()
    warnings.warn(
        "Arguments like `--skip-postprocess`, `--dataset` would be \
        parsed directly from config file and are deprecated and \
        will be removed in future releases."
    )

    assert args.opset_version == 11, "MMDet only support opset 11 now"

    try:
        from mmcv.onnx.symbolic import register_extra_symbolics
    except ModuleNotFoundError:
        raise NotImplementedError("please update mmcv to version>=v1.0.4")
    register_extra_symbolics(args.opset_version)

    cfg = Config.fromfile(args.config)
    if args.cfg_options is not None:
        cfg.merge_from_dict(args.cfg_options)

    if args.shape is None:
        img_scale = cfg.test_pipeline[1]["img_scale"]
        input_shape = (1, 3, img_scale[1], img_scale[0])
    elif len(args.shape) == 1:
        input_shape = (1, 3, args.shape[0], args.shape[0])
    elif len(args.shape) == 2:
        input_shape = (1, 3) + tuple(args.shape)
    else:
        raise ValueError("invalid input shape")

    # build the model and load checkpoint
    model = build_model_from_cfg(
        args.config, args.checkpoint, args.cfg_options
    )

    if not args.input_img:
        args.input_img = osp.join(osp.dirname(__file__), "../../demo/demo.jpg")

    normalize_cfg = parse_normalize_cfg(cfg.test_pipeline)

    # convert model to onnx file
    pytorch2onnx(
        model,
        args.input_img,
        input_shape,
        normalize_cfg,
        opset_version=args.opset_version,
        show=args.show,
        output_file=args.output_file,
        verify=args.verify,
        test_img=args.test_img,
        do_simplify=args.simplify,
        dynamic_export=args.dynamic_export,
        skip_postprocess=args.skip_postprocess,
        in_model_preprocess=args.in_model_preprocess,
    )
