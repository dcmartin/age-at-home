#!/bin/csh -fb

# uncomment for production
setenv DEBUG true
# setenv DELETE_CONTAINER true
setenv DELETE_OLD_MODELS true
setenv SWIFT_ARGS "--verbose"

###
### PREREQUISITE CHECK
###

$0:h/mkreqs.csh >& /dev/stderr

##
## SWIFT REQUIRED
##

# check OpenStack Swift client
set version = ( `swift --version |& awk '{ print $1 }'` )
if ( "$version" =~ "python*" ) then
  if ($?DEBUG) echo "$0:t $$ -- [debug] OpenStack Swift installed ($version)"
else
  echo "INSTALLING OpenStack Swift client using pip; system may prompt for password"
  pip3 install python-swiftclient >& /dev/null
  pip3 install python-keystoneclient >& /dev/null
  echo "DONE installing Swift client"
endif

###
### START 
###

if ($?DEBUG) echo "$0:t $$ -- [debug] $0 $argv ($#argv)" >& /dev/stderr

# ARG directory (content to be uploaded)
if ($#argv > 0) then
  set dlaasjob = "$argv[1]"
endif
if ($?dlaasjob == 0) then
  echo "$0:t $$ -- [ERROR] <dlaas_job>.json" >& /dev/stderr
  exit
endif
if ($?DEBUG) echo "$0:t $$ -- [ARG] <dlaas_job>.json ($dlaasjob)" >& /dev/stderr

if (! -e "$dlaasjob.json") then
  echo "$0:t $$ -- [ERROR] cannot locate $dlaasjob.json" >& /dev/stderr
  exit
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

# get SWIFT status information
set stat = "/tmp/$0:t.$$.stat"
swift $SWIFT_ARGS \
  --os-user-id="$userId" \
  --os-password="$password" \
  --os-project-id="$projectId" \
  --os-auth-url="$auth_url/v3" \
  --os-region-name="$region" \
  stat >! "$stat"

# conver to JSON for use
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
set thisdir = ( `jq -r '.thisdir' "$dlaasjob.json"` )

# check if source exists
if (! -e "$thisdir" || ! -d "$thisdir") then
  echo "$0:t $$ -- [ERROR] cannot locate $thisdir"
  exit 1
endif

# extract authorization token and storage URL from JSON processed from curl

set auth = `echo "$json" | jq -r '.AuthToken'`
set sturl = `echo "$json" | jq -r '.StorageURL'`

# get existing containers
set containers = ( `swift $SWIFT_ARGS --os-auth-token "$auth" --os-storage-url "$sturl" list | sed 's/ /%20/g'` )

# check iff container exists; delete it when specified
unset existing
if ($?containers) then
  if ($#containers) then
    echo "$0:t $$ -- [debug] EXISTING CONTAINERS: $containers" >& /dev/stderr
    foreach c ( $containers )
      if ("$c" == "$dlaasjob") then
        if ($?DELETE_CONTAINER) then
          echo "$0:t $$ -- [debug] deleting existing container $c" >& /dev/stderr
          swift $SWIFT_ARGS --os-auth-token "$auth" --os-storage-url "$sturl" delete `echo "$c" | sed 's/%20/ /g'` >& /dev/null
        else
          set existing = "$c"
          set n = ( `echo "$c" | sed 's/%20/ /g'` )
          set contents = ( `swift $SWIFT_ARGS --os-auth-token "$auth" --os-storage-url "$sturl" list "$n"` )
          if ($?contents == 0) set contents = ()
        endif
      else
        if ($?DEBUG) echo "$0:t $$ -- [debug] $c" >& /dev/stderr
      endif
    end
  else
    echo "$0:t $$ -- [debug] zero containers found" >& /dev/stderr
  endif
else
  echo "$0:t $$ -- [INFO] no containers exist" >& /dev/stderr
endif

## MAKE NEW CONTAINER
if ($?existing) then
  echo "$0:t $$ -- [WARN] existing container: $dlaasjob; contents: [$contents]" >& /dev/stderr
else
  echo "$0:t $$ -- [INFO] making container: $dlaasjob" >& /dev/stderr
  swift $SWIFT_ARGS --os-auth-token "$auth" --os-storage-url "$sturl" post `echo "$dlaasjob" | sed 's/%20/ /g'` >& /dev/null
endif

##
## SYNCHRONIZE MODEL FILES
##

# identify training files from configuration
set files = ( `jq -r '.sample.maps[]?.file,.sample.data[]?.file,.model.pretrain.weights?,.model.training.network?,.model.training.solver?,.model.training.median?' "$dlaasjob.json" | egrep -v "null"` )
if ($#files == 0) then
  echo "$0:t $$ -- [ERROR] no training files" >& /dev/stderr
  exit 1
else
  if ($?DEBUG) echo "$0:t $$ -- [debug] training files [$files]" >& /dev/stderr
endif

# identify model from configuration results
set model_id = ( `jq -r '.model.results.model_id' "$dlaasjob.json"` )
if ($#model_id == 0 || "$model_id" == "null") then
  if ($?DEBUG) echo "$0:t $$ -- [debug] no model" >& /dev/stderr
  unset model_id
endif

# jump to source
pushd "$thisdir"

## UPLOAD training files
foreach file ( $files )
  set found = false
  if (-e "$file") then
    foreach c ( $contents )
      if ((-d "$file" && "$c:h" == "$file") || (! -d "$file" && "$c" == "$file")) then
        set found = true
        break
      endif
    end
    if ($found != true) then
      if ($?DEBUG) echo "$0:t $$ -- [debug] UPLOADING $file " `du -k "$file" | awk '{ print $1 }'` "Kbytes" >& /dev/stderr
      swift $SWIFT_ARGS --os-auth-token "$auth" --os-storage-url "$sturl" upload `echo "$dlaasjob" | sed 's/%20/ /g'` "$file"
    else
      if ($?DEBUG) echo "$0:t $$ -- [debug] $file has been uploaded" >& /dev/stderr
    endif
  else
    echo "$0:t $$ -- [ERROR] $file does not exists" >& /dev/stderr
    exit 1
  endif
end

## DOWNLOAD result files
if ($?contents && $?model_id) then
  foreach c ( $contents )
    # results match model identifier
    if ( "$c" =~ "$model_id/*" ) then
      if ( ! -e "$c" ) then
        mkdir -p "$c:h"
        swift $SWIFT_ARGS --os-auth-token "$auth" --os-storage-url "$sturl" download `echo "$dlaasjob" | sed 's/%20/ /g'` "$c" >& /dev/null
        if ($?DEBUG) echo "$0:t $$ -- [debug] DOWNLOADED $c " `du -k "$c " | awk '{ print $1 }'` " Kbytes" >& /dev/stderr
        if ($?output) then
          set output = ( $output "$c" )
        else
          set output = ( "$c" )
        endif
      else
        if ($?DEBUG) echo "$0:t $$ -- [debug] JOB $c synchronized" >& /dev/stderr
      endif
    else if ("$c" =~ "training-*") then
      if ($?DEBUG) echo "$0:t $$ -- [debug] OLD $c exists" >& /dev/stderr
      if ($?oldmodels) then
        set oldmodels = ( $oldmodels "$c" )
      else
        set oldmodels = ( "$c" )
      endif
    else
      if ($?DEBUG) echo "$0:t $$ -- [debug] $c exists" >& /dev/stderr
    endif
  end
endif

# back from source
popd
# update files
if ($?output) then
  set files = ( $files $output )
endif

## DELETE OLD MODELS (or not)
if ($?oldmodels && $?DELETE_OLD_MODELS) then
  foreach c ( $oldmodels )
    echo "$0:t $$ -- [INFO] DELETING OLD MODEL $c" >& /dev/stderr
    swift $SWIFT_ARGS --os-auth-token "$auth" --os-storage-url "$sturl" delete `echo "$dlaasjob" | sed 's/%20/ /g'` "$c" >& /dev/null
  end
endif

###
### DONE
###

# files list to JSON array elements
if ($#files) then
  set files = `echo "$files" | sed 's/\([^ ]*\)/"\1",/g' | sed 's/\(.*\),$/\1/'`
else
  set files = ""
endif
# storage documentation
set storage = '{"type":"bluemix_objectstore","container":"'"$dlaasjob"'","auth_url":"'"$auth_url"'/v3","user_name":"'"$username"'","password":"'"$password"'","domain_name":"'"$domainName"'","region":"'"$region"'","project_id":"'"$projectId"'","files":['"$files"']}'
# update storage
jq '.storage='"$storage" "$dlaasjob.json" >! /tmp/$0:t.$$.json
# save result and return
jq '.' /tmp/$0:t.$$.json | tee "$dlaasjob.json"
rm -f /tmp/$0:t.$$.json
