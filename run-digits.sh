#!/bin/bash
docker run --restart always \
--runtime=nvidia --name digits -d -p 5000:5000 -p 6006:6006 -v digits-jobs:/opt/digits/jobs nvidia/digits
