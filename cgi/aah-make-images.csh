#!/bin/tcsh -b
setenv APP "aah"
setenv API "images"

# debug on/off
setenv DEBUG true
# setenv VERBOSE true

# environment
if ($?LAN == 0) setenv LAN "192.168.1"
if ($?DIGITS == 0) setenv DIGITS "$LAN".30
if ($?TMP == 0) setenv TMP "/tmp"
if ($?AAHDIR == 0) setenv AAHDIR "/var/lib/age-at-home"
if ($?CREDENTIALS == 0) setenv CREDENTIALS /usr/local/etc
if ($?LOGTO == 0) setenv LOGTO $TMP/$APP.log

###
### dateutils REQUIRED
###

if ( -e /usr/bin/dateutils.dconv ) then
   set dateconv = /usr/bin/dateutils.dconv
else if ( -e /usr/local/bin/dateconv ) then
   set dateconv = /usr/local/bin/dateconv
else
  echo "No date converter; install dateutils" >& /dev/stderr
  exit 1
endif

# CAMERA IMAGE DEFAULTS
if ($?CAMERA_MODEL_TRANDFORM == 0) setenv CAMERA_MODEL_TRANSFORM "CROP"
if ($?CAMERA_IMAGE_WIDTH == 0) setenv CAMERA_IMAGE_WIDTH 640
if ($?CAMERA_IMAGE_HEIGHT == 0) setenv CAMERA_IMAGE_HEIGHT 480

# UPDATE INTERVAL
if ($?TTL == 0) set TTL = 60
if ($?SECONDS == 0) set SECONDS = `date "+%s"`
if ($?DATE == 0) set DATE = `echo $SECONDS \/ $TTL \* $TTL | /usr/bin/bc`

# standardize QUERY_STRING
if ($?QUERY_STRING) then
    set device = `echo "$QUERY_STRING" | sed 's/.*device=\([^&]*\).*/\1/'`
    if ($device == "$QUERY_STRING") unset device
    set force = `echo "$QUERY_STRING" | sed 's/.*force=\([^&]*\).*/\1/'`
    if ($force == "$QUERY_STRING") unset force
endif
setenv QUERY_STRING "device=$device"

##
## start
##
if ($?DEBUG) echo `date` "$0:t $$ -- $device -- START" >>&! $LOGTO

##
## single threaded by OUTPUT
##

