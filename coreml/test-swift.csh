#!/bin/csh -fb

#
# TEST IF PRE-REQUISITES ARE INSTALLED
#

command -v jq >& /dev/null
if ($status != 0) then
  echo "[ERROR] Please install jq first; try using http://brew.sh (brew install jq)"
  exit 1
endif

command -v curl >& /dev/null
if ($status != 0) then
  echo "[ERROR] Please install curl first; try using http://brew.sh (brew install curl)"
  exit 1
endif

# check OpenStack Swift client
set version = ( `swift --version |& awk '{ print $1 }'` )
if ( "$version" =~ "python*" ) then
  echo "Swift installed ($version)"
else
  echo "INSTALLING Swift client using pip; system may prompt for password"
  sudo easy_install pip >& /dev/null
  sudo pip install python-swiftclient >& /dev/null
  sudo pip install python-keystoneclient >& /dev/null
  echo "DONE installing Swift client""
endif

#
# FIND CREDENTIALS
#

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
  echo "No credentials found: $CREDENTIALS"
  exit 1
endif

# BASE OPENSTACK VERSION; NOT IN CREDENTIALS
setenv OS_IDENTITY_API_VERSION 3
setenv OS_AUTH_VERSION 3

# EXERCISE SWIFT CONNECT WITH 'stat' COMMAND
set stat = "/tmp/$0:t.$$.stat"
swift --verbose \
  --os-user-id="$userId" \
  --os-password="$password" \
  --os-project-id="$projectId" \
  --os-auth-url="$auth_url/v3" \
  --os-region-name="$region" \
  stat >! "$stat"

if (-e "$stat") then
  echo "STAT: successful ($stat)"
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
  exit 1
endif

if ($?json) then
  echo "STAT: processed into JSON:"
  echo "$json" | jq '.'
else
  echo "FAIL: no JSON"
  exit 1
endif

if ($#argv >= 1) then
  set file = "$argv[1]"
endif
if ($?file == 0) set file = "/usr/share/dict/words"

if (! -e "$file") then
  echo "ERROR: no such input ($file)"
  exit 1
endif

# extract authorization token and storage URL from JSON processed from curl
set auth = `echo "$json" | jq -r '.AuthToken'`
set sturl = `echo "$json" | jq -r '.StorageURL'`

echo "TESTING: $file " `wc "$file"`


  echo "  EXISTING CONTAINERS: "
  swift --verbose \
    --os-auth-token "$auth" \
    --os-storage-url "$sturl" \
   list

  echo "  MAKE NEW CONTAINER: $0:t.$$"
  swift --verbose \
    --os-auth-token "$auth" \
    --os-storage-url "$sturl" \
   post "$0:t.$$" 

onintr cleanup

  if (-e "$file") then
    echo "  UPLOAD: $0:t.$$ $file"
    swift --verbose \
      --os-auth-token "$auth" \
      --os-storage-url "$sturl" \
     upload "$0:t.$$" "$file"
  else
     echo "NO FILE: $file"
  endif

cleanup:

  set containers = ( `swift --verbose \
    --os-auth-token "$auth" \
    --os-storage-url "$sturl" \
   list` )

  foreach c ( $containers )

    echo "  LIST CONTAINER: $c"
    swift --verbose \
      --os-auth-token "$auth" \
      --os-storage-url "$sturl" \
     list $c

    if ("$c" == "$0:t.$$") then
      echo "  DELETE CONTAINER: $c"
      swift --verbose \
        --os-auth-token "$auth" \
        --os-storage-url "$sturl" \
       delete $c
    endif
  end

  echo "  RESIDUAL CONTAINERS: "
  swift --verbose \
    --os-auth-token "$auth" \
    --os-storage-url "$sturl" \
   list

endif
