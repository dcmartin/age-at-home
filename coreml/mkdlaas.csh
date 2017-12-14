#!/bin/csh -fb

if ($?MODEL_IMAGE_HEIGHT == 0) setenv MODEL_IMAGE_HEIGHT 224
if ($?MODEL_IMAGE_WIDTH == 0) setenv MODEL_IMAGE_WIDTH 224
if ($?SAMPLE_SET_FORMAT == 0) setenv SAMPLE_SET_FORMAT lmdb
if ($?SAMPLE_DATA_FORMAT == 0) setenv SAMPLE_DATA_FORMAT png

# change for production
setenv DEBUG true
# setenv DELETE_FAILED_MODELS true
setenv DOWNLOAD_TRAINED_MODELS true

###
### CONTENT SOURCE
###

if ($?ROOTDIR == 0) setenv ROOTDIR /var/lib/age-at-home/label
if ($?DEBUG) echo '[ENV] ROOTDIR (' "$ROOTDIR" ')' >& /dev/stderr
if (! -e "$ROOTDIR" || ! -d "$ROOTDIR") then
  echo "$0:t $$ -- [ERROR] directory $ROOTDIR is not available" >& /dev/stderr
  exit 1
endif

###
### PREREQUISITE CHECK
###

$0:h/mkreqs.csh >& /dev/stderr

# ALEXNET by default
if ($?PRETRAINED_MODEL == 0) set PRETRAINED_MODEL = "http://dl.caffe.berkeleyvision.org/bvlc_alexnet.caffemodel"

####
####
#### START (PROCESS ARGUMENTS)
####
####

if ($?DEBUG) echo "$0:t $$ -- [debug] $0 $argv ($#argv)" >& /dev/stderr

