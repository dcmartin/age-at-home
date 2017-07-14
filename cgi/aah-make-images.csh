#!/bin/csh -fb
setenv APP "aah"
setenv API "images"
setenv LAN "192.168.1"
setenv WWW "$LAN".32
setenv DIGITS "$LAN".30
setenv WAN "www.dcmartin.com"
setenv TMP "/var/lib/age-at-home"

if ($?TTL == 0) set TTL = 60
if ($?SECONDS == 0) set SECONDS = `/bin/date "+%s"`
if ($?DATE == 0) set DATE = `/bin/echo $SECONDS \/ $TTL \* $TTL | /usr/bin/bc`

setenv DEBUG true

# transform image
setenv CAMERA_MODEL_TRANSFORM "CROP"
# retrieve using FTP
setenv CAMERA_IMAGE_RETRIEVE "FTP"
# maximum backlog size -- specify force to use all records
if ($?IMAGE_LIMIT == 0) setenv IMAGE_LIMIT 10000

# do not force continued attempts after failure when processing images

if ($?QUERY_STRING) then
    set device = `/bin/echo "$QUERY_STRING" | sed 's/.*device=\([^&]*\).*/\1/'`
    if ($device == "$QUERY_STRING") unset device
    set force = `/bin/echo "$QUERY_STRING" | sed 's/.*force=\([^&]*\).*/\1/'`
    if ($force == "$QUERY_STRING") unset force
    set limit = `/bin/echo "$QUERY_STRING" | /usr/bin/sed 's/.*limit=\([^&]*\).*/\1/'`
    if ($limit == "$QUERY_STRING") unset limit
endif

# DEFAULTS to quiet-water
if ($?device == 0) set device = "quiet-water" # should be a fail

if ($?limit) then
  if ($limit > $IMAGE_LIMIT) set limit = $IMAGE_LIMIT
else
  set limit = $IMAGE_LIMIT
endif

# standardize QUERY_STRING
setenv QUERY_STRING "device=$device"

if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- START ($QUERY_STRING)"   >>&! $TMP/LOG

# OUTPUT target
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

if ($?force == 0 && -s "$OUTPUT") goto done

