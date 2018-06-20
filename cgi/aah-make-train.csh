#!/bin/csh
setenv APP "aah"
setenv API "train"
setenv WWW "www.dcmartin.com"

# setenv DEBUG true 
# setenv VERBOSE true 

if ($?TMP == 0) setenv TMP "/tmp"
if ($?AAHDIR == 0) setenv AAHDIR "/var/lib/age-at-home"
if ($?LOGTO == 0) setenv LOGTO $TMP/$APP.log

# don't update file information more than once per (in seconds)
setenv TTL 28800
setenv SECONDS `date "+%s"`
setenv DATE `echo $SECONDS \/ $TTL \* $TTL | bc`

#
# CLOUDANT SETUP
#
set creds = ~$USER/.cloudant_url
if (-e $creds) then
    set cc = ( `cat $creds` )
    if ($#cc > 0) set CU = $cc[1]
    if ($#cc > 1) set CN = $cc[2]
    if ($#cc > 2) set CP = $cc[3]
endif
if ($?CLOUDANT_URL) then
    set CU = $CLOUDANT_URL
else if ($?CN && $?CP) then
    set CU = "$CN":"$CP"@"$CN.cloudant.com"
else
    echo `date` "$0:t $$ -- no Cloudant URL ($creds)" >>&! $LOGTO
    exit
endif
if ($?DEBUG) echo `date` "$0:t $$ -- Cloudant noSQL ($CU)" >>&! $LOGTO

#
# VISUAL_RECOGNITION SETUP
#

set creds = ~$USER/.watson.visual-recognition.json
if (-e $creds) then
    # this is to handle multiple entires
    set keys = ( `jq '.[]|.credentials.api_key' $creds` )
    if ($#keys > 0) set api_key = `echo "$keys[1]" | sed 's/"//g'`
    set urls = ( `jq '.[]|.credentials.url' $creds` )
    if ($#urls > 0) set TU = `echo "$urls[1]" | sed 's/"//g'`
else 
    echo `date` "$0:t $$ -- no VisualRecognition ($creds)" >>&! $LOGTO
    exit
endif
if ($?TU && $?api_key) then
    if ($?verid == 0) set verid = "v3"
    if ($?vdate == 0) set vdate = "2016-05-20"
    if ($?DEBUG) echo `date` "$0:t $$ -- VisualRecognition $verid/$vdate ($TU)" >>&! $LOGTO
else
    echo `date` "$0:t $$ -- invalid VisualRecognition ($creds)" >>&! $LOGTO
    exit
endif

#
# PROCESS CGI QUERY_STRING
#

if ($?QUERY_STRING) then
    set device = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($device == "$QUERY_STRING") unset device
    set model = `echo "$QUERY_STRING" | sed 's/.*model=\([^&]*\).*/\1/'`
    if ($model == "$QUERY_STRING") unset model
    set notags = `echo "$QUERY_STRING" | sed 's/.*notags=\([^&]*\).*/\1/'`
    if ($notags == "$QUERY_STRING") unset notags
endif

#
# PROCESS COMMAND LINE ARGUMENTS
#
echo "$0:t [ -n <maxfiles> -D(elete old) -m <model_id> -j <job_id> -N <negative_class> -d <label_dir> -e {frame|sample}] <device-id>"

@ i = 1
while ($i <= $#argv)
    set t = "$argv[$i]"
    if (($#t == 1) && ($#argv >= $i)) then
	if ("$t" == "-n") then
	    @ i++
	    set maxfiles = $argv[$i]
	else if ("$t" == "-D") then
	    # delete existing model (must also specify -m <model>)
	    set delete = true
	else if ("$t" == "-e") then
	    @ i++
	    # full frame (jpg) or sample (jpeg)
	    switch ($argv[$i])
	    case "sample":
		set ext = "jpeg"
	        breaksw
	    case "frame":
	    default:
		set ext = "jpg"
	        breaksw
	    endsw
	else if ("$t" == "-m") then
	    @ i++
	    # model by <classifier_id>
	    set model = $argv[$i]
	else if ("$t" == "-j") then
	    @ i++
	    # find by job_id (DATE)
	    setenv DATE $argv[$i]
	else if ("$t" == "-N") then
	    @ i++
	    # negative example class
	    set notags  = $argv[$i]
	else if ("$t" == "-d") then
	    @ i++
	    # base path directory
	    setenv AAHDIR "$argv[$i]"
       else if ($#argv >= $i) then
	   # name of directory in $TMP/label
	   set device = "$argv[$i]"
       endif
    endif
    @ i++
end

#
# configure defaults
#
if ($?device == 0) set device = rough-fog
if ($?ext == 0) set ext = jpg

#
# check arguments
#
if ($?device && $?model && $?notags) then
    if ($?DEBUG) /bin/echo `/bin/date` "$0:t $$ -- $device $model $notags" 
    setenv QUERY_STRING "db=$device"
else if ($?notags == 0) then
    set location = `/usr/bin/curl -s -q -f -L "http://$WWW/CGI/aah-devices.cgi" | jq -r '.|select(.name=="'"$device"'")|.location'`
    if ($#location) then
	if ($?DEBUG) /bin/echo `/bin/date` "$0:t $$ -- found AAH_LOCATION ($location)" 
    else
	if ($?DEBUG) /bin/echo `/bin/date` "$0:t $$ -- not found AAH_LOCATION" 
	unset location
	exit
    endif
    if ($?DEBUG) /bin/echo `/bin/date` "$0:t $$ -- using default ($location) for negative (notags)" 
    set notags = "$location"
endif

setenv QUERY_STRING "db=$device&ext=$ext"

echo `date` "$0:t $$ -- START ($QUERY_STRING)" >>&! $LOGTO

#
# FIND OLD MODEL
#

if ($?CLOUDANT_OFF == 0) then
    set db = ( `curl -s -q -L "$CU/$device-$API" | jq '.'` )
    if ($#db) then
      set error = ( `echo "$db" | jq '.error,.reason' | sed 's/"//g'` )
      if ($#error > 0 && $error[1] == "not_found") then
        if ($?DEBUG) echo `date` "$0:t $$ -- $error[2-] ($device-$API)" >>&! $LOGTO
	unset db
      endif
    endif
    if ($?db && $?model) then
      set model = ( `curl -s -q -L "$CU/$device-$API/_all_docs?include_docs=true" | jq '.rows[]|select(.doc.model=="'"$model"'")'` )
    else if ($?db) then
      set device_models = ( `curl -s -q -L "$CU/$device-$API/_all_docs?include_docs=true" | jq '.rows[]|select(.doc.name=="'"$device"'")'` )
    endif
    if ($?model) then
      if ($?DEBUG) echo `date` "$0:t $$ -- FOUND MODEL ($#model)" >>&! $LOGTO
      # CHECK INVENTORY AGAINST TRAINED SET
      set w = ( `echo "$model" | jq '.date' | sed 's/"//g'` )
      set s = ( `echo "$model" | jq '.images[].class' | sed 's/"//g'` )
      set p = ( `echo "$model" | jq '.detail.classes[].class' | sed 's/"//g'` )
      set n = ( `echo "$model" | jq '.negative' | sed 's/"//g'` )
      if ($?DEBUG) echo `date` "$0:t $$ -- EXISTING MODEL ($model) date ($w) sets ($s) negative ($n) positive ($p)" >>&! $LOGTO
      exit
    else if ($?device_models) then
      if ($?DEBUG) echo `date` "$0:t $$ -- DEVICE MODELS ($#device_models)" >>&! $LOGTO
      set classifier_ids = ( `echo "$device_models" | jq '.doc.detail.classifier_id' | sed 's/"//g'` )
      set models = ( `echo "$device_models" | jq '.doc.model' | sed 's/"//g'` )
      set dates = ( `echo "$device_models" | jq '.doc.date' | sed 's/"//g'` )
      # get models by date
      set date_model = ( `echo "$device_models" | jq '.|select(.doc.date=="'$DATE'")' ` )
      if ($#date_model) then
        set model = `echo "$date_model" | jq '.doc.model' | sed 's/"//g'`
	if ($?DEBUG) echo `date` "$0:t $$ -- model ($model) by date ($DATE) in Cloudant" >>&! $LOGTO
      endif
      if ($?DEBUG) echo `date` "$0:t $$ -- classifiers ($classifier_ids) models ($models)" >>&! $LOGTO
    endif
else
    if ($?DEBUG) echo `date` "$0:t $$ -- Cloudant OFF" >>&! $LOGTO
endif

if ($?model) then
    if ($?DEBUG) echo `date` "$0:t $$ -- model ($model) in Cloudant" >>&! $LOGTO
else
    if ($?DEBUG) echo `date` "$0:t $$ -- NO MODEL ($device)" >>&! $LOGTO
endif

##
## STEP 1 - INVENTORY
##

inventory:

if ($?previous && $?model) then
  if ($?DEBUG) echo `date` "$0:t $$ -- PREVIOUS MODEL ($model)" `jq '.' "$previous"` >>&! $LOGTO
endif

set INVENTORY = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
set INPROGRESS = ( `echo "$INVENTORY".*` )
if ($#INPROGRESS) then
    if ($?DEBUG) echo `date` "$0:t $$ -- inventory in-progress ($INPROGRESS)" >>&! $LOGTO
    goto done
else if (-s "$INVENTORY") then
    if ($?DEBUG) echo `date` "$0:t $$ -- found $INVENTORY" >>&! $LOGTO
    goto batch
endif
if ($?DEBUG) echo `date` "$0:t $$ -- finding old ($APP-$API-$QUERY_STRING.*.json)" >>&! $LOGTO
set old = ( `echo "$TMP/$APP-$API-$QUERY_STRING".*.json` )
if ($#old > 0) then
    if ($?DEBUG) echo `date` "$0:t $$ -- removing old ($old)" >>&! $LOGTO
    rm -f $old
endif
# indicate in-progress
if ($?DEBUG) echo `date` "$0:t $$ -- creating inventory $INVENTORY" >>&! $LOGTO

# note specification of "label" subdirectory
if (! -d "$AAHDIR/label") then
    echo `date` "$0:t $$ -- no directory ($AAHDIR/label)" >>&! $LOGTO
    exit
endif

echo '{"name":"'$device'","negative":"'$notags'",' >! "$INVENTORY.$$"

unset classes
echo '"images":[' >> "$INVENTORY.$$"
# iterate
foreach xdir ( "$AAHDIR/label/$device/"* )
    if ($?DEBUG) echo `date` "$0:t $$ -- processing $xdir" >>&! $LOGTO
    if ($?set) echo ',' >> "$INVENTORY.$$"
    set set = "$xdir:t"
    if ($?classes) then
	set classes = "$classes"',"'"$set"'"'
    else
      set classes = '"'"$set"'"'
    endif
    echo '{"class":"'$set'","ids":[' >> "$INVENTORY.$$"
    @ count = 0
    @ bytes = 0
    foreach file ( `find "$xdir" -name "*.$ext" -type f -print` )
      if ($count > 0) echo ',' >> "$INVENTORY.$$"
      @ bytes += `ls -l $file | awk '{ print $5 }'`
      echo '"'"$file:t:r"'"' >> "$INVENTORY.$$"
      @ count++
    end
    echo '],"bytes":'$bytes',"count":'$count'}' >> "$INVENTORY.$$"
end
echo '],"classes":['"$classes"']}' >> "$INVENTORY.$$"
 
jq '.' "$INVENTORY.$$" >! "$INVENTORY"

rm -f "$INVENTORY.$$"

##
## STEP 2 - CALCULATE BATCH JOBS
##

batch:

set JOB = "$TMP/$APP-$API-$QUERY_STRING.$DATE.job"
set INPROGRESS = ( `echo "$JOB".*` )
if ($#INPROGRESS) then
    if ($?DEBUG) echo `date` "$0:t $$ -- batching in-progress ($INPROGRESS)" >>&! $LOGTO
    goto done
else if (-s "$JOB/job.json") then
    if ($?DEBUG) echo `date` "$0:t $$ -- existing batches ($JOB/job.json)" >>&! $LOGTO
    goto training
endif
set old = ( `echo "$TMP/$APP-$API-$QUERY_STRING".*.job` )
if ($#old > 0) then
    if ($?DEBUG) echo `date` "$0:t $$ -- removing old ($old); entries remain in DB and VR" >>&! $LOGTO
    rm -fr $old
endif
# indicate JOB in-progress
if ($?DEBUG) echo `date` "$0:t $$ -- batching jobs $JOB" >>&! $LOGTO
touch "$JOB.$$"
mkdir -p "$JOB"

#
# WATSON VISUAL RECOGNITION - INSTRUCTIONS
#
# SIZE LIMITATIONS (enforced by API)
# 
# The service accepts a maximum of 10,000 images or 100 MB per .zip file
# The service requires a minimum of 10 images per .zip file.
# The service accepts a maximum of 256 MB per training call.
#
# GUIDELINES (not enforced)
#
# Include approximately the same number of images in each examples file.
# Including an unequal number of images can cause the quality of the trained classifier to decline. 
#
# 1) A minimum of 50 images is recommended in each .zip file, as fewer than 50 images can decrease the quality of the trained classifier.
# 2) If the quality and content of training data is the same, then classifiers that are trained on more images will generally be more accurate 
#    than classifiers that are trained on fewer images. The benefits of training a classifier on more images plateaus at around 5000 images, 
#    and this can take a while to process. You can train a classifier on more than 5000 images, but it may not significantly increase that classifier's accuracy.
# 3) Uploading a total of 150-200 images per .zip file gives you the best balance between the time it takes to train and the improvement to classifier accuracy. 
#    More than 200 images increases the time, and it does increace the accuracy, but with diminishing returns for the amount of time it takes.
#
# ADDITIONAL INSTRUCTIONS
#
# Split into two or three sets: training, validation (for hyper-parameters) and testing (http://sebastianraschka.com/blog/2016/model-evaluation-selection-part3.html)
#
@ MAXIMAGES = 10000
@ MAXZIPBYTES = 1000 * 1000 * 90 # should be 100
@ MINIMAGES = 10
@ MAXSETBYTES = 256 * 1000 * 1000
@ MINSETSIZE = 50
@ MAXSETSIZE = 5000
@ MAXZIPSET = 200
@ SPLITSETS = 2

# get all classes as pairs of class name and count (including negative)
set allclass = ( `jq '[.images|sort_by(.count)[]|{"class":.class,"count":.count,"bytes":.bytes}]' "$INVENTORY"`)
if ($?DEBUG) echo `date` "$0:t $$ -- batching images by counts ($allclass)" >>&! $LOGTO

# process all samples into training, validation and test sets
set pairs = ( `echo "$allclass" | jq '.[]|.class,.count' | sed 's/"//g'` )
if ($#pairs == 0) then
    if ($?DEBUG) echo `date` "$0:t $$ -- NO PAIRS" >>&! $LOGTO
    exit
endif

@ p = 1
set job = '{"device":"'"$device"'","date":'"$DATE"',"jobs":['
unset sets
while ($p < $#pairs) 
    set class = $pairs[$p]
    @ p++
    set count = $pairs[$p]
    @ p++
    if ($?DEBUG) echo `date` "$0:t $$ -- CLASS ($class) COUNT ($count)" >>&! $LOGTO
    # calculate split size to create only SPLITSETS number of sets
    @ split = ( $count / $SPLITSETS ) + ( $count % $SPLITSETS )
    # test is split size is sufficient
    if ($split > $MINIMAGES) then
	# test if too many samples
	if ($split > $MAXSETSIZE) then
	    if ($?DEBUG) echo `date` "$0:t $$ -- split size ($MAXSETSIZE); actual ($split)" >>&! $LOGTO
	    set split = MAXSETSIZE
	else
	    if ($?DEBUG) echo `date` "$0:t $$ -- split size ($split)" >>&! $LOGTO
	endif
	set base = "$JOB/$class." 
	jq '.images[]|select(.class=="'$class'").ids[]' "$INVENTORY" | sed 's/"//g' | split -l $split - $base 
	set split = ( `echo $base*` )
	if ($?sets) then
	    set sets = "$sets"'},{"class":"'"$class"'","sets":'
	else
	    set sets = '{"class":"'"$class"'","sets":'
	endif
    else
	if ($?DEBUG) echo `date` "$0:t $$ -- insufficient samples ($split)" >>&! $LOGTO
	unset split
    endif
    if ($?split) then
	if ($?DEBUG) echo `date` "$0:t $$ -- processing ($split)" >>&! $LOGTO
	foreach s ( $split )
	    if ($?splits) then
		set splits = "$splits"','
	    else
		set splits = '['
	    endif
	    set sext = $s:e
	    # create ZIP file name 
	    set zip = "$JOB/$class.zip"
	    if ($?DEBUG) echo `date` "$0:t $$ -- creating ($zip) from split ($s)" >>&! $LOGTO
	    foreach id ( `cat "$s"` )
		if ($?ids) then
		    set ids = "$ids"',"'"$id"'"'
		else
		    set ids = '["'"$id"'"'
		endif
		# slow but complete
		find $AAHDIR/label/$device -name "$id"."$ext" -print | xargs -I % zip -q -j -r -u "$zip" % >>&! $LOGTO
	    end
	    set ids = "$ids"']'
	    # if ($?DEBUG) echo `date` "$0:t $$ -- IDS: $ids" >>&! $LOGTO
	    rm -f "$s"
	    if (-s "$zip") then
		# put all results into temporary directory
		set base = "$JOB/$class"
		mkdir -p "$base"
		if ($?DEBUG) echo `date` "$0:t $$ -- splitting ($zip) into ($base)" >>&! $LOGTO
		zipsplit -b "$base/" -n $MAXZIPBYTES "$zip" >& /dev/null
		# success?
		if ($status == 0) then
		    # get all the zips created
		    set zips = ( `echo "$base/"*.zip` )
		    if ($#zips > 0) then
			if ($?DEBUG) echo `date` "$0:t $$ -- split into $#zips ZIP files ($zips)" >>&! $LOGTO
			@ i = 1
			foreach z ( $zips )
			    set b = "$JOB/$class.$sext.$i.zip"
			    if ($?DEBUG) echo `date` "$0:t $$ -- creating batch entry ($b)" >>&! $LOGTO
			    mv "$z" "$b"
			    if ($?batch) then
				set batch = "$batch"',"'"$b"'"'
			    else
				set batch = '["'"$b"'"'
			    endif
			    @ i++
			end
			set batch = "$batch"']'
			# if ($?DEBUG) echo `date` "$0:t $$ -- BATCH: $batch" >>&! $LOGTO
		    else
			echo `date` "$0:t $$ -- NO ZIPS" >>&! $LOGTO
			exit
		    endif
		else
		    echo `date` "$0:t $$ -- ZIPSPLIT failure" >>&! $LOGTO
		    exit
		endif
		rm -fr "$base"
	    else
		echo `date` "$0:t $$ -- ZIP failure" >>&! $LOGTO
		exit
	    endif
	    if ($?zips) then
		unset zips
	    endif
	    rm -f "$zip"
	    set splits = "$splits""$batch","$ids"
	    # if ($?DEBUG) echo `date` "$0:t $$ -- SPLITS: $splits" >>&! $LOGTO
	    unset batch
	    unset ids
	end
	set splits = "$splits"']'
    else
	echo `date` "$0:t $$ -- NO SPLIT" >>&! $LOGTO
        unset splits
    endif
    if ($?splits) then
	set sets = "$sets""$splits"
	# if ($?DEBUG) echo `date` "$0:t $$ -- SETS: $sets" >>&! $LOGTO
    endif
    unset splits
end
# SETS
if ($?sets) then
    set job = "$job""$sets"'}]}'
else 
    set job = "$job"'}]}'
else
    # NO SETS?
    if ($?DEBUG) echo `date` "$0:t $$ !! NO SETS" >>&! $LOGTO
endif
if ($?job) then
    # store result
    echo "$job" >! "$JOB/job.json"
else
    if ($?DEBUG) echo `date` "$0:t $$ !! NO JOB" >>&! $LOGTO
    exit
endif

# all done
rm -f "$JOB.$$"

##
## STEP 3 - EXECUTING TRAINING JOBS
##

training:

if ($?DEBUG) echo `date` "$0:t $$ -- TRAIN" >>&! $LOGTO

set TRAIN = "$TMP/$APP-$API-$QUERY_STRING.$DATE.job/train"
set INPROGRESS = ( `echo "$TRAIN".*` )
if ($#INPROGRESS) then
    if ($?DEBUG) echo `date` "$0:t $$ -- training in-progress ($INPROGRESS)" >>&! $LOGTO
    goto done
else if (-d "$TRAIN") then
    if ($?DEBUG) echo `date` "$0:t $$ -- existing training ($TRAIN)" >>&! $LOGTO
    goto training
endif
set old = ( `echo "$TMP/$APP-$API-$QUERY_STRING.$DATE.job/train".*.json` )
if ($#old > 0) then
    if ($?DEBUG) echo `date` "$0:t $$ -- NOT removing old ($old)" >>&! $LOGTO
    # rm -fr $old
endif

# check requisites
set INVENTORY = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
set JOB = "$TMP/$APP-$API-$QUERY_STRING.$DATE.job"
if ((-s "$INVENTORY") && (-d "$JOB")) then
    if ($?DEBUG) echo `date` "$0:t $$ -- found inventory ($INVENTORY) and job ($JOB)" >>&! $LOGTO
else 
    if ($?DEBUG) echo `date` "$0:t $$ -- no inventory ($INVENTORY) or job ($JOB)" >>&! $LOGTO
    goto cleanup
endif

# get parameters
set device = ( `jq '.name' "$INVENTORY" | sed 's/"//g'` )

if ($?DEBUG) echo `date` "$0:t $$ -- device ($device)" >>&! $LOGTO

#
# GET EXISTING CLASSIFIERS FROM WATSON_VR
#

if ($?model) then
    if ($?DEBUG) echo `date` "$0:t $$ -- searching for classifier by ID" >>&! $LOGTO
    set classifiers = ( `curl -q -s -L "$TU/$verid/classifiers?api_key=$api_key&version=$vdate" | jq '[.classifiers[]|select(.classifier_id=="'"$model"'")]'` )
    if ($?DEBUG) echo `date` "$0:t $$ -- got ($classifiers) for $model on $device" >>&! $LOGTO
else if ($?device) then
    if ($?DEBUG) echo `date` "$0:t $$ -- searching for classifier by device" >>&! $LOGTO
    set classifiers = ( `curl -q -s -L "$TU/$verid/classifiers?api_key=$api_key&version=$vdate" | jq '[.classifiers[]|select(.name=="'"$device"'")]'` )
    set model = ( `echo "$classifiers" | jq '.[].classifier_id' | sed 's/"//g'` )
    if ($#model > 0) then
      if ($?DEBUG) echo `date` "$0:t $$ -- using $model[1] from $device for classifier by device" >>&! $LOGTO
      set model = $model[1]
    else
      unset model
    endif
endif

if ($?classifiers) then
    if ($?DEBUG) echo `date` "$0:t $$ -- CLASSIFIERS ($classifiers)" >>&! $LOGTO
else
    if ($?DEBUG) echo `date` "$0:t $$ -- NO EXISTING CLASSIFIERS" >>&! $LOGTO
    set classifiers = ()
endif

#
# TEST IF MODEL READY FOR TRAINING
#
# Can only train a classifier in "ready" state
#

if ($#classifiers > 0 && $?model) then
    set ready = ( `echo "$classifiers" | jq '[.[]|select(.status=="ready")]'` )
    set cids = `echo "$classifiers" | jq '.[]|select(.classifier_id=="'"$model"'").classifier_id' | sed 's/"//g'`
    if ($#cids > 0) then
      foreach cid ( $cids )
	if ($cid == "$model") then
	    if ($?DEBUG) echo `date` "$0:t $$ -- matched specified classifier ($model)" >>&! $LOGTO
	    if ($?delete) then
		if ($?DEBUG) echo `date` "$0:t $$ -- deleting classifier id ($cid)" >>&! $LOGTO
		curl -s -q -X DELETE "$TU/$verid/classifiers/$cid?api_key=$api_key&version=$vdate"
		unset model
	    else
		if ($?DEBUG) echo `date` "$0:t $$ -- getting details for classifier id ($cid)" >>&! $LOGTO
		set detail = ( `curl -s -q "$TU/$verid/classifiers/$cid?api_key=$api_key&version=$vdate" | jq '.'` )
	    endif
	    break
	endif
      end
      # test if model matched (and not deleted)
      if ($?model) then
        if ($cid != "$model") then
	  if ($?DEBUG) echo `date` "$0:t $$ -- no classifier ($model) for device ($device) is ready" >>&! $LOGTO
	  set training = ( `echo "$classifiers" | jq '[.[]|select(.status=="training")]'` )
	  set cids = ( `echo $training | jq '.[]|select(.name=="'"$model"'").classifier_id' | sed 's/"//g'` )
	  if ($?DEBUG) echo `date` "$0:t $$ -- classifiers ($cids) are in training" >>&! $LOGTO
	  foreach cid ( $cids )
	      if ($cid == "$model") then
		  if ($?DEBUG) echo `date` "$0:t $$ -- classifier id ($cid) in training" >>&! $LOGTO
		  goto cleanup
	      endif
	  end
	  # no matching model
	  unset model
	endif
      endif
    endif
endif

#
# GET CLASSES (OLD, NET, NEGATIVE)
#

if ($?detail) then
    if ($?DEBUG) echo `date` "$0:t $$ -- model details ($detail)" >>&! $LOGTO
    set oldclasses = ( `echo "$detail" | jq '.classes[].class' | sed 's/"//g'` )
else
    unset oldclasses
endif

set newclasses = ( `jq '.images[].class' "$INVENTORY" | sed 's/"//g'` )
set notags = ( `jq '.negative' "$INVENTORY" | sed 's/"//g'` )

set net = ()
foreach nc ( $newclasses )
    if ($?oldclasses && $nc != "$notags") then
	foreach oc ( $oldclasses )
	    if ($nc == "$oc") break
	end
	if ($nc != "$oc") then
	    set net = ( $net $nc )
	endif
    else if ($nc != "$notags") then
	set net = ( $net $nc )
    endif
end 

if ($?DEBUG) echo `date` "$0:t $$ -- OLD ($?oldclasses) NEW ($net) NEGATIVE ($notags) +++" >>&! $LOGTO

#
# RUN TRAINING JOBS
#

set positive = ( `jq '.images|sort_by(.count)[]|select(.class!="'$notags'")|.class' "$INVENTORY" | sed 's/"//g'` )
set negative = ( `jq '.images|sort_by(.count)[]|select(.class=="'$notags'")|.class' "$INVENTORY" | sed 's/"//g'` )

if ($?DEBUG) echo `date` "$0:t $$ -- POSITIVE ($positive) NEGATIVE ($negative) +++" >>&! $LOGTO

# the zero'th set is the training example ZIPs; corresponding +1 set are the IDs used in those ZIPs
set negatives = ( `jq '.jobs[]|select(.class=="'"$notags"'").sets[0][]' "$JOB/job.json" | sed 's/"//g'` )

@ ttime = 0
@ h = 1
@ j = 1
while ($h <= $#positive) 
  set p = $positive[$h]
  # first (0) set is training
  set positives = ( `jq '.jobs[]|select(.class=="'"$p"'").sets[0][]' "$JOB/job.json" | sed 's/"//g'` )
  @ i = 1
  while ($i <= $#positives) 
    set job = "$JOB/$p.$$.json"
    if ($?negatives) then
      set examples = ( -F "$p""_positive_examples=@$positives[$i]" -F "negative_examples=@$negatives[$j]" )
    else if ($?model) then
      set examples = ( -F "$p""_positive_examples=@$positives[$i]" )
    else
      echo `date` "$0:t $$ ** INSUFFICIENT EXAMPLE SETS **"
      exit
    endif
again:
    # timer start
    @ start = `date +%s`
    # run training 
    if ($?model) then
      if ($?DEBUG) echo `date` "$0:t $$ -- RETRAIN $model ($examples)" >>&! $LOGTO
      curl -f -s -q -S -L "$TU/$verid/classifiers/$model?api_key=$api_key&version=$vdate" -o $job $examples >>&! $LOGTO
    else
      if ($?DEBUG) echo `date` "$0:t $$ -- CREATE $device ($examples)" >>&! $LOGTO
      curl -f -s -q -S -L "$TU/$verid/classifiers?api_key=$api_key&version=$vdate" -F "name=$device" -o $job $examples >>&! $LOGTO
    endif
    set cstatus = $status
    # check status
    if ($cstatus != 0) then
      echo `date` "$0:t $$ ** FAILURE ($cstatus)" >>&! $LOGTO
      if (-s "$job") then
	  echo `date` "$0:t $$ ** " `cat "$job"` >>&! $LOGTO
	  # check result code
	  set code = `jq '.code' "$job" | sed 's/"//g'` 
	  set message = `jq '.error' "$job" | sed 's/"//g'`
	  if ($?DEBUG) echo `date` "$0:t $$ -- FAILURE ($message)" >>&! $LOGTO
      endif
      rm -f "$job"
      goto next
    else if (! -s "$job") then
      echo `date` "$0:t $$ ** no output ($job)" >>&! $LOGTO
      goto again
    else 
      # check result code
      set code = `jq '.code' "$job" | sed 's/"//g'` 
      if ($code == 400) then
	set message = `jq '.error' "$job" | sed 's/"//g'`
	if ($?DEBUG) echo `date` "$0:t $$ -- FAILURE ($message)" >>&! $LOGTO
	goto next
      endif
      # get classifier id to check on progress
      set cid = `jq '.classifier_id' "$job" | sed 's/"//g'`
      set sts = `jq '.status' "$job" | sed 's/"//g'`
      if ($#cid > 0 && $cid != "null" && $sts != "error") then
	if ($?DEBUG) echo `date` "$0:t $$ -- LEARNING ($cid) status ($sts)" >>&! $LOGTO
	set model = "$cid"
      else
	echo -n `date` "$0:t $$ ** FAILURE ($cid) ($sts) ($job)" >>&! $LOGTO
	goto next
      endif
    endif
    rm -f "$job"
    @ elapsed = `date +%s` - $start
    if ($?DEBUG) echo -n `date` "$0:t $$ -- LOAD COMPLETE ($elapsed) WAITING "
    while ($sts != "ready") 
	set detail = ( `curl -s -q -L "$TU/$verid/classifiers/$model?api_key=$api_key&version=$vdate" | jq '.'` )
	set sts = ( `echo "$detail" | jq '.status' | sed 's/"//g'` )
	if ($sts != "null") then
	  if ($?DEBUG) echo -n "."
	else
	  if ($?DEBUG) echo -n "!"
	endif
        sleep 10
    end
    @ elapsed = `date +%s` - $start
    if ($?DEBUG) echo " ($elapsed seconds)"
    set model = "$cid"
    @ ttime += $elapsed
next:
    # increment to next batch
    @ i++
    @ j++
    if ($?negatives) then
      if ($j <= $#negatives) then
	set negatives = ( $negatives[$j-] )
      else
	unset negatives
      endif
    endif
  end
  @ h++
end

if ($?DEBUG) echo `date` "$0:t $$ -- COMPLETE $DATE ($model) time ($ttime) ($detail)" >>&! $LOGTO

#
# UPDATE INVENTORY INDICATING SUCCESS
#

update:

# get jobs batches
set batches = ( `jq '.' "$JOB/job.json"` )
set created = `echo "$detail" | jq '.created' | sed 's/"//g'`
set created = `date -j -f '%Y-%m-%dT%H:%M:%S' +%s $created:r`
set retrained = `echo "$detail" | jq '.retrained' | sed 's/"//g'`
set retrained = `date -j -f '%Y-%m-%dT%H:%M:%S' +%s $retrained:r`
set classes = `echo "$batches" | jq '[.jobs[].class]'`
# update INVENTORY with resulting model
cat "$INVENTORY" \
    | jq '.classes='"$classes" \
    | jq '.created="'$created'"' \
    | jq '.retrained="'$retrained'"' \
    | jq '.sets='"$batches" \
    | jq '.date="'"$DATE"'"' \
    | jq '.model="'"$model"'"' \
    | jq '.detail='"$detail" \
    >! "$INVENTORY.$$"
if (-s "$INVENTORY.$$") then
  mv -f "$INVENTORY.$$" "$INVENTORY"
else
  echo `date` "$0:t $$ -- FAILURE UPDATING INVENTORY WITH MODEL AND DETAILS" >>&! $LOGTO
  exit
endif

#
# update Cloudant
#

if ($?CLOUDANT_OFF == 0 && $?CU && $?device) then
    if ($?DEBUG) echo `date` "$0:t $$ -- test if device exists ($device-$API)" >>&! $LOGTO
    set devdb = `curl -s -q -X GET "$CU/$device-$API" | jq '.db_name'`
    if ( "$devdb" == "null" ) then
        if ($?DEBUG) echo `date` "$0:t $$ -- creating device $CU/$device-$API" >>&! $LOGTO
        # create device
        set devdb = `curl -s -q -X PUT "$CU/$device-$API" | jq '.ok'`
        # test for success
        if ( "$devdb" != "true" ) then
            # failure
            if ($?DEBUG) echo `date` "$0:t $$ -- failure creating Cloudant database ($device-$API)" >>&! $LOGTO
            setenv CLOUDANT_OFF TRUE
        else
            if ($?DEBUG) echo `date` "$0:t $$ -- success creating device $device-$API" >>&! $LOGTO
        endif
    endif
    if ( $?CLOUDANT_OFF == 0 ) then
        curl -s -q -o "$INVENTORY.$$" "$CU/$device-$API/$model" >>&! $LOGTO
        if (-s "$INVENTORY.$$") then
            set doc = ( `cat "$INVENTORY.$$" | jq -r '._id,._rev'` )
            if ($#doc == 2 && $doc[1] == $model && $doc[2] != "") then
                set rev = $doc[2]
                if ($?DEBUG) echo `date` "$0:t $$ -- deleting old output ($rev)" >>&! $LOGTO
                curl -s -q -X DELETE "$CU/$device-$API/$model?rev=$rev" >>&! $LOGTO
            endif
        else
            if ($?DEBUG) echo `date` "$0:t $$ -- no old output to delete" >>&! $LOGTO
        endif
	rm -f "$INVENTORY.$$"
        if ($?DEBUG) echo `date` "$0:t $$ -- storing new output" >>&! $LOGTO
        curl -s -q -H "Content-type: application/json" -X PUT "$CU/$device-$API/$model" -d "@$INVENTORY" >>&! $LOGTO
        if ($status == 0) then
            if ($?DEBUG) echo `date` "$0:t $$ -- success storing new output" >>&! $LOGTO
        else
            if ($?DEBUG) echo `date` "$0:t $$ -- failure storing new output" >>&! $LOGTO
        endif
    else
        if ($?DEBUG) echo `date` "$0:t $$ -- Cloudant OFF ($device-$API)" >>&! $LOGTO
    endif
else
    if ($?DEBUG) echo `date` "$0:t $$ -- no Cloudant update" >>&! $LOGTO
endif

cleanup:

rm -f "$TMP/$APP-$API-$QUERY_STRING.$DATE.json".*

done:
  echo `date` "$0:t $$ -- FINISH ($*)"
