#!/bin/tcsh -b
setenv APP "aah"
setenv API "images"

# debug on/off
setenv DEBUG true
setenv VERBOSE true

# environment
if ($?LAN == 0) setenv LAN "192.168.1"
if ($?DIGITS == 0) setenv DIGITS "$LAN".30
if ($?TMP == 0) setenv TMP "/tmp"
if ($?AAHDIR == 0) setenv AAHDIR "/var/lib/age-at-home"
if ($?CREDENTIALS == 0) setenv CREDENTIALS /usr/local/etc
if ($?LOGTO == 0) setenv LOGTO $TMP/$APP.log

if ($?TTL == 0) set TTL = 60
if ($?SECONDS == 0) set SECONDS = `date "+%s"`
if ($?DATE == 0) set DATE = `echo $SECONDS \/ $TTL \* $TTL | /usr/bin/bc`

setenv DEBUG true

# transform image
setenv CAMERA_MODEL_TRANSFORM "CROP"
# retrieve using FTP
setenv CAMERA_IMAGE_RETRIEVE "FTP"
# maximum backlog size -- specify force to use all records
if ($?IMAGE_LIMIT == 0) setenv IMAGE_LIMIT 1000

# do not force continued attempts after failure when processing images

if ($?QUERY_STRING) then
    set device = `echo "$QUERY_STRING" | sed 's/.*device=\([^&]*\).*/\1/'`
    if ($device == "$QUERY_STRING") unset device
    set force = `echo "$QUERY_STRING" | sed 's/.*force=\([^&]*\).*/\1/'`
    if ($force == "$QUERY_STRING") unset force
    set limit = `echo "$QUERY_STRING" | sed 's/.*limit=\([^&]*\).*/\1/'`
    if ($limit == "$QUERY_STRING") unset limit
endif

if ($?limit) then
  if ($limit > $IMAGE_LIMIT) set limit = $IMAGE_LIMIT
else
  set limit = $IMAGE_LIMIT
endif

# standardize QUERY_STRING
setenv QUERY_STRING "device=$device"

if ($?DEBUG) echo `date` "$0:t $$ -- START ($QUERY_STRING)" >>&! $LOGTO

# OUTPUT target
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

if ($?force == 0 && -s "$OUTPUT") goto done

