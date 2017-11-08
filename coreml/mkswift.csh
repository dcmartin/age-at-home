#!/bin/csh -fb

# uncomment for production
setenv DEBUG true
# setenv DELETE true
setenv VERBOSE "--verbose"

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
swift $VERBOSE \
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
set containers = ( `swift $VERBOSE --os-auth-token "$auth" --os-storage-url "$sturl" list | sed 's/ /%20/g'` )

# check iff container exists; delete it when specified
unset existing
if ($?containers) then
  if ($#containers) then
    echo "$0:t $$ -- [debug] EXISTING CONTAINERS: $containers" >& /dev/stderr
    foreach c ( $containers )
      if ($?DELETE && ("$c" == "$dlaasjob" || "$c" == "$dlaasjob-output")) then
        echo "$0:t $$ -- [debug] deleting existing container $c" >& /dev/stderr
        swift $VERBOSE --os-auth-token "$auth" --os-storage-url "$sturl" delete `echo "$c" | sed 's/%20/ /g'` >& /dev/stderr
        continue
      else if ("$c" == "$dlaasjob") then
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
  echo "$0:t $$ -- [WARN] existing container: $dlaasjob; contents: [$contents]" >& /dev/stderr
else
  echo "$0:t $$ -- [INFO] making container: $dlaasjob" >& /dev/stderr
  swift $VERBOSE --os-auth-token "$auth" --os-storage-url "$sturl" post `echo "$dlaasjob" | sed 's/%20/ /g'` >& /dev/stderr
endif

##
## STORE SPECIFIED FILES (in thisdir)
##

set files = ( `jq -r '.maps[]?.file,.data[]?.file,.model.pretrain.weights?,.model.training.median?' "$dlaasjob.json"` )
if ($#files == 0) then
  echo "$0:t $$ -- [WARN] no files" >& /dev/stderr
endif

# jump to source
pushd "$thisdir"

foreach file ( $files )
  if ("$file" == "null") continue
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
      swift $VERBOSE --os-auth-token "$auth" --os-storage-url "$sturl" upload `echo "$dlaasjob" | sed 's/%20/ /g'` "$file"
    else
      if ($?DEBUG) echo "$0:t $$ -- [debug] $file exists" >& /dev/stderr
    endif
  else
    echo "$0:t $$ -- [ERROR] NO FILE: $file" >& /dev/stderr
  endif
end

# back from source
popd

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
# set storage = '{"type":"bluemix_objectstore","container":"'"$dlaasjob"'","auth_url":"'"$auth_url"'/v3","user_name":"'"$userId"'","password":"'"$password"'","domain_name":"'"$domainName"'","region":"'"$region"'","project_id":"'"$projectId"'","files":['"$files"']}'
set storage = '{"type":"bluemix_objectstore","container":"'"$dlaasjob"'","auth_url":"'"$auth_url"'/v3","user_name":"'"$username"'","password":"'"$password"'","domain_name":"'"$domainName"'","region":"'"$region"'","project_id":"'"$projectId"'","files":['"$files"']}'
# update storage
jq '.storage='"$storage" "$dlaasjob.json" >! /tmp/$0:t.$$.json
# save result and return
jq '.' /tmp/$0:t.$$.json | tee "$dlaasjob.json"

