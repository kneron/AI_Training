# Step 0. Environment

## Prerequisites

- Python 3.6+
- PyTorch 1.3+
- CUDA 9.2+ (If you built PyTorch from source, CUDA 9.0 is also compatible)
- (Optional, used to build from source) GCC 5+
- [mmcv-full](https://mmcv.readthedocs.io/en/latest/#installation) (Note: not `mmcv`!)

**Note:** You need to run `pip uninstall mmcv` first if you have `mmcv` installed.
If mmcv and mmcv-full are both installed, there will be `ModuleNotFoundError`.


### Install kneron-mmdetection

1. We recommend you installing mmcv-full with pip:

    ```shell
    pip install mmcv-full -f https://download.openmmlab.com/mmcv/dist/{cu_version}/{torch_version}/index.html
    ```

    Please replace `{cu_version}` and `{torch_version}` in the url to your desired one. For example, to install the `mmcv-full` with `CUDA 10.1` and `PyTorch 1.6.0`, use the following command:

    ```shell
    pip install mmcv-full -f https://download.openmmlab.com/mmcv/dist/cu101/torch1.6.0/index.html
    ```

    See [here](https://github.com/open-mmlab/mmcv#install-with-pip) for different versions of MMCV compatible to different PyTorch and CUDA versions.

2. Clone the Kneron-version mmdetection (kneron-mmdetection) repository.

    ```bash
    git clone https://github.com/kneron/kneron-mmdetection
    cd kneron-mmdetection
    ```

3. Install required python packages for building kneron-mmdetection and then install kneron-mmdetection.

    ```shell
    pip install -r requirements/build.txt
    pip install -v -e .  # or "python setup.py develop"
    pip install onnx onnxoptimizer onnx-simplifier
    ```

# Step 1: Train models on standard datasets 

MMDetection provides hundreds of detection models in [Model Zoo](https://mmdetection.readthedocs.io/en/latest/model_zoo.html)) and supports several standard datasets like Pascal VOC, COCO, CityScapes, LVIS, etc. This note demonstrates how to perform common object detection tasks with these existing models and standard datasets, including:

- Use existing trained models to inference on given images.
- Evaluate existing trained models on standard datasets.
- Train models on standard datasets.

## Train YOLOX on COCO detection dataset

mmdetection provides out-of-the-box tools for training detection models.
This section will show how to train models (under [configs](https://github.com/open-mmlab/mmdetection/tree/master/configs)) on COCO.

**Important**: You might need to modify the [config file](https://github.com/open-mmlab/mmdetection/blob/5e246d5e3bc3310b5c625fb57bc03d2338ca39bc/docs/en/tutorials/config.md) according your GPUs resource (such as `samples_per_gpu`, `workers_per_gpu` ...etc due to your GPUs RAM limitation).
The default learning rate in config files is for 8 GPUs and 2 img/gpu (batch size = 8\*2 = 16).

### Step 1-1: Prepare COCO detection dataset

[COCO](https://cocodataset.org/#download) is available on official websites or mirrors.
We suggest that you download and extract the dataset to somewhere outside the project directory and symlink (`ln`) the dataset root to `$MMDETECTION/data` (`ln -s realpath/to/dataset $MMDetection/data/dataset`), as shown below:

```plain
mmdetection
├── mmdet
├── tools
├── configs
├── data (this folder should be made beforehand)
│   ├── coco (symlink)
│   │   ├── annotations
│   │   ├── train2017
│   │   ├── val2017
│   │   ├── test2017
...
```

It's recommended to *symlink* the dataset folder to mmdetection folder. However, if you place your dataset folder at different place and do not want to symlink, you have to change the corresponding paths in config files (absolute path is recommended).

### Step 1-2: Train YOLOX on COCO

[YOLOX: Exceeding YOLO Series in 2021](https://arxiv.org/abs/2107.08430)

We only need the configuration file (which is provided in `configs/yolox`) to train YOLOX: 
```python
python tools/train.py configs/yolox/yolox_s_8x8_300e_coco_img_norm.py
```
* (Note 2) The whole training process might take several days, depending on your computational resource (number of GPUs, etc). If you just want to take a quick look at the deployment flow, we suggest that you download our trained model so you can skip the training process:
```bash
mkdir work_dirs
cd work_dirs
wget https://github.com/kneron/Model_Zoo/raw/main/mmdetection/yolox_s/latest.zip
unzip latest.zip
cd ..
```
* (Note 3) This is a "training from scratch" tutorial, which might need lots of time and gpu resource. If you want to train a model on your custom dataset, it is recommended that you read [finetune.md](https://github.com/open-mmlab/mmdetection/blob/5e246d5e3bc3310b5c625fb57bc03d2338ca39bc/docs/en/tutorials/finetune.md), [customize_dataset.md](https://github.com/open-mmlab/mmdetection/blob/5e246d5e3bc3310b5c625fb57bc03d2338ca39bc/docs/en/tutorials/customize_dataset.md), and [colab tutorial: Train A Detector on A Customized Dataset](https://github.com/open-mmlab/mmdetection/blob/master/demo/MMDet_Tutorial.ipynb).

# Step 2: Test trained pytorch model
`tools/test_kneron.py` is a script that generates inference results from test set with our pytorch model(or onnx model) and evaluates the results to see if our pytorch model(or onnx model) is well trained (if `--eval` argument is given). Note that it's always good to evluate our pytorch model before deploying it.

```python
python tools/test_kneron.py \
    configs/yolox/yolox_s_8x8_300e_coco_img_norm.py \
    work_dirs/latest.pth \
    --eval bbox \
    --out-kneron output.json
```
* `configs/yolox/yolox_s_8x8_300e_coco_img_norm.py` is your yolox training config
* `work_dirs/latest.pth` is your trained yolox model

The expected result of the command above will be something similar to the following text (the numbers may slightly differ):
```plain
...
 Average Precision  (AP) @[ IoU=0.50:0.95 | area=   all | maxDets=100 ] = 0.378
 Average Precision  (AP) @[ IoU=0.50      | area=   all | maxDets=1000 ] = 0.563
 Average Precision  (AP) @[ IoU=0.75      | area=   all | maxDets=1000 ] = 0.408
 Average Precision  (AP) @[ IoU=0.50:0.95 | area= small | maxDets=1000 ] = 0.207
 Average Precision  (AP) @[ IoU=0.50:0.95 | area=medium | maxDets=1000 ] = 0.416
 Average Precision  (AP) @[ IoU=0.50:0.95 | area= large | maxDets=1000 ] = 0.505
 Average Recall     (AR) @[ IoU=0.50:0.95 | area=   all | maxDets=100 ] = 0.529
 Average Recall     (AR) @[ IoU=0.50:0.95 | area=   all | maxDets=300 ] = 0.530
 Average Recall     (AR) @[ IoU=0.50:0.95 | area=   all | maxDets=1000 ] = 0.530
 Average Recall     (AR) @[ IoU=0.50:0.95 | area= small | maxDets=1000 ] = 0.318
 Average Recall     (AR) @[ IoU=0.50:0.95 | area=medium | maxDets=1000 ] = 0.581
 Average Recall     (AR) @[ IoU=0.50:0.95 | area= large | maxDets=1000 ] = 0.677

OrderedDict([('bbox_mAP', 0.378), ('bbox_mAP_50', 0.563), ('bbox_mAP_75', 0.408), ('bbox_mAP_s', 0.207), ('bbox_mAP_m', 0.416), ('bbox_mAP_l', 0.505), ('bbox_mAP_copypaste', '0.378 0.563 0.408 0.207 0.416 0.505')])
...
```

# Step 3: Export onnx
`tools/deployment/pytorch2onnx_kneron.py` is a script provided by Kneron to help user to convert our trained pth model to kneron-optimized onnx:
```python
python tools/deployment/pytorch2onnx_kneron.py \
    configs/yolox/yolox_s_8x8_300e_coco_img_norm.py \
    work_dirs/yolox_s_8x8_300e_coco_img_norm/latest.pth \
    --output-file work_dirs/latest.onnx \
    --skip-postprocess \
    --shape 640 640
```
* `configs/yolox/yolox_s_8x8_300e_coco_img_norm.py` is your yolox training config
* `work_dirs/latest.pth` is your trained yolox model

The output onnx should be the same name as `work_dirs/latest.pth` with `.onnx` postfix in the same folder.

# Step 4: Test exported onnx model:
We use the same script(`tools/test_kneron.py`) in step 2 to test our exported onnx. The only difference is that instead of pytorch model, we use onnx model (`work_dirs/latest.onnx`).

```python
python tools/test_kneron.py \
    configs/yolox/yolox_s_8x8_300e_coco_img_norm.py \
    work_dirs/latest.onnx \
    --eval bbox \
    --out-kneron output.json
```
* `configs/yolox/yolox_s_8x8_300e_coco_img_norm.py` is your yolox training config
* `work_dirs/latest.onnx` is your exported yolox onnx model

The expected result of the command above will be something similar to the following text (the numbers may slightly differ):
```plain
...
 Average Precision  (AP) @[ IoU=0.50:0.95 | area=   all | maxDets=100 ] = 0.379
 Average Precision  (AP) @[ IoU=0.50      | area=   all | maxDets=1000 ] = 0.564
 Average Precision  (AP) @[ IoU=0.75      | area=   all | maxDets=1000 ] = 0.410
 Average Precision  (AP) @[ IoU=0.50:0.95 | area= small | maxDets=1000 ] = 0.205
 Average Precision  (AP) @[ IoU=0.50:0.95 | area=medium | maxDets=1000 ] = 0.416
 Average Precision  (AP) @[ IoU=0.50:0.95 | area= large | maxDets=1000 ] = 0.503
 Average Recall     (AR) @[ IoU=0.50:0.95 | area=   all | maxDets=100 ] = 0.530
 Average Recall     (AR) @[ IoU=0.50:0.95 | area=   all | maxDets=300 ] = 0.531
 Average Recall     (AR) @[ IoU=0.50:0.95 | area=   all | maxDets=1000 ] = 0.531
 Average Recall     (AR) @[ IoU=0.50:0.95 | area= small | maxDets=1000 ] = 0.317
 Average Recall     (AR) @[ IoU=0.50:0.95 | area=medium | maxDets=1000 ] = 0.582
 Average Recall     (AR) @[ IoU=0.50:0.95 | area= large | maxDets=1000 ] = 0.678

OrderedDict([('bbox_mAP', 0.379), ('bbox_mAP_50', 0.564), ('bbox_mAP_75', 0.41), ('bbox_mAP_s', 0.205), ('bbox_mAP_m', 0.416), ('bbox_mAP_l', 0.503), ('bbox_mAP_copypaste', '0.379 0.564 0.410 0.205 0.416 0.503')])
...
```

# Step 5: Convert onnx to [NEF](http://doc.kneron.com/docs/#toolchain/manual/#5-nef-workflow) model for Kneron platform
 
### Step 5-1: Install Kneron toolchain docker:
* Check [document](http://doc.kneron.com/docs/#toolchain/manual/#1-installation)

### Step 5-2: Mout Kneron toolchain docker 
* Mount a folder (e.g. '/mnt/hgfs/Competition') to toolchain docker container as `/data1`. The converted onnx in Step 3 should be put here. All the toolchain operation should happen in this folder.
```shell
sudo docker run --rm -it -v /mnt/hgfs/Competition:/data1 kneron/toolchain:latest
```

### Step 5-3: Import KTC and other required packages in python shell
* Here we demonstrate how to go through all Kneron Toolchain (KTC) flow through Python API:
```python
import ktc
import numpy as np
import os
import onnx
from PIL import Image
```

### Step 5-4: Optimize the onnx model
```python
onnx_path = '/data1/latest.onnx'
m = onnx.load(onnx_path)
m = ktc.onnx_optimizer.onnx2onnx_flow(m)
onnx.save(m,'latest.opt.onnx')
```

### Step 5-5: Configure and load data necessary for ktc, and check if onnx is ok for toolchain
```python 
# npu (only) performance simulation
km = ktc.ModelConfig(20008, "0001", "720", onnx_model=m)
eval_result = km.evaluate()
print("\nNpu performance evaluation result:\n" + str(eval_result))
```

### Step 5-6: Quantize the onnx model
We [random sampled 50 images from voc dataset](https://www.kneron.com/forum/uploads/112/SMZ3HLBK3DXJ.7z) as quantization data, we have to
1. Download the data 
2. Uncompression the data as folder named `voc_data50"`
3. Put the `voc_data50` into docker mounted folder (the path in docker container should be `/data1/voc_data50`)

The following script will do some preprocess(should be the same as training code) on our quantization data, and put it in a list:
```python
import os
from os import walk

img_list = []
for (dirpath, dirnames, filenames) in walk("/data1/voc_data50"):
    for f in filenames:
        fullpath = os.path.join(dirpath, f)
        
        image = Image.open(fullpath)
        image = image.convert("RGB")
        image = Image.fromarray(np.array(image)[...,::-1])
        img_data = np.array(image.resize((640, 640), Image.BILINEAR)) / 256 - 0.5
        print(fullpath)
        img_list.append(img_data)
```

Then perform quantization. The BIE model will be generated at `/data1/output.bie`.

```python
# fixed-point analysis
bie_model_path = km.analysis({"input": img_list})
print("\nFixed-point analysis done. Saved bie model to '" + str(bie_model_path) + "'")
```

### Step 5-7: Compile
The final step is to compile the BIE model into an NEF model.
```python
# compile
nef_model_path = ktc.compile([km])
print("\nCompile done. Saved Nef file to '" + str(nef_model_path) + "'")
```

You can find the NEF file at `/data1/batch_compile/models_720.nef`. `models_720.nef` is the final compiled model.


# Step 6: Run [NEF](http://doc.kneron.com/docs/#toolchain/manual/#5-nef-workflow) model on [KL720 USB accelerator](https://www.kneo.ai/products/hardwares/HW2020122500000007/1)

[WARNING] Don't do this step in toolchain docker enviroment mentioned in Step 5

Recommend you read [Kneron PLUS official document](http://doc.kneron.com/docs/#plus_python/#_top) first.

### Step 6-1: Download and Install PLUS python library(.whl)
* Go to [Kneron education center](https://www.kneron.com/tw/support/education-center/)
* Scroll down to OpenMMLab Kneron Edition table
* Select Kneron Plus v1.13.0 (pre-built python library)
* Select your OS version(Ubuntu, Windows, MacOS, Raspberry pi)
* Download KneronPLUS-1.3.0-py3-none-any_{your_os}.whl
* unzip downloaded `KneronPLUS-1.3.0-py3-none-any.whl.zip`
* pip install KneronPLUS-1.3.0-py3-none-any.whl

### Step 6-2: Run NEF on [KL720 USB accelerator](https://www.kneo.ai/products/hardwares/HW2020122500000007/1) with kneron-mmdetection API (Ubuntu only)

RUN the following python script (change `/PATH/TO/YOUR/720_NEF_MODEL.nef` and `/PATH/TO/YOUR/IMAGE.bmp` and `configs/yolox/yolox_s_8x8_300e_coco_img_norm.py` to yours)

```python
from mmdet.apis import (inference_detector_kn, init_detector, show_result_pyplot)
from mmdet.models import build_detector
import kp

config_file = 'configs/yolox/yolox_s_8x8_300e_coco_img_norm.py'
model = init_detector(config_file, device='cpu')

device_group = kp.core.connect_devices(usb_port_ids=[0])
model_nef_descriptor = kp.core.load_model_from_file(device_group=device_group,
                                                            file_path='/PATH/TO/YOUR/720_NEF_MODEL.nef')
generic_raw_image_header = kp.GenericRawImageHeader(
    model_id=model_nef_descriptor.models[0].id,
    resize_mode=kp.ResizeMode.KP_RESIZE_ENABLE,
    padding_mode=kp.PaddingMode.KP_PADDING_CORNER,
    normalize_mode=kp.NormalizeMode.KP_NORMALIZE_KNERON,
    inference_number=0
)
kp_params = {
    'device_group' : device_group,
    'model_nef_descriptor': model_nef_descriptor,
    'generic_raw_image_header': generic_raw_image_header
}
res = inference_detector_kn(model, '/PATH/TO/YOUR/IMAGE.bmp', kneron_plus_params = kp_params)

show_result_pyplot(
    model,
     '/PATH/TO/YOUR/IMAGE.bmp',
    res,
    score_thr=0.3)

```

# Step 7 (For Kneron AI Competition 2022): Run [NEF](http://doc.kneron.com/docs/#toolchain/manual/#5-nef-workflow) model on [KL720 USB accelerator](https://www.kneo.ai/products/hardwares/HW2020122500000007/1)

[WARNING] Don't do this step in toolchain docker enviroment mentioned in Step 5

Recommend you read [Kneron PLUS official document](http://doc.kneron.com/docs/#plus_python/#_top) first.

### Step 7-1: Download and Install PLUS python library(.whl)
* Go to [Kneron education center](https://www.kneron.com/tw/support/education-center/)
* Scroll down to `OpenMMLab Kneron Edition table`
* Select `Kneron Plus v1.3.0 (pre-built python library, firmware)`
* Select `python library`
* Select Your OS version(Ubuntu, Windows, MacOS, Raspberry pi)
* Download `KneronPLUS-1.3.0-py3-none-any_{your_os}.whl`
* unzip downloaded `KneronPLUS-1.3.0-py3-none-any.whl.zip`
* pip install KneronPLUS-1.3.0-py3-none-any.whl

### Step 7-2: Download and upgrade KL720 USB accelerator firmware
* Go to [Kneron education center](https://www.kneron.com/tw/support/education-center/)
* Scroll down to `OpenMMLab Kneron Edition table`
* Select `Kneron Plus v1.3.0 (pre-built python library, firmware)`
* Select `firmware`
* Download `kl720_frimware.zip (fw_ncpu.bin、fw_scpu.bin)`
* unzip downloaded `kl720_frimware.zip`
* upgrade KL720 USB accelerator firmware(fw_ncpu.bin、fw_scpu.bin) by following [document](http://doc.kneron.com/docs/#plus_python/getting_start/), `Sec. 2. Update AI Device to KDP2 Firmware`, `Sec. 2.2 KL720`

### Step 7-3: Download YoloX example code
* Go to [Kneron education center](https://www.kneron.com/tw/support/education-center/)
* Scroll down to OpenMMLab Kneron Edition table
* Select kneron-mmdetection
* Select YoloX
* Download yolox_plus_demo.zip 
* unzip downloaded `yolox_plus_demo`

### Step 7-3: Test enviroment is ready (require [KL720 USB accelerator](https://www.kneo.ai/products/hardwares/HW2020122500000007/1))
In `yolox_plus_demo`, we provide a yolo example model and image for quick test. 
* Plug in [KL720 USB accelerator](https://www.kneo.ai/products/hardwares/HW2020122500000007/1) into your computer USB port
* Go to the yolox_plus_demo folder
```bash
cd /PATH/TO/yolox_plus_demo
```

* Install required library
```bash
pip insall -r requirements.txt
```

* Run example on [KL720 USB accelerator](https://www.kneo.ai/products/hardwares/HW2020122500000007/1)
```python
python KL720DemoGenericInferenceYoloX_BypassHwPreProc.py -img ./000000000536.jpg -nef ./example_yolox_720.nef
```

Then you can see the inference result is saved as output_000000000536.jpg in the same folder.
And the expected result of the command above will be something similar to the following text:
```plain
...
[Connect Device]
 - Success
[Set Device Timeout]
 - Success
[Upload Model]
 - Success
[Read Image]
 - Success
[Starting Inference Work]
 - Starting inference loop 1 times
 - .
[Retrieve Inference Node Output ]
 - Success
[Output Result Image]
 - Output bounding boxes on 'output_000000000536.jpg'
(291.7100891113281,135.5036407470703,444.81996459960936,331.6263565063477)
(86.29214324951171,75.08173713684083,178.1478744506836,331.3882736206055)
(168.07337951660156,81.79956779479981,274.36656799316404,331.9453491210938)
...
```

### Step 7-4: Run your NEF model and your image on [KL720 USB accelerator](https://www.kneo.ai/products/hardwares/HW2020122500000007/1)
Use the same script in previous step, but now we change the input NEF model path and image to yours
```bash
python KL720DemoGenericInferenceYoloX_BypassHwPreProc.py -img /PATH/TO/YOUR_IMAGE.bmp -nef /PATH/TO/YOUR/720_NEF_MODEL.nef
```


