#!/bin/csh -fb

# uncomment for production
setenv DEBUG true
# setenv DELETE true
setenv VERBOSE "--verbose"

## HOMEBREW (http://brew.sh)
command -v brew >& /dev/null
if ($status != 0) then
  echo "$0:t $$ -- [WARN] HomeBrew not installed; trying " `bash /usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"` >& /dev/stderr
  rehash
endif

## JQ
command -v jq >& /dev/null
if ($status != 0) then
  echo "$0:t $$ -- [WARN] jq not found; trying `brew install jq`" >& /dev/stderr
  rehash
endif

## PYTHON3
command -v python3 >& /dev/null
if ($status != 0) then
  echo "$0:t $$ -- [WARN] python3 not found; trying `brew install python3`" >& /dev/stderr
  rehash
endif

## CURL
command -v curl >& /dev/null
if ($status != 0) then
  echo "$0:t $$ -- [WARN] curl not found; trying `brew install curl`" >& /dev/stderr
  rehash
endif

## CURL SSL
set config = ( `curl-config --configure` )
set sslver = ( `echo "$config" | sed 's/.*--with-ssl=\([^ ]*\).*/\1/'` )
if ("$sslver" == "$config") then
  echo "$0:t $$ - [ERROR] curl not configured with SSL support" >& /dev/stderr
  exit 1
else
  set sslver = "$sslver:t"
endif
if (! -e "/usr/local/opt/$sslver") then
  echo "$0:t $$ - [WARN] SSL /usr/local/opt/$sslver not found; trying `brew install $sslver`" >& /dev/stderr
endif

## CAFFE
if ($?CAFFE == 0) setenv CAFFE "$0:h/caffe"
if ($?DEBUG) echo '[ENV] CAFFE (' "$CAFFE" ')' >& /dev/stderr

if (! -e "$CAFFE") then
  echo "$0:t $$ -- [ERROR] please install BLVC Caffe in ($CAFFE); trying `$0:h/mkcaffe.csh`"" >& /dev/stderr
  exit 1
endif

if (! -e "$0:h/mklmdb.csh") then
  echo "$0:t $$ -- [ERROR] mklmdb.csh not found ($0:h/mklmdb.csh)" >& /dev/stderr
  exit
endif

# path to source directory
if ($?AAH_HOME == 0) setenv AAH_HOME /var/lib/age-at-home/label
if ($?DEBUG) echo '[ENV] AAH_HOME (' "$AAH_HOME" ')' >& /dev/stderr
if (! -e "$AAH_HOME" || ! -d "$AAH_HOME") then
  echo "$0:t $$ -- [ERROR] directory $AAH_HOME is not available" >& /dev/stderr
  exit 1
endif

if ($?DEBUG) echo "$0:t $$ -- [debug] $0 $argv ($#argv)" >& /dev/stderr

