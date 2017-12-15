#!/bin/csh -fb

# comment for production
setenv DEBUG true

##
## NETWORK
##

if ($#argv >= 3) then
set training_set = "$argv[1]"
set test_set = "$argv[2]"
set outputs = "$argv[3]"
else
  exit 1
endif

if ($#argv == 4) then
  set mean_image = "$argv[4]"
endif

# ALEXNET NETWORK

echo 'name: "AlexNet"' 
if ($?mean_image) then
  echo 'layer { name: "data" type: "Data" top: "data" top: "label" include { phase: TRAIN } transform_param { mirror: true crop_size: '$MODEL_IMAGE_WIDTH' mean_file: "'"$mean_image"'" } data_param { source: "'"$training_set"'" batch_size: 256 backend: LMDB } }' 
  echo 'layer { name: "data" type: "Data" top: "data" top: "label" include { phase: TEST } transform_param { mirror: false crop_size: '$MODEL_IMAGE_WIDTH' mean_file: "'"$mean_image"'" } data_param { source: "'"$test_set"'" batch_size: 50 backend: LMDB } }' 
else
  echo 'layer { name: "data" type: "Data" top: "data" top: "label" include { phase: TRAIN } transform_param { mirror: true crop_size: '$MODEL_IMAGE_WIDTH' } data_param { source: "'"$training_set"'" batch_size: 256 backend: LMDB } }' 
  echo 'layer { name: "data" type: "Data" top: "data" top: "label" include { phase: TEST } transform_param { mirror: false crop_size: '$MODEL_IMAGE_WIDTH' } data_param { source: "'"$test_set"'" batch_size: 50 backend: LMDB } }' 
endif
echo 'layer { name: "conv1" type: "Convolution" bottom: "data" top: "conv1" param { lr_mult: 1 decay_mult: 1 } param { lr_mult: 2 decay_mult: 0 } convolution_param { num_output: 96 kernel_size: 11 stride: 4 weight_filler { type: "gaussian" std: 0.01 } bias_filler { type: "constant" value: 0 } } }' 
echo 'layer { name: "relu1" type: "ReLU" bottom: "conv1" top: "conv1" }' 
echo 'layer { name: "norm1" type: "LRN" bottom: "conv1" top: "norm1" lrn_param { local_size: 5 alpha: 0.0001 beta: 0.75 } }' 
echo 'layer { name: "pool1" type: "Pooling" bottom: "norm1" top: "pool1" pooling_param { pool: MAX kernel_size: 3 stride: 2 } }' 
echo 'layer { name: "conv2" type: "Convolution" bottom: "pool1" top: "conv2" param { lr_mult: 1 decay_mult: 1 } param { lr_mult: 2 decay_mult: 0 } convolution_param { num_output: 256 pad: 2 kernel_size: 5 group: 2 weight_filler { type: "gaussian" std: 0.01 } bias_filler { type: "constant" value: 0.1 } } }' 
echo 'layer { name: "relu2" type: "ReLU" bottom: "conv2" top: "conv2" }' 
echo 'layer { name: "norm2" type: "LRN" bottom: "conv2" top: "norm2" lrn_param { local_size: 5 alpha: 0.0001 beta: 0.75 } }' 
echo 'layer { name: "pool2" type: "Pooling" bottom: "norm2" top: "pool2" pooling_param { pool: MAX kernel_size: 3 stride: 2 } }' 
echo 'layer { name: "conv3" type: "Convolution" bottom: "pool2" top: "conv3" param { lr_mult: 1 decay_mult: 1 } param { lr_mult: 2 decay_mult: 0 } convolution_param { num_output: 384 pad: 1 kernel_size: 3 weight_filler { type: "gaussian" std: 0.01 } bias_filler { type: "constant" value: 0 } } }' 
echo 'layer { name: "relu3" type: "ReLU" bottom: "conv3" top: "conv3" }' 
echo 'layer { name: "conv4" type: "Convolution" bottom: "conv3" top: "conv4" param { lr_mult: 1 decay_mult: 1 } param { lr_mult: 2 decay_mult: 0 } convolution_param { num_output: 384 pad: 1 kernel_size: 3 group: 2 weight_filler { type: "gaussian" std: 0.01 } bias_filler { type: "constant" value: 0.1 } } }' 
echo 'layer { name: "relu4" type: "ReLU" bottom: "conv4" top: "conv4" }' 
echo 'layer { name: "conv5" type: "Convolution" bottom: "conv4" top: "conv5" param { lr_mult: 1 decay_mult: 1 } param { lr_mult: 2 decay_mult: 0 } convolution_param { num_output: 256 pad: 1 kernel_size: 3 group: 2 weight_filler { type: "gaussian" std: 0.01 } bias_filler { type: "constant" value: 0.1 } } }' 
echo 'layer { name: "relu5" type: "ReLU" bottom: "conv5" top: "conv5" }' 
echo 'layer { name: "pool5" type: "Pooling" bottom: "conv5" top: "pool5" pooling_param { pool: MAX kernel_size: 3 stride: 2 } }' 
echo 'layer { name: "fc6" type: "InnerProduct" bottom: "pool5" top: "fc6" param { lr_mult: 1 decay_mult: 1 } param { lr_mult: 2 decay_mult: 0 } inner_product_param { num_output: 4096 weight_filler { type: "gaussian" std: 0.005 } bias_filler { type: "constant" value: 0.1 } } }' 
echo 'layer { name: "relu6" type: "ReLU" bottom: "fc6" top: "fc6" }' 
echo 'layer { name: "drop6" type: "Dropout" bottom: "fc6" top: "fc6" dropout_param { dropout_ratio: 0.5 } }' 
echo 'layer { name: "fc7" type: "InnerProduct" bottom: "fc6" top: "fc7" param { lr_mult: 1 decay_mult: 1 } param { lr_mult: 2 decay_mult: 0 } inner_product_param { num_output: 4096 weight_filler { type: "gaussian" std: 0.005 } bias_filler { type: "constant" value: 0.1 } } }' 
echo 'layer { name: "relu7" type: "ReLU" bottom: "fc7" top: "fc7" }' 
echo 'layer { name: "drop7" type: "Dropout" bottom: "fc7" top: "fc7" dropout_param { dropout_ratio: 0.5 } }' 
echo 'layer { name: "fc8" type: "InnerProduct" bottom: "fc7" top: "fc8" param { lr_mult: 1 decay_mult: 1 } param { lr_mult: 2 decay_mult: 0 } inner_product_param { num_output: '$outputs' weight_filler { type: "gaussian" std: 0.01 } bias_filler { type: "constant" value: 0 } } }' 
echo 'layer { name: "accuracy" type: "Accuracy" bottom: "fc8" bottom: "label" top: "accuracy" include { phase: TEST } }' 
echo 'layer { name: "loss" type: "SoftmaxWithLoss" bottom: "fc8" bottom: "label" top: "loss" }' 