#
# SINGLE THREADED (by QUERY_STRING)
#
set INPROGRESS = ( `echo "$OUTPUT:r:r".*` )
if ($#INPROGRESS) then
    foreach ip ( $INPROGRESS )
      set pid = $ip:e
      set eid = ( `ps axw | awk '{ print $1 }' | egrep "$pid"` )
      if ($pid == $eid) then
        if ($?DEBUG) echo `date` "$0:t $$ -- PID $pid in-progress ($QUERY_STRING)"  >>&! $LOGTO
        goto done
      else
        if ($?VERBOSE) echo `date` "$0:t $$ -- removing $ip"  >>&! $LOGTO
        rm -f "$ip"
      endif
    end
    if ($?VERBOSE) echo `date` "$0:t $$ -- NO PROCESSES FOUND ($QUERY_STRING)"  >>&! $LOGTO
else
    if ($?VERBOSE) echo `date` "$0:t $$ -- NO EXISTING $0:t ($QUERY_STRING)"  >>&! $LOGTO
endif

# cleanup if interrupted
rm -f "$OUTPUT:r:r".*
onintr cleanup
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

#
# CREATE <device>-images DATABASE 
#
if ($?CU && $?device) then
  if ($?VERBOSE) echo `date` "$0:t $$ -- test if device exists ($CU/$device-$API)"  >>&! $LOGTO
  set dd = `curl -s -q -f -L -X GET "$CU/$device-$API" | jq -r '.db_name'`
  if ( $#dd == 0 || $dd == "null" ) then
    if ($?VERBOSE) echo `date` "$0:t $$ -- creating device $CU/$device-$API"  >>&! $LOGTO
    # create device
    set dd = `curl -s -q -f -L -X PUT "$CU/$device-$API" | jq '.ok'`
    # test for success
    if ( "$dd" != "true" ) then
      # failure
      if ($?VERBOSE) echo `date` "$0:t $$ -- failure creating Cloudant database ($device-$API)"  >>&! $LOGTO
      goto done
    else
      if ($?VERBOSE) echo `date` "$0:t $$ -- success creating device $CU/$device-$API"  >>&! $LOGTO
    endif
  endif
endif

# get last image processed
set since = 0
set url = "$CU/$device-images/_all_docs?include_docs=true&descending=true&limit=1"
set out = "/tmp/$0:t.$$.json"
curl -s -q -f -L "$url" -o "$out"
if ($status == 22 || ! -s "$out") then
  if ($?VERBOSE) echo `date` "$0:t $$ -- failed to retrieve ($url)" >>&! $LOGTO
else
  set total_images = ( `jq -r '.total_rows' "$out"` )
  set since = ( `jq -r '.rows[].doc.date' "$out"` )
  if ($#since == 0 || $since == "null") then
    set since = 0
  else
    set since = "$since[$#since]"
  endif
endif
if ($?VERBOSE) echo `date` "$0:t $$ -- last image retrieved at ($since)" >>&! $LOGTO

# get updates for this device
set url = "$WWW/CGI/aah-updates.cgi?db=$device&since=$since"
set out = "/tmp/$0:t.$$.json"
curl -s -q -f -L "$url" -o "$out"
if ($status == 22 || ! -s "$out") then
  if ($?VERBOSE) echo `date` "$0:t $$ -- failed to retrieve ($url)" >>&! $LOGTO
  goto done
else
  set total_updates = ( `jq -r '.total?' "$out"` )
  # get date, count and updates
  set date = ( `jq -r '.date?' "$out"` )
  if ($#date == 0 || $date == "null") set date = 0
endif
rm -f "$out"
if ($?VERBOSE) echo `date` "$0:t $$ -- last image retrieved at ($since)" >>&! $LOGTO

# check if up-to-date
if ($date <= $since) then
  @ lag = $date - $since
  if ($?DEBUG) echo `date` "$0:t $$ -- UP TO DATE ($device) - updated $date, images $since ($lag seconds)" >>&! $LOGTO
  goto done
endif

# get updates not processed
@ try = 0
@ rtt = 5
if ($?force) then
  set url = "$WWW/CGI/aah-updates.cgi?db=$device&since=$since&limit=$IMAGE_LIMIT"
else
  set url = "$WWW/CGI/aah-updates.cgi?db=$device&since=$since&limit=$limit"
endif
set out = "/tmp/$0:t.$$.json"
while ($try < 3) 
  /bin/rm -f "$out"
  curl -s -q -f -m $rtt -L "$url" -o "$out"
  if ($status == 22 || $status == 28 || ! -s "$out") then
    if ($status == 28) then
      @ try++
      @ rtt = $rtt + $rtt
      rm -f "$out"
      continue
    endif
    rm -f "$out"
  endif
  break
end
if (! -s "$out") then
  if ($?VERBOSE) echo `date` "$0:t $$ -- failed to retrieve ($url)" >>&! $LOGTO
  goto done
endif

set count = ( `jq -r '.count' "$out"` )
if ($#count == 0 || $count == "null") set count = 0
# process updates FIFO
set updates = ( `jq -r '.ids|reverse[]' "$out"` )
if ($#updates == 0) then
  set updates = ()
endif

# SANITY
if ($count == 0 || $#updates == 0) then
  if ($?DEBUG) echo `date` "$0:t $$ -- no updates ($count; $updates)" >>&! $LOGTO
  goto done
else
  if ($?DEBUG) echo `date` "$0:t $$ -- $count $#updates ($updates[1] $updates[$#updates])" >>&! $LOGTO
endif

# get IP address of device
set ipaddr = ( `curl -s -q -f -L "$WWW/CGI/aah-devices.cgi?db=$device" | jq -r ".ip_address"` )
if ($#ipaddr) then
  if ($?VERBOSE) echo `date` "$0:t $$ -- FOUND $device :: $ipaddr" >>&! $LOGTO
else
  if ($?VERBOSE) echo `date` "$0:t $$ -- NOT FOUND $device" >>&! $LOGTO
  goto done
endif

#
# PROCESS ALL UPDATES
#

@ nimage = 0
foreach u ( $updates )

  # retrieve update record (<device>-updates/$u) 
  set url = "$WWW/CGI/aah-updates.cgi?db=$device&id=$u"
  set out = "/tmp/$0:t.$$.json"
  /bin/rm -f "$out"
  curl -s -q -f -L "$url" -o "$out"
  if ($status == 22 || ! -s "$out") then
    if ($?VERBOSE) echo `date` "$0:t $$ -- FAILURE -- curl ($url) for update ($u)"  >>&! $LOGTO
  else if (`jq -r '.error?' "$out"` != "null") then
    if ($?VERBOSE) echo `date` "$0:t $$ -- NOT FOUND ($device,$u)"  >>&! $LOGTO
    rm -f "$out"
    continue 
  else
    set update = ( `jq '.' "$out"` )
  endif
  rm -f "$out"

  if ($?VERBOSE) echo `date` "$0:t $$ -- FOUND -- existing update ($update)" >>&! $LOGTO

  # get relevant update attributes 
  set id = ( `echo "$update" | jq -r '.id'` )
  set class = ( `echo "$update" | jq -r '.class'` )
  set model = ( `echo "$update" | jq -r '.model'` )
  set date = ( `echo "$update" | jq -r '.date'` )

  # CHEAT
  set crop = ( `curl -s -q -f -L "$CU/$device/$u" | jq -r '.imagebox'` )
  if ($#crop && $crop != "null") then
    if ($?VERBOSE) echo `date` "$0:t $$ -- got ($crop) for $u" >>&! $LOGTO
  else
    if ($?VERBOSE) echo `date` "$0:t $$ -- no crop for $u" >>&! $LOGTO
    set crop = ""
  endif

  # test if all good
  if ($#id == 0 || $#class == 0 || $#crop == 0 || "$class" == "null" || "$model" == "null") then
    if ($?DEBUG) echo `date` "$0:t $$ -- INVALID update ($device @ $nimage of $count) -- $id $model $class $crop" >>&! $LOGTO
    continue
  endif

  # test if already done w/ this image
  set exists = ( `curl -s -q -f -L "$CU/$device-$API/$u" | jq -r '._id,._rev'` )
  if ($#exists) then
    if ($#exists > 0 && "$exists[1]" == "$u") then
      # break if image exists and not forced
      if ($?force == 0) then
	if ($?DEBUG) echo `date` "$0:t $$ -- BREAKING ($device) UPDATES: $nimage INDEX: $nimage COUNT: $count -- existing ($exists)" >>&! $LOGTO
	break
      endif
      if ($?VERBOSE) echo `date` "$0:t $$ -- WARNING -- IMAGE EXISTS ($exists)" >>&! $LOGTO
      set exists = "$exists[2]"
    else
      unset exists
    endif
  else
    unset exists
  endif
  if ($?exists == 0) then
    if ($?VERBOSE) echo `date` "$0:t $$ -- NEW IMAGE ($u)" >>&! $LOGTO
  endif

  # propose destination
  set image = "$AAHDIR/$device/$class/$id.jpg"

  # ensure destination
  /bin/mkdir -p "$image:h"
  # verify destination
  if (! -d "$image:h") then
    echo `date` "$0:t $$ -- FAILURE -- exit; no directory ($image:h)" >>&! $LOGTO
    goto done
  endif

  # try to retreive iff DNE
  if (! -s "$image" && ! -l "$image") then
    if ($?VERBOSE) echo `date` "$0:t $$ -- retrieving ($id) with $ipaddr using $CAMERA_IMAGE_RETRIEVE" >>&! $LOGTO
    switch ($CAMERA_IMAGE_RETRIEVE)
      case "FTP":
        if ($?VERBOSE) echo `date` "$0:t $$ -- calling $APP-ftpImage to retrieve $image" >>&! $LOGTO
        ./$APP-ftpImage.csh "$id" "jpg" "$ipaddr" "$image" >>&! $LOGTO
        if (! -s "$image") then
          if ($?VERBOSE) echo `date` "$0:t $$ -- $APP-ftpImage FAILED to retrieve $image" >>&! $LOGTO
        endif
        breaksw
      default:
        if ($?VERBOSE) echo `date` "$0:t $$ -- unknown CAMERA_IMAGE_RETRIEVE ($CAMERA_IMAGE_RETRIEVE)" >>&! $LOGTO
        breaksw
    endsw
  endif

  # optionally transform image
  if (-s "$image" && ! -s "$image:r.jpeg" && $?CAMERA_MODEL_TRANSFORM) then
    if ($?VERBOSE) echo `date` "$0:t $$ -- transforming $image with $crop using $CAMERA_MODEL_TRANSFORM" >>&! $LOGTO
    set xform = ( `./$APP-transformImage.csh "$image" "$crop"` )
    if ($?VERBOSE) echo `date` "$0:t $$ -- TRANSFORMED ($u) $xform" >>&! $LOGTO
  endif
  
  # get image characteristics
  if (-s "$image") then
    identify "$image" \
      | /usr/bin/awk '{ printf("{\"type\":\"%s\",\"size\":\"%s\",\"crop\":\"'"$crop"'\",\"depth\":\"%s\",\"color\":\"%s\",\"date\":'"$date"'}\n", $2, $4, $5, $6) }' \
      >! "$out"
    if (-s "$out") then
      # create $devices-images/$u record
      set url = "$device-images/$u"
      # this should only happen when force is true and record already exists
      if ($?exists) then
        set url = "$url?rev=$exists"
      endif
      curl -s -q -f -L -H "Content-type: application/json" -X PUT "$CU/$url" -d "@$out" >&! /dev/null
      if ($status != 0) then
        if ($?DEBUG) echo `date` "$0:t $$ -- FAILURE ($u) $nimage of $count " `cat "$out"`  >>&! $LOGTO
      else
        @ nimage++
        if ($?DEBUG) echo `date` "$0:t $$ -- SUCCESS ($u) $nimage of $count " `jq -c '.' "$out"`  >>&! $LOGTO
      endif
      rm -f "$out"
    endif
  else
    if ($?VERBOSE) echo `date` "$0:t $$ -- WARNING ($u) -- no image ($image)" >>&! $LOGTO
  endif

  #
  # EXPERIMENT 1: STEP 2: BEGIN (STEP 1 in aah-make-updates)
  #
  set t = "$AAHDIR/$device/.models/$model/$class"
  /bin/mkdir -p "$t"
  /bin/rm -f "$u/$u"
  /bin/ln -s "$image" "$t/$u" >&! /dev/null
  #
  # EXPERIMENT 1: STEP 2: END
  #

end

done:
if ($?DEBUG) echo `date` "$0:t $$ -- FINISH ($QUERY_STRING)"  >>&! $LOGTO

cleanup:
rm -f "$OUTPUT.$$"