#
# SINGLE THREADED (by QUERY_STRING)
#
set INPROGRESS = ( `/bin/echo "$OUTPUT:r:r".*` )
if ($#INPROGRESS) then
    foreach ip ( $INPROGRESS )
      set pid = $ip:e
      set eid = ( `ps axw | awk '{ print $1 }' | egrep "$pid"` )
      if ($pid == $eid) then
        if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- PID $pid in-progress ($QUERY_STRING)"  >>&! $TMP/LOG
        goto done
      else
        if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- removing $ip"  >>&! $TMP/LOG
        rm -f "$ip"
      endif
    end
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- NO PROCESSES FOUND ($QUERY_STRING)"  >>&! $TMP/LOG
else
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- NO EXISTING $0 ($QUERY_STRING)"  >>&! $TMP/LOG
endif

# cleanup if interrupted
rm -f "$OUTPUT:r:r".*
onintr cleanup
touch "$OUTPUT".$$

#
# GET CLOUDANT CREDENTIALS
#
if (-e ~$USER/.cloudant_url) then
  set cc = ( `cat ~$USER/.cloudant_url` )
  if ($#cc > 0) set CU = $cc[1]
  if ($#cc > 1) set CN = $cc[2]
  if ($#cc > 2) set CP = $cc[3]
  if ($?CN && $?CP) then
    set CU = "$CN":"$CP"@"$CU"
  else
else
  /bin/echo `/bin/date` "$0 $$ -- NO ~$USER/.cloudant_url"  >>&! $TMP/LOG
  goto done
endif

#
# CREATE <device>-images DATABASE 
#
if ($?CU && $?device) then
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- test if device exists ($CU/$device-$API)"  >>&! $TMP/LOG
  set dd = `/usr/bin/curl -s -q -f -L -X GET "$CU/$device-$API" | /usr/local/bin/jq -r '.db_name'`
  if ( $#dd == 0 || $dd == "null" ) then
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- creating device $CU/$device-$API"  >>&! $TMP/LOG
    # create device
    set dd = `/usr/bin/curl -s -q -f -L -X PUT "$CU/$device-$API" | /usr/local/bin/jq '.ok'`
    # test for success
    if ( "$dd" != "true" ) then
      # failure
      if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- failure creating Cloudant database ($device-$API)"  >>&! $TMP/LOG
      goto done
    else
      if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- success creating device $CU/$device-$API"  >>&! $TMP/LOG
    endif
  endif
endif

# get last image processed
set since = 0
set url = "$CU/$device-images/_all_docs?include_docs=true&descending=true&limit=1"
set out = "/tmp/$0:t.$$.json"
/usr/bin/curl -s -q -f -L "$url" -o "$out"
if ($status == 22 || ! -s "$out") then
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- failed to retrieve ($url)" >>! $TMP/LOG
else
  set total_images = ( `/usr/local/bin/jq -r '.total_rows' "$out"` )
  set since = ( `/usr/local/bin/jq -r '.rows[].doc.date' "$out"` )
  if ($#since == 0 || $since == "null") then
    set since = 0
  else
    set since = "$since[$#since]"
  endif
endif

# get updates for this device
set url = "$WWW/CGI/aah-updates.cgi?db=$device&since=$since"
set out = "/tmp/$0:t.$$.json"
/usr/bin/curl -s -q -f -L "$url" -o "$out"
if ($status == 22 || ! -s "$out") then
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- failed to retrieve ($url)" >>! $TMP/LOG
  goto done
else
  set total_updates = ( `/usr/local/bin/jq -r '.total?' "$out"` )
  # get date, count and updates
  set date = ( `/usr/local/bin/jq -r '.date?' "$out"` )
  if ($#date == 0 || $date == "null") set date = 0
endif
rm -f "$out"

# check if up-to-date
if ($date <= $since) then
  @ lag = $date - $since
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- UP TO DATE ($device) - updated "`/bin/date -j -f %s "$date"`", images "`/bin/date -j -f %s "$since"`" ($lag seconds)" >>! $TMP/LOG
  goto done
endif

# get updates not processed
@ try = 0
@ rtt = 5
if ($?force) then
  set url = "$WWW/CGI/aah-updates.cgi?db=$device&since=$since&limit=$total_updates"
else
  set url = "$WWW/CGI/aah-updates.cgi?db=$device&since=$since&limit=$limit"
endif
set out = "/tmp/$0:t.$$.json"
while ($try < 3) 
  /bin/rm -f "$out"
  /usr/bin/curl -s -q -f -m $rtt -L "$url" -o "$out"
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
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- failed to retrieve ($url)" >>! $TMP/LOG
  goto done
endif

set count = ( `/usr/local/bin/jq -r '.count' "$out"` )
if ($#count == 0 || $count == "null") set count = 0
# process updates FIFO
set updates = ( `/usr/local/bin/jq -r '.ids|reverse[]' "$out"` )
if ($#updates == 0) then
  set updates = ()
endif

# SANITY
if ($count == 0 || $#updates == 0) then
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- no updates ($count; $updates)" >>! $TMP/LOG
  goto done
else
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- $count $#updates ($updates[1] $updates[$#updates])" >>! $TMP/LOG
endif

# get IP address of device
set ipaddr = ( `/usr/bin/curl -s -q -f -L "$WWW/CGI/aah-devices.cgi?db=$device" | /usr/local/bin/jq -r ".ip_address"` )
if ($#ipaddr) then
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- FOUND $device :: $ipaddr" >>! $TMP/LOG
else
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- NOT FOUND $device" >>! $TMP/LOG
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
  /usr/bin/curl -s -q -f -L "$url" -o "$out"
  if ($status == 22 || ! -s "$out") then
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- FAILURE -- curl ($url) for update ($u)"  >>&! $TMP/LOG
  else if (`/usr/local/bin/jq -r '.error?' "$out"` != "null") then
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- NOT FOUND ($device,$u)"  >>&! $TMP/LOG
    rm -f "$out"
    continue 
  else
    set update = ( `/usr/local/bin/jq '.' "$out"` )
  endif
  rm -f "$out"

  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- FOUND -- existing update ($update)" >>! $TMP/LOG

  # get relevant update attributes 
  set id = ( `/bin/echo "$update" | /usr/local/bin/jq -r '.id'` )
  set class = ( `/bin/echo "$update" | /usr/local/bin/jq -r '.class'` )
  set model = ( `/bin/echo "$update" | /usr/local/bin/jq -r '.model'` )
  set date = ( `/bin/echo "$update" | /usr/local/bin/jq -r '.date'` )

  # CHEAT
  set crop = ( `/usr/bin/curl -s -q -f -L "$CU/$device/$u" | /usr/local/bin/jq -r '.imagebox'` )
  if ($#crop && $crop != "null") then
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- got ($crop) for $u" >>! $TMP/LOG
  else
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- no crop for $u" >>! $TMP/LOG
    set crop = ""
  endif

  # test if all good
  if ($#id == 0 || $#class == 0 || $#crop == 0 || "$class" == "null" || "$model" == "null") then
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- INVALID update ($device @ $nimage of $count) -- $id $model $class $crop" >>! $TMP/LOG
    continue
  endif

  # test if already done w/ this image
  set exists = ( `/usr/bin/curl -s -q -f -L "$CU/$device-$API/$u" | /usr/local/bin/jq -r '._id,._rev'` )
  if ($#exists) then
    if ($#exists > 0 && "$exists[1]" == "$u") then
      # break if image exists and not forced
      if ($?force == 0) then
	if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- BREAKING ($device) UPDATES: $nimage INDEX: $nimage COUNT: $count -- existing ($exists)" >>! $TMP/LOG
	break
      endif
      if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- WARNING -- IMAGE EXISTS ($exists)" >>! $TMP/LOG
      set exists = "$exists[2]"
    else
      unset exists
    endif
  else
    unset exists
  endif
  if ($?exists == 0) then
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- NEW IMAGE ($u)" >>! $TMP/LOG
  endif

  # propose destination
  set image = "$TMP/$device/$class/$id.jpg"

  # ensure destination
  /bin/mkdir -p "$image:h"
  # verify destination
  if (! -d "$image:h") then
    /bin/echo `/bin/date` "$0 $$ -- FAILURE -- exit; no directory ($image:h)" >>! $TMP/LOG
    goto done
  endif

  # try to retreive iff DNE
  if (! -s "$image" && ! -l "$image") then
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- retrieving ($id) with $ipaddr using $CAMERA_IMAGE_RETRIEVE" >>! $TMP/LOG
    switch ($CAMERA_IMAGE_RETRIEVE)
      case "FTP":
        if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- calling $APP-ftpImage to retrieve $image" >>! $TMP/LOG
        ./$APP-ftpImage.csh "$id" "jpg" "$ipaddr" "$image" >>! $TMP/LOG
        if (! -s "$image") then
          if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- $APP-ftpImage FAILED to retrieve $image" >>! $TMP/LOG
        endif
        breaksw
      default:
        if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- unknown CAMERA_IMAGE_RETRIEVE ($CAMERA_IMAGE_RETRIEVE)" >>! $TMP/LOG
        breaksw
    endsw
  endif

  # optionally transform image
  if (-s "$image" && ! -s "$image:r.jpeg" && $?CAMERA_MODEL_TRANSFORM) then
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- transforming $image with $crop using $CAMERA_MODEL_TRANSFORM" >>! $TMP/LOG
    set xform = ( `./$APP-transformImage.csh "$image" "$crop"` )
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- TRANSFORMED ($u) $xform" >>! $TMP/LOG
  endif
  
  # get image characteristics
  if (-s "$image") then
    /usr/local/bin/identify "$image" \
      | /usr/bin/awk '{ printf("{\"type\":\"%s\",\"size\":\"%s\",\"crop\":\"'"$crop"'\",\"depth\":\"%s\",\"color\":\"%s\",\"date\":'"$date"'}\n", $2, $4, $5, $6) }' \
      >! "$out"
    if (-s "$out") then
      # create $devices-images/$u record
      set url = "$device-images/$u"
      # this should only happen when force is true and record already exists
      if ($?exists) then
        set url = "$url?rev=$exists"
      endif
      /usr/bin/curl -s -q -f -L -H "Content-type: application/json" -X PUT "$CU/$url" -d "@$out" >&! /dev/null
      if ($status != 0) then
        if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- FAILURE ($u) $nimage of $count " `/bin/cat "$out"`  >>&! $TMP/LOG
      else
        @ nimage++
        if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- SUCCESS ($u) $nimage of $count " `/usr/local/bin/jq -c '.' "$out"`  >>&! $TMP/LOG
      endif
      rm -f "$out"
    endif
  else
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- WARNING ($u) -- no image ($image)" >>&! $TMP/LOG
  endif

  #
  # EXPERIMENT 1: STEP 2: BEGIN (STEP 1 in aah-make-updates)
  #
  set t = "$TMP/$device/.models/$model/$class"
  /bin/mkdir -p "$t"
  /bin/rm -f "$u/$u"
  /bin/ln -s "$image" "$t/$u" >&! /dev/null
  #
  # EXPERIMENT 1: STEP 2: END
  #

end

done:
if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- FINISH ($QUERY_STRING)"  >>! $TMP/LOG

cleanup:
rm -f "$OUTPUT.$$"
