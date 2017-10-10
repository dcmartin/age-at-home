#!/bin/bash

# use homebrew (brew.sh) on macOS
brew install -vd snappy leveldb gflags glog szip lmdb
brew tap homebrew/science
brew install hdf5 opencv
brew install protobuf boost

# get test data
wget -c http://dl.caffe.berkeleyvision.org/caffe_ilsvrc12.tar.gz

# Needs Python 2.7 and Keras 1.2.2
#
# To set this up:
# virtualenv -p /usr/bin/python2.7 env
# source env/bin/activate
# pip install tensorflow
# pip install keras==1.2.2
# pip install coremltools
#
# Use "deactivate" when you're done.

# macOS
# sudo easy_install pip
# sudo pip install --upgrade setuptools
# sudo pip install --upgrade python-swiftclient
# sudo pip install --upgrade python-keystoneclient
# export OS_USERNAME=
# export OS_PASSWORD=
# export OS_AUTH_URL=https://identity.open.softlayer.com/v3/
# export OS_PROJECT_DOMAIN_NAME=
# export OS_REGION_NAME=

pip install virtualenv

virtualenv -p /usr/bin/python2.7 env
source env/bin/activate
pip install tensorflow==1.2.1
pip install keras==1.2.2
pip install python-swiftclient
# version 1.0 which requires ST_AUTH, ST_USER, and ST_KEY environment (or keystoneclient)
pip install python-keystoneclient
pip install pandas
pip install coremltools

python -v convert.py

deactivate