# get source
if ($#argv > 0) then
  set device = "$argv[1]"
endif

# get percentages
if ($#argv > 1) then
  @ i = 2
  set total = 0
  set percentages = ()
  while ($i <= $#argv)
    @ t = $argv[$i]
    @ total += $t
    set percentages = ( $percentages $t )
    @ i++
  end
else
  set total = 100
endif

if ($?total) then
  if ($total != 100) then
    echo "$0:t $$ -- [ERROR] set breakdown ($percentages) across $#percentages does not total 100%" >& /dev/stderr
    exit
  endif
endif
if ($?percentages == 0) then
  set percentages = ( 75 25 )
endif

if ($?DEBUG) echo "$0:t $$ -- [ARGS] --percentages ($percentages)" >& /dev/stderr

if ($?device == 0) set device = "rough-fog"
if ($?DEBUG) echo "$0:t $$ -- [ARGS] --device ($device)" >& /dev/stderr

# get ID for the output
set lid = ( `$0:h/mklmdb.csh $device $percentages | jq '.'` ) >& /dev/null

if ($?DEBUG) echo "$0:t $$ -- [debug] successfully processed input: $lid" >& /dev/stderr

set maps = ( `echo "$lid" | jq -r '.maps[].file' ` )
if ($?DEBUG) echo "$0:t $$ -- [debug] maps = ( $maps )"

set data = ( `echo "$lid" | jq -r '.data[].file' ` )
if ($?DEBUG) echo "$0:t $$ -- [debug] data = ( $data )"

set mids = ( `echo "$lid" | jq -r '.maps[].id' ` )
set dids = ( `echo "$lid" | jq -r '.data[].id' ` )

set entries = ()
foreach d ( $data )
 if (-e "$d" && -d "$d") then
    set entries = ( $entries `mdb_stat "$d" | egrep "Entries: " | awk -F: '{ print $2 }'` )
    @ total_entries += $entries[$#entries]
  else
    echo "$0:t $$ -- [ERROR] FAILURE - $d does not exist or is not a directory" >& /dev/stderr
    exit 1
  endif
end

foreach m ( $maps )
  if (-e "$m") then
    set c = `awk '{ print $2 }' $m | sort | uniq | wc -l`
    if ($?classes) then
      if ($c != $classes) then
        echo "$0:t $$ -- [ERROR] FAILURE - $m class counts not equal ($c,$classes)" >& /dev/stderr
        exit 1
      endif
    endif
    set classes = $c
  else 
    echo "$0:t $$ -- [ERROR] FAILURE - $m does not exist" >& /dev/stderr
    exit 1
  endif
end

if ($#entries) then
  @ i = 1
  while ($?DEBUG && $i <= $#entries)
    echo "$0:t $$ -- [debug] file: $d; set $i; entries $entries[$i]; " `echo "$entries[$i] / $total_entries * 100.0" | bc -l | awk '{ printf("%.2f\n",$1) }'` "%" >& /dev/stderr
    @ i++
  end
else
  echo "$0:t $$ -- [ERROR] no entries ???" >& /dev/stderr
  exit 1
endif

##
## TEST IF PRE-REQUISITES ARE INSTALLED
##

# check OpenStack Swift client
set version = ( `swift --version |& awk '{ print $1 }'` )
if ( "$version" =~ "python*" ) then
  if ($?DEBUG) echo "$0:t $$ -- [debug] Swift installed ($version)"
else
  echo "INSTALLING Swift client using pip; system may prompt for password"
  pip3 install python-swiftclient >& /dev/null
  pip3 install python-keystoneclient >& /dev/null
  echo "DONE installing Swift client"
endif

##
## FIND CREDENTIALS
##

if ($?CREDENTIALS == 0) set CREDENTIALS = ~/.watson.objectstore.json

if (-e "$CREDENTIALS") then
  set auth_url = ( `jq -r '.auth_url' "$CREDENTIALS"` )
  set domainId = ( `jq -r '.domainId' "$CREDENTIALS"` )
  set domainName = ( `jq -r '.domainName' "$CREDENTIALS"` )
  set password = ( `jq -r '.password' "$CREDENTIALS"` )
  set project = ( `jq -r '.project' "$CREDENTIALS"` )
  set projectId = ( `jq -r '.projectId' "$CREDENTIALS"` )
  set region = ( `jq -r '.region' "$CREDENTIALS"` )
  set role = ( `jq -r '.role' "$CREDENTIALS"` )
  set userId = ( `jq -r '.userId' "$CREDENTIALS"` )
  set username = ( `jq -r '.username' "$CREDENTIALS"` )
else
  echo "$0:t $$ -- [ERROR] no credentials found: $CREDENTIALS"
  exit 1
endif

# BASE OPENSTACK VERSION; NOT IN CREDENTIALS
setenv OS_IDENTITY_API_VERSION 3
setenv OS_AUTH_VERSION 3

###
### interrogate SWIFT CONNECT WITH 'stat' COMMAND & convert to JSON
###

set stat = "/tmp/$0:t.$$.stat"
swift $VERBOSE \
  --os-user-id="$userId" \
  --os-password="$password" \
  --os-project-id="$projectId" \
  --os-auth-url="$auth_url/v3" \
  --os-region-name="$region" \
  stat >! "$stat"

if (-e "$stat") then
  if ($?DEBUG) echo "$0:t $$ -- [debug] successful ($stat)"
  set attrs = ( `awk -F': ' '{ print $1 }' "$stat" | sed 's/ //g' | sed 's/"//g'` )
  set vals = ( `awk -F': ' '{ print $2 }' "$stat" | sed 's/ //g' | sed 's/"//g'` )
  @ a = 1
  set j = '{ '
  while ($a <= $#attrs)
    if ($a > 1) set j = "$j"', '
    set j = "$j"'"'$attrs[$a]'": "'$vals[$a]'"'
    @ a++
  end
  set json = "$j"' }'
  rm -f "$stat"
else
  echo "$0:t $$ -- [ERROR] stat failed: --os-user-id=$userId --os-password=$password --os-project-id=$projectId --os-auth-url=$auth_url/v3 --os-region-name=$region" >& /dev/stderr
endif

if ($?json == 0) then
  echo "$0:t $$ -- [ERROR] cannot access SWIFT object storage"
  exit 1
endif

if ($?DEBUG) echo "$0:t $$ -- [debug] processed into JSON: " `echo "$json" | jq -c '.'`

# get parameters
set thisdir = ( `echo "$lid" | jq -r '.thisdir'` )
set device = ( `echo "$lid" | jq -r '.device'` )
set date = ( `echo "$lid" | jq -r '.date'` )
set percents = ( `echo "$lid" | jq -r '.maps[].percent'`) ; set percents = ( `echo "$percents" | sed 's/ /:/g'` )
set container = "$device.$date.$percents"

# check if source exists
if (! -e "$thisdir" || ! -d "$thisdir") then
  echo "$0:t $$ -- [ERROR] cannot locate $thisdir"
  exit 1
endif

##
## TEST IF STORAGE COMPLETE
##

set storage = ( `echo "$lid" | jq -r '.storage'` )

if ("$storage" != "null") then
  goto dlaas
endif

# extract authorization token and storage URL from JSON processed from curl

set auth = `echo "$json" | jq -r '.AuthToken'`
set sturl = `echo "$json" | jq -r '.StorageURL'`

# get existing containers
set containers = ( `swift $VERBOSE --os-auth-token "$auth" --os-storage-url "$sturl" list | sed 's/ /%20/g'` )

# check iff container exists; delete it when specified
unset existing
if ($?containers) then
  if ($#containers) then
    echo "$0:t $$ -- [debug] EXISTING CONTAINERS: $containers" >& /dev/stderr
    foreach c ( $containers )
      if ($?DELETE && "$c" == "$container") then
        echo "$0:t $$ -- [debug] deleting existing container $c" >& /dev/stderr
        swift $VERBOSE --os-auth-token "$auth" --os-storage-url "$sturl" delete `echo "$c" | sed 's/%20/ /g'` >& /dev/stderr
        continue
      else if ("$c" == "$container") then
        set existing = "$c"
        set n = ( `echo "$c" | sed 's/%20/ /g'` )
        set contents = ( `swift $VERBOSE --os-auth-token "$auth" --os-storage-url "$sturl" list "$n"` )
        if ($?contents == 0) set contents = ()
      else
        if ($?DEBUG) echo "$0:t $$ -- [debug] $c" >& /dev/stderr
      endif
    end
  else
    echo "$0:t $$ -- [debug] no existing containers" >& /dev/stderr
  endif
else
  echo "$0:t $$ -- [debug] no containers found" >& /dev/stderr
  exit 1
endif

# make new container
if ($?existing) then
  echo "$0:t $$ -- [WARN] existing container: $container; contents: [$contents]" >& /dev/stderr
else
  echo "$0:t $$ -- [INFO] making container: $container" >& /dev/stderr
  swift $VERBOSE --os-auth-token "$auth" --os-storage-url "$sturl" post `echo "$container" | sed 's/%20/ /g'` >& /dev/stderr
endif

# store all files
set files = ( `echo "$lid" | jq -r '.maps[].file,.data[].file'` )

# jump to thisdir (source)
pushd "$thisdir"

foreach file ( $files )
  set found = false
  if (-e "$file") then
    if ($?existing) then
      if ($#contents) then
        foreach c ( $contents )
          if ("$c:h" == "$file") then
            set found = true
          endif
        end
      endif
    endif
    if ($found != true) then
      if ($?DEBUG) echo "$0:t $$ -- [debug] copying $file " `du -k "$file" | awk '{ print $1 }'` "Kbytes" >& /dev/stderr
      swift $VERBOSE --os-auth-token "$auth" --os-storage-url "$sturl" upload `echo "$container" | sed 's/%20/ /g'` "$file"
    else
      if ($?DEBUG) echo "$0:t $$ -- [debug] $file exists" >& /dev/stderr
    endif
  else
    echo "$0:t $$ -- [ERROR] NO FILE: $file" >& /dev/stderr
  endif
end

# back from thisdir
popd

set files = `echo "$files" | sed 's/\([^ ]*\)/"\1",/g' | sed 's/\(.*\),$/\1/'`
set storage = '{"type":"bluemix_objectstore","container":"'"$container"'","auth_url":"'"$auth_url"'","user_name":"'"$username"'","password":"'"$password"'","domain_name":"'"$domainName"'","region":"'"$region"'","project_id":"'"$projectId"'","files":['"$files"']}'

echo "$lid" | jq '.storage='"$storage" >! "$container.json"

###
### BEGIN DLAAAS
###

dlaas:

set input = `jq '.' "$container.json"` 

echo "$input"

exit

# get models from DLAAS
set models = ( `curl -u "$DLAAS_USERNAME":"$DLAAS_PASSWORD" "$DLAAS_URL/v1/models?version=2017-02-13" | jq '.'` )

# show models
if ($?DEBUG) echo "$0:t $$ -- [debug] models = $models" >& /dev/stderr


###
### START DLAAS SETUP
###

set training_set = $data[1]
set test_set = $data[2]

##
## NETWORK
##

set network = "$thisdir/$container.network.prototxt"
if (-e "$network") then
  echo "$0:t $$ -- [WARN] deleting existing network ($network)"
  rm -f "$network"
endif

# ALEXNET NETWORK

echo 'name: "AlexNet"' >>! "$network"
if ($?mean_image) then
  echo 'layer { name: "data" type: "Data" top: "data" top: "label" include { phase: TRAIN } transform_param { mirror: true crop_size: 227 mean_file: "'"$mean_image"'" } data_param { source: "'"$training_set"'" batch_size: 256 backend: LMDB } }' >>! "$network"
  echo 'layer { name: "data" type: "Data" top: "data" top: "label" include { phase: TEST } transform_param { mirror: false crop_size: 227 mean_file: "'"$mean_image"'" } data_param { source: "'"$test_set"'" batch_size: 50 backend: LMDB } }' >>! "$network"
else
  echo 'layer { name: "data" type: "Data" top: "data" top: "label" include { phase: TRAIN } transform_param { mirror: true crop_size: 227 } data_param { source: "'"$training_set"'" batch_size: 256 backend: LMDB } }' >>! "$network"
  echo 'layer { name: "data" type: "Data" top: "data" top: "label" include { phase: TEST } transform_param { mirror: false crop_size: 227 } data_param { source: "'"$test_set"'" batch_size: 50 backend: LMDB } }' >>! "$network"
endif
echo 'layer { name: "conv1" type: "Convolution" bottom: "data" top: "conv1" param { lr_mult: 1 decay_mult: 1 } param { lr_mult: 2 decay_mult: 0 } convolution_param { num_output: 96 kernel_size: 11 stride: 4 weight_filler { type: "gaussian" std: 0.01 } bias_filler { type: "constant" value: 0 } } }' >>! "$network"
echo 'layer { name: "relu1" type: "ReLU" bottom: "conv1" top: "conv1" }' >>! "$network"
echo 'layer { name: "norm1" type: "LRN" bottom: "conv1" top: "norm1" lrn_param { local_size: 5 alpha: 0.0001 beta: 0.75 } }' >>! "$network"
echo 'layer { name: "pool1" type: "Pooling" bottom: "norm1" top: "pool1" pooling_param { pool: MAX kernel_size: 3 stride: 2 } }' >>! "$network"
echo 'layer { name: "conv2" type: "Convolution" bottom: "pool1" top: "conv2" param { lr_mult: 1 decay_mult: 1 } param { lr_mult: 2 decay_mult: 0 } convolution_param { num_output: 256 pad: 2 kernel_size: 5 group: 2 weight_filler { type: "gaussian" std: 0.01 } bias_filler { type: "constant" value: 0.1 } } }' >>! "$network"
echo 'layer { name: "relu2" type: "ReLU" bottom: "conv2" top: "conv2" }' >>! "$network"
echo 'layer { name: "norm2" type: "LRN" bottom: "conv2" top: "norm2" lrn_param { local_size: 5 alpha: 0.0001 beta: 0.75 } }' >>! "$network"
echo 'layer { name: "pool2" type: "Pooling" bottom: "norm2" top: "pool2" pooling_param { pool: MAX kernel_size: 3 stride: 2 } }' >>! "$network"
echo 'layer { name: "conv3" type: "Convolution" bottom: "pool2" top: "conv3" param { lr_mult: 1 decay_mult: 1 } param { lr_mult: 2 decay_mult: 0 } convolution_param { num_output: 384 pad: 1 kernel_size: 3 weight_filler { type: "gaussian" std: 0.01 } bias_filler { type: "constant" value: 0 } } }' >>! "$network"
echo 'layer { name: "relu3" type: "ReLU" bottom: "conv3" top: "conv3" }' >>! "$network"
echo 'layer { name: "conv4" type: "Convolution" bottom: "conv3" top: "conv4" param { lr_mult: 1 decay_mult: 1 } param { lr_mult: 2 decay_mult: 0 } convolution_param { num_output: 384 pad: 1 kernel_size: 3 group: 2 weight_filler { type: "gaussian" std: 0.01 } bias_filler { type: "constant" value: 0.1 } } }' >>! "$network"
echo 'layer { name: "relu4" type: "ReLU" bottom: "conv4" top: "conv4" }' >>! "$network"
echo 'layer { name: "conv5" type: "Convolution" bottom: "conv4" top: "conv5" param { lr_mult: 1 decay_mult: 1 } param { lr_mult: 2 decay_mult: 0 } convolution_param { num_output: 256 pad: 1 kernel_size: 3 group: 2 weight_filler { type: "gaussian" std: 0.01 } bias_filler { type: "constant" value: 0.1 } } }' >>! "$network"
echo 'layer { name: "relu5" type: "ReLU" bottom: "conv5" top: "conv5" }' >>! "$network"
echo 'layer { name: "pool5" type: "Pooling" bottom: "conv5" top: "pool5" pooling_param { pool: MAX kernel_size: 3 stride: 2 } }' >>! "$network"
echo 'layer { name: "fc6" type: "InnerProduct" bottom: "pool5" top: "fc6" param { lr_mult: 1 decay_mult: 1 } param { lr_mult: 2 decay_mult: 0 } inner_product_param { num_output: 4096 weight_filler { type: "gaussian" std: 0.005 } bias_filler { type: "constant" value: 0.1 } } }' >>! "$network"
echo 'layer { name: "relu6" type: "ReLU" bottom: "fc6" top: "fc6" }' >>! "$network"
echo 'layer { name: "drop6" type: "Dropout" bottom: "fc6" top: "fc6" dropout_param { dropout_ratio: 0.5 } }' >>! "$network"
echo 'layer { name: "fc7" type: "InnerProduct" bottom: "fc6" top: "fc7" param { lr_mult: 1 decay_mult: 1 } param { lr_mult: 2 decay_mult: 0 } inner_product_param { num_output: 4096 weight_filler { type: "gaussian" std: 0.005 } bias_filler { type: "constant" value: 0.1 } } }' >>! "$network"
echo 'layer { name: "relu7" type: "ReLU" bottom: "fc7" top: "fc7" }' >>! "$network"
echo 'layer { name: "drop7" type: "Dropout" bottom: "fc7" top: "fc7" dropout_param { dropout_ratio: 0.5 } }' >>! "$network"
echo 'layer { name: "fc8" type: "InnerProduct" bottom: "fc7" top: "fc8" param { lr_mult: 1 decay_mult: 1 } param { lr_mult: 2 decay_mult: 0 } inner_product_param { num_output: '$classes' weight_filler { type: "gaussian" std: 0.01 } bias_filler { type: "constant" value: 0 } } }' >>! "$network"
echo 'layer { name: "accuracy" type: "Accuracy" bottom: "fc8" bottom: "label" top: "accuracy" include { phase: TEST } }' >>! "$network"
echo 'layer { name: "loss" type: "SoftmaxWithLoss" bottom: "fc8" bottom: "label" top: "loss" }' >>! "$network"

if ($?DEBUG) cat "$network" >& /dev/stderr

##
## WEIGHTS
##

# ALEXNET

if ($?CAFFE_MODEL == 0) set CAFFE_MODEL = "http://dl.caffe.berkeleyvision.org/bvlc_alexnet.caffemodel"

set weights = "$thisdir/$container.weights.caffemodel"
if (-e "$weights") then
  echo "$0:t $$ -- [WARN] using existing weights ($weights)"
else if ($?CAFFE_MODEL) then
  curl -s -q -f -L "$CAFFE_MODEL" -o "$weights"
  if ($status == 22 || $status == 28 || ! -s "$weights") then
    echo "$0:t $$ -- [ERROR] failed to find weights ($weights); CAFFE_MODEL = $CAFFE_MODEL" >& /dev/stderr
    exit 1
  endif
else
  unset weights
endif

##
## SOLVER
##

set solver = "$thisdir/$container.solver.prototxt"
if (-e "$solver") then
  echo "$0:t $$ -- [WARN] deleting existing solver ($solver)"
  rm -f "$solver"
endif

# ALEXNET SOLVER

echo 'net: "'"$network"'"' >>! "$solver"
echo 'test_iter: 1000' >>! "$solver"
echo 'test_interval: 1000' >>! "$solver"
echo 'base_lr: 0.01' >>! "$solver"
echo 'lr_policy: "step"' >>! "$solver"
echo 'gamma: 0.1' >>! "$solver"
echo 'stepsize: 100000' >>! "$solver"
echo 'display: 20' >>! "$solver"
echo 'max_iter: 450000' >>! "$solver"
echo 'momentum: 0.9' >>! "$solver"
echo 'weight_decay: 0.0005' >>! "$solver"
echo 'snapshot: 10000' >>! "$solver"
echo 'snapshot_prefix: "${DATA_DIR}/'"$weights:t"'"' >>! "$solver"
echo 'solver_mode: GPU' >>! "$solver"

if ($?DEBUG) cat "$solver" >& /dev/stderr


##
## ZIP IT ALL UP
##

set zip = ( $solver $network )
if ($?weights) then
  set zip = ( $zip $weights )
endif

##
## MANIFEST 
##

set manifest = "$TMP/$0:t.$$.manifest.yaml"
if (-e "$manifest") then
  echo "$0:t $$ -- [WARN] deleting existing manifest ($manifest)"
  rm -f "$manifest"
endif

echo "name: $container" >>! "$manifest"
echo 'version: "'"1.0"'"' >>! "$manifest"
echo "description: Caffe model running on GPUs." >>! "$manifest"
echo "gpus: 1" >>! "$manifest"
echo "memory: 500MiB" >>! "$manifest"
echo "" >>! "$manifest"
echo "data_stores:" >>! "$manifest"
echo "  - id: $container" >>! "$manifest"
echo "    type: bluemix_objectstore" >>! "$manifest"
echo "    training_data:" >>! "$manifest"
echo "      container: $container" >>! "$manifest"
echo "    training_results:" >>! "$manifest"
echo "      container: $container" >>! "$manifest"
echo "    connection:" >>! "$manifest"
echo "      auth_url: $auth_url" >>! "$manifest"
echo "      user_name: $username" >>! "$manifest"
echo "      password: $password" >>! "$manifest"
echo "      domain_name: $domainName" >>! "$manifest"
echo "      region: $region" >>! "$manifest"
echo "      project_id: $projectId" >>! "$manifest"
echo "" >>! "$manifest"
echo "framework:" >>! "$manifest"
echo "  name: caffe" >>! "$manifest"
echo '  version: "'"1.0-py2"'"' >>! "$manifest"
if ($?weights) then
  echo "  command: caffe train -solver $solver -gpu all -weights $weights" >>! "$manifest"
else
  echo "  command: caffe train -solver $solver -gpu all" >>! "$manifest"
endif


if ($?DEBUG) cat "$manifest" >& /dev/stderr

####
#### END
####

# cleanup 
if ($?DELETE) then
  echo "$0:t $$ -- [debug]  DELETE CONTAINER: $c" >& /dev/stderr
  swift $VERBOSE --os-auth-token "$auth" --os-storage-url "$sturl" delete `echo "$container" | sed 's/%20/ /g'` >& /dev/stderr
endif

# end
set containers = ( `swift $VERBOSE --os-auth-token "$auth" --os-storage-url "$sturl" list | sed 's/ /%20/g'` )
if ($?DEBUG) echo "$0:t $$ -- [debug]  RESIDUAL CONTAINERS: $containers" >& /dev/stderr

