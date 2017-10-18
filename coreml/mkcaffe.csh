#!/bin/csh -fb

if ($?GIT == 0) setenv GIT .
echo "[ENV] using ($GIT) for GIT" >& /dev/stderr

## HOMEBREW (http://brew.sh)
command -v brew >& /dev/null
if ($status != 0) then
  echo "[WARN] HomeBrew not installed; trying " `bash /usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"` >& /dev/stderr
  rehash
endif

## JQ
command -v jq >& /dev/null
if ($status != 0) then
  echo "[WARN] jq not found; trying `brew install jq`" >& /dev/stderr
  rehash
endif

## PYTHON3
command -v python3 >& /dev/null
if ($status != 0) then
  echo "[WARN] python3 not found; trying `brew install python3`" >& /dev/stderr
  rehash
endif

## CMAKE
command -v cmake >& /dev/null
if ($status != 0) then
  echo "[WARN] cmake not found; trying `brew install cmake`" >& /dev/stderr
  rehash
endif
set cmake = ( `command -v cmake` )

## CAFFE

# PRE-REQUISITES

# tap science
echo "[INFO] tapping homebrew/science for opencv, hdf5" >& /dev/stderr
brew tap homebrew/science
foreach i ( snappy leveldb gflags glog szip lmdb opencv hdf5 protobuf boost )
  set json = `brew info --json=v1 "$i" | jq '.[].installed'`
  if ("$json" == "[]") then
    echo "[WARN] $i not found; trying `brew install $i`" >& /dev/stderr
  endif
end
rehash
 
# build from github.com
if (! -e "$GIT/caffe") then
  echo "[WARN] BLVC Caffe not found; cloning into ($GIT/caffe)" >& /dev/stderr
  # get caffe
  pushd "$GIT"
  git clone https://github.com/BVLC/caffe.git
  popd
endif

if (! -e "$GIT/caffe/build/tools/convert_imageset") then
  echo "[WARN] BLVC Caffe not found; installing" >& /dev/stderr
  if ($#cmake) then
    # building using cmake
    mkdir $GIT/caffe/build
    pushd caffe/build
    cmake ..
    # make it
    make all
    make install
    make runtest
    popd
  else
    echo "[ERROR] no cmake" >& /dev/stderr
    exit 1
  endif
else
  echo "[INFO] BLVC Caffe setup complete; $GIT/caffe/build/tools/convert_imageset available" >& /dev/stderr
  echo "$GIT/caffe/build/tools/convert_imageset"
endif