# OUTPUT target
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
set INPROGRESS = ( `echo "$OUTPUT:r:r".*` )
if ($#INPROGRESS) then
    foreach ip ( $INPROGRESS )
      set pid = $ip:e
      set eid = ( `ps axw | awk '{ print $1 }' | egrep "$pid"` )
      if ($pid == $eid) then
        if ($?DEBUG) echo `date` "$0:t $$ -- PID $pid in-progress ($QUERY_STRING)" >>&! $LOGTO
        goto done
      else
        if ($?VERBOSE) echo `date` "$0:t $$ -- removing $ip" >>&! $LOGTO
        rm -f "$ip"
      endif
    end
    if ($?VERBOSE) echo `date` "$0:t $$ -- NO PROCESSES FOUND ($QUERY_STRING)" >>&! $LOGTO
else
    if ($?VERBOSE) echo `date` "$0:t $$ -- NO EXISTING $0:t ($QUERY_STRING)" >>&! $LOGTO
endif
# remove all prior traces
rm -f "$OUTPUT:r:r".*
# cleanup if interrupted
onintr cleanup
# begin
touch "$OUTPUT".$$

##
## ACCESS CLOUDANT
##
if ($?CLOUDANT_URL) then
  set CU = $CLOUDANT_URL
else if (-s $CREDENTIALS/.cloudant_url) then
  set cc = ( `cat $CREDENTIALS/.cloudant_url` )
  if ($#cc > 0) set CU = $cc[1]
  if ($#cc > 1) set CN = $cc[2]
  if ($#cc > 2) set CP = $cc[3]
  if ($?CP && $?CN && $?CU) then
    set CU = 'https://'"$CN"':'"$CP"'@'"$CU"
  else if ($?CU) then
    set CU = "https://$CU"
  endif
else
  echo `date` "$0:t $$ -- FAILURE: no Cloudant credentials" >>&! $LOGTO
  goto done
endif

##
## ACCESS FTP
##
if ($?FTP_URL) then
  set FTP = $FTP_URL
else if (-s $CREDENTIALS/.ftp_url) then
  set cc = ( `cat $CREDENTIALS/.ftp_url` )
  if ($#cc > 0) set CN = $cc[1]
  if ($#cc > 1) set CP = $cc[2]
  if ($?CP && $?CN) then
    set FTP = 'ftp://'"$CN"':'"$CP"
  else
    set FTP = "ftp://ftp:ftp"
  endif
else
  echo `date` "$0:t $$ -- FAILURE: no FTP credentials" >>&! $LOGTO
  goto done
endif

#
# CREATE <device>-images DATABASE 
#
if ($?CU && $?device) then
  set dd = `curl -s -q -f -L -X GET "$CU/$device-$API" | jq -r '.db_name'`
  if ( $#dd == 0 || $dd == "null" ) then
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- no existing database: $API" >>&! $LOGTO
    # create device
    set dd = `curl -s -q -f -L -X PUT "$CU/$device-$API" | jq '.ok'`
    # test for success
    if ( "$dd" != "true" ) then
      # failure
      if ($?DEBUG) echo `date` "$0:t $$ -- $device -- failure creating database: $API" >>&! $LOGTO
      goto done
    else
      if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- success creating database: $API" >>&! $LOGTO
      set since = 0
    endif
  endif
endif

# test if DB just created
if ($?since == 0) then
  # get last image processed
  set url = "$CU/$device-$API/_all_docs?include_docs=true&descending=true&limit=1"
  set out = "$TMP/$0:t.$$.json"
  curl -s -q -f -L "$url" -o "$out"
  if ($status == 22 || ! -s "$out") then
    if ($?DEBUG) echo `date` "$0:t $$ -- $device -- FATAL: failed to retrieve last image from $url" >>&! $LOGTO
    rm -f "$out"
    goto done
  endif
  set total_images = ( `jq -r '.total_rows' "$out"` )
  set since = ( `jq -r '.rows[].doc.date' "$out"` )
  if ($#since == 0 || $since == "null") then
    set since = 0
  else
    set since = "$since[$#since]"
  endif
  if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- last image retrieved at ($since)" >>&! $LOGTO
  rm -f "$out"
else
  if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- new DB; no prior images" >>&! $LOGTO
endif

# get IP address of this device
set url = "$HTTP_HOST/CGI/aah-devices.cgi?db=$device"
set ipaddr = ( `curl -s -q -f -L "$url" | jq -r ".ip_address"` )
if ($#ipaddr && $ipaddr != "null") then
  if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- found with address $ipaddr; last update $since" >>&! $LOGTO
else
  if ($?DEBUG) echo `date` "$0:t $$ -- $device -- FATAL -- not found ($url)" >>&! $LOGTO
  goto done
endif

###
### GET ALL UPDATES
###

set url = "$ipaddr/"
# retrieve updates (JSON) indicating image processed; reverse order to LIFO
set updates = ( `curl -s -q -f -L "$FTP"'@'"$url" | awk '{ print $9 }' | egrep "json" | sort -r` )
if ($#updates && $#updates != "null") then
  if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- found $#updates updates" >>&! $LOGTO
  @ i = 1
  while ($i <= $#updates)
    set updates[$i] = "$updates[$i]:r"
    @ i++
  end
else
  if ($?DEBUG) echo `date` "$0:t $$ -- $device -- FATAL: found no updates" >>&! $LOGTO
  goto done
endif

#
# PROCESS ALL UPDATES
#

# count images processed
@ nimage = 0
# process image formats
set formats = ( "jpg" "jpeg" )
foreach u ( $updates )

  # get relevant update 
  set url = "$CU/$device/$u"
  set out = "$TMP/$0:t.$device.$u.$$.json"
  /bin/rm -f "$out"
  curl -s -q -f -L "$url" -o "$out"
  if (! -s "$out") then
    rm -f "$out"
    if ($?DEBUG) echo `date` "$0:t $$ -- $device -- cannot find update $u; continuing..." >>&! $LOGTO
    continue
  endif

  # get update attributes
  set id = ( `jq -r '._id' "$out"` )
  set imagebox = ( `jq -r '.imagebox' "$out"` )
  set year = ( `jq -r '.year' "$out"` )
  set month = ( `jq -r '.month' "$out"` )
  set day = ( `jq -r '.day' "$out"` )
  set hour = ( `jq -r '.hour' "$out"` )
  set minute = ( `jq -r '.minute' "$out"` )
  set second = ( `jq -r '.second' "$out"` )

  # done w/ output
  rm -f "$out"

  # calculate date in seconds since epoch
  set date = `echo "$year/$month/$day $hour"':'"$month"':'"$second" | $dateconv -i "%Y/%M/%D %H:%M:%S" -f "%s"`

  # test imagebox
  if ($#imagebox == 0) set imagebox = "null"
  # test if all good
  if ($#id == 0 || $#imagebox == 0 || $#date == 0 || "$id" == "null" || "$date" == "null") then
    if ($?DEBUG) echo `date` "$0:t $$ -- $device -- WARNING: invalid or missing update $u from $url response;continuing..." >>&! $LOGTO
    continue
  else
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- $id ($imagebox)" >>&! $LOGTO
  endif

  # propose destination
  set image = "$AAHDIR/$device/$year/$month/$day/$id"

  # ensure destination
  /bin/mkdir -p "$image:h"
  # verify destination
  if (! -d "$image:h") then
    echo `date` "$0:t $$ -- $device -- FATAL: no directory ($image:h)" >>&! $LOGTO
    goto done
  endif

  unset fmts
  foreach ext ( $formats )
    # try to retreive iff DNE
    if (! -s "$image.$ext" && ! -l "$image.$ext") then
      set url = "ftp://$ipaddr/$id.$ext"
      set out = "$TMP/$0:t.$device.$id.$$.$ext"
      if ($?VERBOSE) echo `date` "$0:t $$ -- retrieving ($id) with $ipaddr" >>&! $LOGTO
      curl -s -q -L -u "ftp:ftp" "$url" -o "$out"
      if (! -s "$out") then
	rm -f "$out"
	if ($?DEBUG) echo `date` "$0:t $$ -- $device -- failed to retrieve $id image format $ext; continuing..." >>&! $LOGTO
	continue
      else
	if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- successful retrieve image $image format $ext" >>&! $LOGTO
	mv -f "$out" "$image.$ext"
      endif
    else
      if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- existing image ($id) format $ext" >>&! $LOGTO
    endif
    set attrs = ( `identify "$image.$ext" | awk '{ print $2, $4, $5, $6 }'` )
    if ($status == 0 && $#attrs) then
      if ($?fmts == 0) then
        set fmts = '['
      else
        set fmts = "$fmts"','
      endif
      set fmts = "$fmts"'{"ext":"'"$ext"'","type":"'"$attrs[1]"'","size":"'"$attrs[2]"'","depth":"'"$attrs[3]"'","color":"'"$attrs[4]"'"}'
    else
      if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- unable to identify image for $id ($ext)" >>&! $LOGTO
    endif
  end

  if ($?fmts == 0) then
    if ($?DEBUG) echo `date` "$0:t $$ -- $device -- update $id lacks images in any format; continuing..." >>&! $LOGTO
    continue
  else
    set fmts = "$fmts"']'
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- update $id formats" `echo "$fmts" | jq -c '.'` >>&! $LOGTO
  endif

  # test if image already identified 
  set url = "$CU/$device-$API/$id"
  set rev = ( `curl -s -q -f -L "$url" | jq -r '._rev'` )
  if ($#rev && $rev != "null") then
    if ($?force) then
      if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- WARNING -- attempting to update document for $id" >>&! $LOGTO
      set url = "$url?rev=$rev"
    else
      if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- found existing image in database; BREAKING" >>&! $LOGTO
      rm -f "$out"
      break
    endif
  endif
   
  ## write image document to database
  # create output record
  set out = "$TMP/$0:t.$device.$id.$$.json"
  # start record
  echo '{"id":"'"$id"'","date":'$date',"imagebox":"'"$imagebox"'","path":"'"$device/$year/$month/$day"'","formats":'"$fmts"'}' | jq -c '.' >! "$out"
  if ($status == 0 && -s "$out") then
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- record for image $id" `jq -c '.' "$out"` >>&! $LOGTO
  else
    if ($?DEBUG) echo `date` "$0:t $$ -- $device -- FAILURE: creating JSON for $id" `cat "$out"` >>&! $LOGTO
    rm -f "$out"
    break
  endif
  # store record
  curl -s -q -f -L -H "Content-type: application/json" -X PUT "$url" -d "@$out" >&! /dev/null
  if ($status != 0) then
    if ($?DEBUG) echo `date` "$0:t $$ -- FAILURE ($id) $nimage of $#updates" `cat "$out"` >>&! $LOGTO
  else
    @ nimage++
    if ($?VERBOSE) echo `date` "$0:t $$ -- SUCCESS ($id) $nimage of $#updates" `jq -c '.' "$out"` >>&! $LOGTO
  endif
  rm -f "$out"

## foreach
end

done:
if ($?DEBUG) echo `date` "$0:t $$ -- $device -- FINISH" >>&! $LOGTO

cleanup:
rm -f "$OUTPUT.$$"
