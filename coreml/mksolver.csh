#!/bin/csh -fb

# comment for production
setenv DEBUG true

##
## NETWORK
##

if ($#argv >= 1) then
  set network = "$argv[1]"
else
  exit 1
endif

if ($#argv == 2) then
  set snapshot = "$argv[2]"
endif

# ALEXNET SOLVER

echo 'net: "'"$network"'"' 
echo 'test_iter: 1000' 
echo 'test_interval: 1000' 
echo 'base_lr: 0.01' 
echo 'lr_policy: "step"' 
echo 'gamma: 0.1' 
echo 'stepsize: 100000' 
echo 'display: 20' 
echo 'max_iter: 450000' 
echo 'momentum: 0.9' 
echo 'weight_decay: 0.0005' 
echo 'snapshot: 10000' 
echo 'snapshot_prefix: "'"$snapshot"'"' 
echo 'solver_mode: GPU' 