# get source
if ($#argv > 0) then
  set device = "$argv[1]"
endif
if ($?device == 0) set device = "rough-fog"
if ($?DEBUG) echo "$0:t $$ -- [ARG] device ($device)" >& /dev/stderr

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
endif
if ($?percentages == 0) then
  set percentages = ( 75 25 )
endif
if ($?DEBUG) echo "$0:t $$ -- [ARG] <device> percentages ($percentages)" >& /dev/stderr

if ($?total) then
  if ($total != 100) then
    echo "$0:t $$ -- [ERROR] set breakdown ($percentages) across $#percentages does not total 100%" >& /dev/stderr
    exit
  endif
endif

####
####
#### DATA (LMDB & MAPS)
####
####

# validate executable
if (! -e "$0:h/mklmdb.csh") then
  echo "$0:t $$ -- [ERROR] mklmdb.csh not found ($0:h/mklmdb.csh)" >& /dev/stderr
  exit
endif

##
## CREATE LMDB and MAPS from directory ($ROOTDIR)
##

if ($?DEBUG) echo "$0:t $$ -- CALLING $0:h/mklmdb.csh [ device: $device; percentages: $percentages ]" >& /dev/stderr
set json = ( `$0:h/mklmdb.csh $device $percentages | jq '.'` )
if ($?json) then
  if ($#json && "$json" != "null") then
    set dlaasjob = ( `echo "$json" | jq -r '.name'` )

    if ($#dlaasjob && "$dlaasjob" != "null") then
      set thisdir = ( `jq -r '.thisdir' "$dlaasjob.json"` )
      if (-e "$thisdir" && -d "$thisdir" && -e "$thisdir/$dlaasjob.json") then
        if ($?DEBUG) echo "$0:t $$ -- [debug] successfully created LMDB ($dlaasjob)" >& /dev/stderr
      else
        unset thisdir
      endif
    else
      unset dlaasjob
    endif
endif
# both should be good
if ($?thisdir == 0 || $?dlaasjob == 0) then
    echo "$0:t $$ -- [ERROR] mklmdb.csh failed: { $json }" >& /dev/stderr
    cat /tmp/$0:t.$$.log >& /dev/stderr
    rm -f /tmp/$0:t.$$.log
    exit 1
endif
if ($?DEBUG) echo "$0:t $$ -- JOB $json" >& /dev/stderr

###
### TEST DATA & MAPS (OPTIONAL)
###

set count = ( `jq -r '.source.count' "$dlaasjob.json"` )
if ($?DEBUG) echo "$0:t $$ -- [debug] $dlaasjob samples = $count" >& /dev/stderr
rm -f /tmp/$0:t.$$.log

# check the maps
set maps = ( `jq -r '.sample.maps[].file' "$dlaasjob.json"` )
foreach m ( $maps )
  if (-e "$thisdir/$m") then
    set mcc = `awk '{ print $2 }' "$thisdir/$m" | sort | uniq | wc -l`
    if ($?mapclasscount) then
      if ($mcc != $mapclasscount) then
        echo "$0:t $$ -- [ERROR] FAILURE - $m class counts not equal ($mcc,$mapclasscount)" >& /dev/stderr
        exit 1
      endif
    endif
    set mapclasscount = $mcc
  else 
    echo "$0:t $$ -- [ERROR] FAILURE - $thisdir/$m does not exist" >& /dev/stderr
    exit 1
  endif
end

# check the data
set data = ( `jq -r '.sample.data[].file' "$dlaasjob.json"` )
@ total_entries = 0
set entries = ()
foreach d ( $data )
 if (-e "$thisdir/$d" && -d "$thisdir/$d") then
    set entries = ( $entries `mdb_stat "$thisdir/$d" | egrep "Entries: " | awk -F: '{ print $2 }'` )
    @ total_entries += $entries[$#entries]
  else
    echo "$0:t $$ -- [ERROR] FAILURE - $thisdir/$d does not exist or is not a directory" >& /dev/stderr
    exit 1
  endif
end
if ($total_entries != $count) then
  echo "$0:t $$ -- [ERROR] FAILURE - data count ($total_entries) does not equal specification ($count)" >& /dev/stderr
  exit
endif

# report on distribution 
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
  
####
####
#### DLAAS MODEL
####
####

if (! -e ~$USER/.watson.dlaas.json) then
  echo "$0:t $$ -- [ERROR] cannot find Watson DL-AAS credentials (~$USER/.watson.dlaas.json)" >&! /dev/stderr
  exit 1
else
  set DLAAS_USERNAME = ( `jq -r '.username?' ~$USER/.watson.dlaas.json` )
  set DLAAS_URL = ( `jq -r '.url?' ~$USER/.watson.dlaas.json` )
  set DLAAS_PASSWORD = ( `jq -r '.password?' ~$USER/.watson.dlaas.json` )
endif

model:

# sanity check
if ($?dlaasjob == 0 || $?thisdir == 0) then
  echo "$0:t $$ -- [ERROR] no DLAASJOB" >& /dev/stderr
  exit 1
else if (! -e "$thisdir/$dlaasjob.json") then
  echo "$0:t $$ -- [ERROR] cannot find $thisdir/$dlaasjob.json" >& /dev/stderr
  exit 1
endif

# get prior model
set model = ( `jq -r '.model?' "$dlaasjob.json"` )
if ($#model <= 1) then
  set model = '{"type":"caffe","version":"1.0-py2"}'
endif

###
### MODEL PRETRAIN 
###

set pretrain = ( `echo "$model" | jq -r '.pretrain?'` )
if ($#pretrain == 0 || "$pretrain" == "null") set pretrain = '{}'

# PRETRAIN URL
set url = ( `echo "$pretrain" | jq -r '.url?'` )
if (($#url == 0 || "$url" == "null" ) && $?PRETRAINED_MODEL) then
  set url = "$PRETRAINED_MODEL"
else
  unset url
endif
if ($?url) then
  set pretrain = ( `echo "$pretrain" | jq '.url="'"$url"'"'` )
endif

# PRETRAIN WEIGHTS
set weights = ( `echo "$pretrain" | jq -r '.weights?'` )
if ($#weights && "$weights" != "null") then
  set weights = "$thisdir/$weights"; if (! -e "$weights") unset weights
else
  unset weights
endif
if ($?weights == 0) then
  if ($?url) then
    set weights = "$thisdir/$dlaasjob.caffemodel"

    if ( ! -e "$weights") then
      curl -s -q -f -L "$url" -o "$weights"
      if ($status == 22 || $status == 28 || ! -e "$weights") then
        echo "$0:t $$ -- [ERROR] failed to download weights; URL = $url" >& /dev/stderr
        exit 1
      endif
    endif
  endif 
endif
if ($?weights) then
  set pretrain = ( `echo "$pretrain" | jq '.weights="'"$weights:t"'"'` )
endif

## UPDATE MODEL (PRETRAIN)
if ($#pretrain > 1) then
  set model = ( `echo "$model" | jq '.pretrain='"$pretrain"` )
endif

###
### MODEL TRAINING
###

# only handle two sets (training and test)
set data = ( `jq -r '.sample.data[].id' "$dlaasjob.json"` )
if ($#data != 2) then
  echo "$0:t $$ -- [ERROR] invalid number of sets; only two (2) allowed: $#data" >& /dev/stderr
  exit 1
else
  # get training and test set
  set training_set = ( `jq -r '.sample.data[0].file' "$dlaasjob.json"` )
  set test_set = ( `jq -r '.sample.data[1].file' "$dlaasjob.json"` )
  # get count of classes
  set class_count = ( `jq -r '.source.classes|length' "$dlaasjob.json"` )
endif

# PRIOR TRAINING
set training = ( `echo "$model" | jq -r '.training?'` )
if ($#training == 0 || "$training" == "null") set training = '{}'

## TRAINING NETWORK w/ training and test sets
set network = ( `echo "$training" | jq -r '.network?'` )
if ($#network && "$network" != "null") then
  set network = "$thisdir/$network"
else 
  set network = "$thisdir/$dlaasjob.network.prototxt"
endif
$0:h/mknetwork.csh "$training_set" "$test_set" "$class_count" >! "$network"
if ($status != 0 || ! -e "$network") then
  echo "$0:t $$ -- [ERROR] failed to build network" >& /dev/stderr
  exit 1
endif
if ($?network) then
  set training = ( `echo "$training" | jq '.network="'"$network:t"'"'` )
endif

## TRAINING SOLVER w/ network (above) defined
set solver = ( `echo "$training" | jq -r '.solver?'` )
if ($#solver && "$solver" != "null") then
  set solver = "$thisdir/$solver"
else
  set solver = "$thisdir/$dlaasjob.solver.prototxt"
endif
$0:h/mksolver.csh "$network:t" "$dlaasjob-snapshot" >! "$solver"
if ($status != 0 || ! -e "$solver") then
  echo "$0:t $$ -- [ERROR] failed to build solver" >& /dev/stderr
  exit 1
endif
if ($?solver) then
  set training = ( `echo "$training" | jq '.solver="'"$solver:t"'"'` )
endif

## UPDATE MODEL (TRAINING)
if ($#training > 1) then
  # update model
  set model = ( `echo "$model" | jq '.training='"$training"` )
else
  echo "$0:t $$ -- [ERROR] models require training" >& /dev/stderr
  exit
endif

###
### UPDATE JSON (MODEL) 
###

if ($#model > 1) then
  set json = ( `echo "$json" | jq '.model='"$model"` )
else
  echo "$0:t $$ -- [ERROR] jobs require models" >& /dev/stderr
  exit
endif

###
### STORE MODEL
###

echo "$json" | jq '.' >! "$dlaasjob.json"

####
####
#### STORE FILES
####
####

store:

if ($?DEBUG) then
  set storage = ( `jq -r '.storage?' "$dlaasjob.json"` )
  echo "$0:t $$ -- [debug] storage = " `echo "$storage" | jq -c '.'` >& /dev/stderr
endif

# do storage
set storage = ( `$0:h/mkswift.csh "$dlaasjob"` )
if ($#storage && "$storage" != "null") then
  set auth_url = ( `jq -r '.storage.auth_url' "$dlaasjob.json"` )
  set username = ( `jq -r '.storage.user_name' "$dlaasjob.json"` )
  set password = ( `jq -r '.storage.password' "$dlaasjob.json"` )
  set domainName = ( `jq -r '.storage.domain_name' "$dlaasjob.json"` )
  set projectId = ( `jq -r '.storage.project_id' "$dlaasjob.json"` )
  set region = ( `jq -r '.storage.region' "$dlaasjob.json"` )
else
  echo "$0:t $$ -- [ERROR] invalid storage ($storage)" >& /dev/stderr
  exit 1
endif

##
## MANIFEST 
##

set manifest = ( `jq -r '.training.manifest?' "$dlaasjob.json"` )
if ($#manifest == 0 || "$manifest" == "null") then
  set manifest = "$thisdir/$dlaasjob.manifest.yaml"
endif

if (-e "$manifest") then
  echo "$0:t $$ -- [WARN] existing manifest; deleting $manifest" >& /dev/stderr
  rm -f "$manifest"
endif

echo "name: $dlaasjob" >>! "$manifest"
echo 'version: "'"1.0"'"' >>! "$manifest"
echo "description: Caffe model running on GPUs." >>! "$manifest"
echo "gpus: 1" >>! "$manifest"
echo "memory: 500MiB" >>! "$manifest"
echo "" >>! "$manifest"
echo "data_stores:" >>! "$manifest"
echo "  - id: $dlaasjob" >>! "$manifest"
echo "    type: bluemix_objectstore" >>! "$manifest"
echo "    training_data:" >>! "$manifest"
echo "      container: $dlaasjob" >>! "$manifest"
echo "    training_results:" >>! "$manifest"
echo "      container: $dlaasjob" >>! "$manifest"
echo "    connection:" >>! "$manifest"
echo "      auth_url: "\""$auth_url"\" >>! "$manifest"
echo "      user_name: "\""$username"\" >>! "$manifest"
echo "      password: "\""$password"\" >>! "$manifest"
echo "      domain_name: "\""$domainName"\" >>! "$manifest"
echo "      region: "\""$region"\" >>! "$manifest"
echo "      project_id: "\""$projectId"\" >>! "$manifest"
echo "" >>! "$manifest"
echo "framework:" >>! "$manifest"
echo "  name: caffe" >>! "$manifest"
echo '  version: "'"1.0-py2"'"' >>! "$manifest"
# WEIGHTS
echo -n '  command: caffe train -solver ${DATA_DIR}/'"$solver:t"' -gpu all' >>! "$manifest"
if ($?weights) then
  echo ' -weights ${DATA_DIR}/'"$weights:t" >>! "$manifest"
else
  echo '' >>! "$manifest"
endif


##
## ZIP IT ALL UP
##

set zip = ( "$solver:t" "$network:t" )

if (-e "$thisdir/$dlaasjob.zip") then
  if ($?DEBUG) echo "$0:t $$ -- [WARN] existing ZIP file; deleting $thisdir/$dlaasjob.zip" >& /dev/stderr
  rm -f "$thisdir/$dlaasjob.zip"
endif

pushd "$thisdir"
zip -u "$dlaasjob.zip" $zip
popd

####
####
#### DLAAS 
####
####

# we should start w/o a model identified (i.e. a DLAAS training ID)
if ($?model_id) then
  unset model_id
endif

##
## DLAAS MAIN LOOP (repeat until job is complete)
##

again:

## GET ALL MODELS FOR USER

set out = "/tmp/$0:t.$$.json"
curl -s -q -f -L -o "$out" -u "$DLAAS_USERNAME":"$DLAAS_PASSWORD" "$DLAAS_URL/v1/models?version=2017-02-13"
set models = ( `jq '.' "$out"` )
if ($#models <= 1) then
  echo "$0:t $$ -- [ERROR] invalid response from DLAAS" `cat "$out"` >& /dev/stderr
  rm -f "$out"
  exit 1
else
  rm -f "$out"
endif
# DEBUG
if ($?DEBUG) then
  set model_names = ( `echo "$models" | jq '.models[].name'` )
  echo "$0:t $$ -- [debug] MODELS ($#model_names): [ $model_names ]" >& /dev/stderr
  unset model_names
endif

## PROCESS ALL MODELS MATCHING "JOB" (<DEVICE>.<SETS>)

set mids = ( `echo "$models" | jq -r '.models[]|select(.name=="'"$dlaasjob"'")|.model_id?'` )
if ($#mids == 0 || "$mids" == "null") then
  if ($?DEBUG) echo "$0:t $$ -- [debug] no existing models for dlaasjob ($dlaasjob)" >& /dev/stderr
  unset models
else
  if ($?DEBUG) echo "$0:t $$ -- [debug] dlaasjob ($dlaasjob) has existing models ($mids)" >& /dev/stderr
  foreach mid ( $mids )
    set ts = ( `echo "$models" | jq '.models[]|select(.model_id=="'"$mid"'")|.training.training_status'` )
    set st = ( `echo "$ts" | jq -r '.status'` )
    set loc = ( `echo "$ts" | jq -r '.location'` )

    if ($?DEBUG) echo "$0:t $$ -- [debug] handling $st model ($mid) for dlaasjob ($dlaasjob)" >& /dev/stderr

    switch ($st)
      case "FAILED":
        if ($?DEBUG) echo "$0:t $$ -- [debug] $mid state: $st for dlaasjob ($dlaasjob)" >& /dev/stderr
	# ONLY DELETES MODEL IN DLAAS
	if ($?DELETE_FAILED_MODELS) then
	  echo "$0:t $$ -- [WARN] DELETING $mid ($st)" >& /dev/stderr
	  set out = "/tmp/$0:t.$$.json"
	  curl -s -q -f -L -o "$out" -u "$DLAAS_USERNAME":"$DLAAS_PASSWORD" -XDELETE "$DLAAS_URL/v1/models/"$mid"?version=2017-02-13"
	  if ($status == 22 || $status == 28 || ! -e "$out") then
	    echo "$0:t $$ -- [WARN] failed to delete model ($mid)" >& /dev/stderr
	  else
	    set m = ( `jq -r '.model_id' "$out"` )
	    if ($m != $mid) then
	      echo "$0:t $$ -- [WARN] failed to delete model ($m)" >& /dev/stderr
	    endif
	  endif
	endif
        breaksw
      case "PENDING":
      case "DOWNLOADING":
      case "PROCESSING":
      case "STORING":
        if ($?DEBUG) echo "$0:t $$ -- [debug] USING $mid state: $st for dlaasjob ($dlaasjob)" >& /dev/stderr
        set model_id = $mid
        breaksw
      default:
        if ($?DEBUG) echo "$0:t $$ -- [debug] $mid state: $st for dlaasjob ($dlaasjob)" >& /dev/stderr
	# DOWNLOAD MODEL DEFINITION AND TRAINED MODEL (WEIGHTS)
	if ($?DOWNLOAD_TRAINED_MODELS) then
	  if ($?DEBUG) echo "$0:t $$ -- [debug] DOWNLOADING $mid ($st)" >& /dev/stderr
          # RETURNS: <<ZIP ARCHIVE>>
	  set out = "/tmp/$0:t.$$.zip"
	  curl -s -q -f -L -o "$out" -u "$DLAAS_USERNAME":"$DLAAS_PASSWORD" -XGET "$DLAAS_URL/v1/models/$mid/definition?version=2017-02-13"
	  if ($status == 22 || $status == 28 || ! -e "$out") then
	    echo "$0:t $$ -- [WARN] failed to download model definition ($mid)" >& /dev/stderr
          else
	    # move to destination
            set modeldef = "$mid-definition.zip"
            mv -f -n "$out" "$thisdir/$modeldef"
            if (-e "$thisdir/$modeldef") then
	      if ($?DEBUG) echo "$0:t $$ -- [debug] DOWNLOADED $thisdir/$modeldef" >& /dev/stderr
            else
	      echo "$0:t $$ -- [ERROR] failed model definition ($thisdir/$modeldef)" >& /dev/stderr
              exit 1
            endif
	  endif
          # if we got definition, go for weights
          if ($?modeldef) then
	    # RETURNS: <<ZIP ARCHIVE>>
	    set out = "/tmp/$0:t.$$.zip"
	    curl -s -q -f -L -o "$out" -u "$DLAAS_USERNAME":"$DLAAS_PASSWORD" -XGET "$DLAAS_URL/v1/models/$mid/trained_model?version=2017-02-13"
	    if ($status == 22 || $status == 28 || ! -e "$out") then
	      echo "$0:t $$ -- [WARN] failed to download model definition ($mid)" >& /dev/stderr
	    else
              # move to destination
	      set trained = "$mid-trained.zip"
	      mv -f -n "$out" "$thisdir/$trained"
	      if (-e "$thisdir/$trained") then
		if ($?DEBUG) echo "$0:t $$ -- [debug] DOWNLOADED $thisdir/$trained" >& /dev/stderr
	      else
		echo "$0:t $$ -- [ERROR] failed model training ($thisdir/$trained)" >& /dev/stderr
		exit 1
	      endif
            endif
          endif
	endif
        set model_id = $mid
        breaksw
    endsw
  end
endif

##
## START TRAINING 
##

# if we did not find an existing model for this job, start one
if ($?model_id == 0) then
  set out = "/tmp/$0:t.$$.json"
  curl -s -q -f -L -o "$out" -u "$DLAAS_USERNAME":"$DLAAS_PASSWORD" "$DLAAS_URL/v1/models?version=2017-02-13" -F "model_definition=@$thisdir/$dlaasjob.zip" -F "manifest=@$manifest"
  if ($status == 22 || $status == 28 || ! -e "$out") then
    echo "$0:t $$ -- [ERROR] failed to submit DLAAS job ($dlaasjob)" >& /dev/stderr
    exit 1
  else
    # EXAMPLE {"model_id":"training-825OVpLzg","location":"/v1/models/training-825OVpLzg"}
    set model_id = ( `jq -r '.model_id?' "$out"` )
    set location = ( `jq -r '.location?' "$out"` )
    rm -f "$out"
    if ($#model_id && "$model_id" != "null") then
      if ($?DEBUG) echo "$0:t $$ -- [debug] model_id: $model_id" >& /dev/stderr
    else
      if ($?DEBUG) echo "$0:t $$ -- [debug] job ($dlaasjob) failure" >& /dev/stderr
      exit 1
    endif
    if ($?DEBUG) echo "$0:t $$ -- [debug] DLAAS job ($dlaasjob) submitted; model_id: $model_id; location: $location" >& /dev/stderr
  endif
  goto again
endif

# if we have training in-flight, test if done or loop to again
if ($?model_id) then
  # WAIT UNTIL DONE
  if ($?models) then
    set training_status = ( `echo "$models" | jq '.models[]|select(.model_id=="'$model_id'").training.training_status?'` )
    if ($#training_status == 0 || "$training_status" == "null") then
      echo "$0:t $$ -- [WARN] invalid training_status for model ($model_id) $training_status" >& /dev/stderr
    endif
    # get current
    set current = ( `echo "$training_status" | jq -r '.status?'` )
    if ($#current && "$current" != "null") then
      switch ($current)
        case "FAILED":
          echo "$0:t $$ -- [INFO] $current ($dlaasjob); model ($model_id)" >& /dev/stderr
          set model = ( `echo "$models" | jq '.models[]|select(.model_id=="'$model_id'")'` )
          breaksw
        case "PENDING":
        case "DOWNLOADING":
        case "PROCESSING":
        case "STORING":
          echo "$0:t $$ -- [INFO] IN-FLIGHT: $current $model_id for JOB: $dlaasjob" >& /dev/stderr
          sleep 5
          goto again
          breaksw
        default:
          if ($?DEBUG) echo "$0:t $$ -- [debug] UNKNOWN STATE ($st)" >& /dev/stderr
          breaksw
      endsw
    endif
  else
    echo "$0:t $$ -- [INFO] INITIATING: $current ($dlaasjob); model ($model_id)" >& /dev/stderr
    goto again
  endif
else
  echo "$0:t $$ -- [WARN] no training for JOB: $dlaasjob" >& /dev/stderr
endif

## UPDATE
if ($?model) then
  echo "$json" | jq '.model.results='"$model" | tee "$dlaasjob.json"
 
  ## CAPTURE RESULTS
  set json = ( `$0:h/mkswift.csh "$dlaasjob"` )

else
  echo "$0:t $$ -- [ERROR] no model for JOB: $dlaasjob" >& /dev/stderr
  exit 1
endif

####
#### END
####

cleanup:

if ($?DELETE) then
  echo "$0:t $$ -- [debug]  DELETE CONTAINER: $c" >& /dev/stderr
  swift $VERBOSE --os-auth-token "$auth" --os-storage-url "$sturl" delete `echo "$container" | sed 's/%20/ /g'` >& /dev/stderr
  if ($?DEBUG) then
    set containers = ( `swift $VERBOSE --os-auth-token "$auth" --os-storage-url "$sturl" list | sed 's/ /%20/g'` )
    echo "$0:t $$ -- [debug]  RESIDUAL CONTAINERS: $containers" >& /dev/stderr
  endif
endif
