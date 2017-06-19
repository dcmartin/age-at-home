#!/bin/csh -fb
setenv APP "aah"
setenv API "updates"
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
# do not force continued attempts after failure when processing images
setenv NOFORCE true

if ($?QUERY_STRING) then
    set device = `/bin/echo "$QUERY_STRING" | sed 's/.*device=\([^&]*\).*/\1/'`
    if ($device == "$QUERY_STRING") unset device
endif

# DEFAULTS to rough-wind (frontdoor)
if ($?device == 0) set device = "rough-wind"

# standardize QUERY_STRING
setenv QUERY_STRING "device=$device"

if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- START ($QUERY_STRING)"  >>&! $TMP/LOG

#
# CHANGES target
#
set CHANGES = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

#
# SINGLE THREADED (by QUERY_STRING)
#
set INPROGRESS = ( `/bin/echo "$CHANGES:r:r".*.json.*` )
if ($#INPROGRESS) then
    foreach ip ( $INPROGRESS )
      set pid = $ip:e
      set eid = ( `ps axw | awk '{ print $1 }' | egrep "$pid"` )
      if ($pid == $eid) then
        if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- in-progress $QUERY_STRING ($pid)" >>&! $TMP/LOG
        goto done
      else
        if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- removing $ip" >>&! $TMP/LOG
        rm -f "$ip"
      endif
    end
else
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- NO EXISTING PROCESS [$INPROGRESS] ($QUERY_STRING)" >>&! $TMP/LOG
endif

# cleanup if interrupted
onintr cleanup
touch "$CHANGES".$$

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
  /bin/echo `/bin/date` "$0 $$ -- NO ~$USER/.cloudant_url" >>&! $TMP/LOG
  goto done
endif

#
# CREATE device-updates DATABASE 
#
if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- test if device exists (device-$API)" >>&! $TMP/LOG
set devdb = `/usr/bin/curl -f -s -q -L -X GET "$CU/device-$API" | /usr/local/bin/jq '.db_name'`
if ( $devdb == "" || "$devdb" == "null" ) then
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- creating device-$API" >>&! $TMP/LOG
  # create device
  set devdb = `/usr/bin/curl -f -s -q -L -X PUT "$CU/device-$API" | /usr/local/bin/jq '.ok'`
  # test for success
  if ( "$devdb" != "true" ) then
    # failure
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- failure creating Cloudant database (device-$API)" >>&! $TMP/LOG
    goto done
  else
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- success creating device (device-$API)" >>&! $TMP/LOG
  endif
endif

#
# GET last sequence for DEVICE from DATABASE
#
set url = "device-$API/$device"
set out = "/tmp/$0:t.$$.json"
/usr/bin/curl --connect-time 10 -m 30 -f -q -s -L "$CU/$url" -o "$out"
if ($status != 22 && $status != 28 && -s "$out") then
  set seqid = ( `/usr/local/bin/jq -r '.seqid' "$out"` )
  set date = ( `/usr/local/bin/jq -r '.date' "$out"` )
  if ($#seqid) then
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- SUCCESS retrieving seqid from $device ($seqid)" >>! $TMP/LOG
    if ($seqid == "null" || $seqid == "") then
       set seqid = 0
    endif
  else
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- FAILED retrieving seqid from $device" >>! $TMP/LOG
    set seqid = 0
  endif
else
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- fail ($url)" >>! $TMP/LOG
  goto done
endif
rm -f "$out"

#
# get new CHANGES since last sequence (seqid from device-updates/<device>)
#
@ try = 0
set url = "$device/_changes?include_docs=true&since=$seqid"
set out = "/tmp/$0:t.$$.json"
set connect = 10
set transfer = 30

again: # try again

if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- download _changes ($url)" >>! $TMP/LOG
/usr/bin/curl -s -q --connect-time $connect -m $transfer -f -L "$CU/$url" -o "$out" >>&! $TMP/LOG
if ($status != 22 && $status != 28 && -s "$out") then
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- download SUCCESS ($CHANGES)" >>! $TMP/LOG
  # test JSON
  /usr/local/bin/jq '.' "$out" >&! /dev/null
  if ($status != 0) then
    set result = $status
    if ($try < 4) then
      @ transfer = $transfer + $transfer
      @ try++
      goto again
    endif
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- INVALID ($result) TRY ($try) TRANSFER ($transfer) CHANGES ($out)" >>! $TMP/LOG
    goto done
  endif
  mv -f "$out" "$CHANGES"
  set last_seq = ( `/usr/local/bin/jq -r '.last_seq' "$CHANGES"` )
  set count = `/usr/local/bin/jq -r '.results[]?.doc._id' "$CHANGES" | wc -l`
  if ($last_seq == $seqid) then
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- up-to-date ($seqid) records ($count)" >>! $TMP/LOG
  endif
else
  rm -f "$out"
  if ($try < 3) then
    @ transfer = $transfer + $transfer
    @ try++
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- RETRY ($url)" >>! $TMP/LOG
    goto again
  endif
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- download FAILED ($url)" >>! $TMP/LOG
  goto done
endif

# start at nothing new
set nimage = 0
set ids = ""

# check if new events (or start-up == 0)
if ($count == 0) then
  goto update
else
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- $count EVENTS FOR $device ($last_seq)" >>! $TMP/LOG
endif

# get IP address of device
set ipaddr = ( `/usr/bin/curl -s -q -f -L "$WWW/CGI/aah-devices.cgi" | /usr/local/bin/jq -r '.|select(.name=="'"$device"'")' | /usr/local/bin/jq -r ".ip_address"` )
if ($#ipaddr) then
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- FOUND $device :: $ipaddr" >>! $TMP/LOG
else
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- NOT FOUND $device" >>! $TMP/LOG
  goto done
endif

foreach line ( `/usr/local/bin/jq -j '.results[]?.doc|(.visual.image,",",.alchemy.text,",",.imagebox,"\n")' "$CHANGES" | egrep -v "^null" | sed "s/ /_/g" | sort -t, -k1,1 -r` )

    set triple = ( `echo "$line" | sed "s/,/ /g"` )

    set file = $triple[1]
    set top1 = $triple[2]
    set crop = $triple[3]

    # image destination
    set image = "$TMP/$device/$top1/$file"
    mkdir -p "$image:h"
    if (! -d "$image:h") then
      if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- exit; no directory ($image:h)" >>! $TMP/LOG
      exit
    endif

    # test if image already exists
    if (! -s "$image") then
	set ext = "$file:e"
	set ftp = "ftp://ftp:ftp@$ipaddr/$file" 
	/usr/bin/curl -s -q -L "$ftp" -o "/tmp/$$.$ext"
	if (! -s "/tmp/$$.$ext") then
	    rm -f "/tmp/$$.$ext"
	    if ($?NOFORCE) then
	      if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- fail ($ftp); break" >>! $TMP/LOG
	      break
	    else
	      if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- fail ($ftp); continue (FORCED)" >>! $TMP/LOG
	      continue
	    endif
	else
	    mv -f "/tmp/$$.$ext" "$image"
	endif
	if (-s "$image") then
	    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- SUCCESS ($device) :: CLASS ($top1) :: ID ($file:r)" >>! $TMP/LOG
	    # add delimiter
	    if ($nimage) set ids = "$ids"','
	    set ids = "$ids"'"'"$file:r"'"'
	    @ nimage++
	    # optionally delete the source
	    if ($?FTP_DELETE) then
		if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- deleting ($file)" >>! $TMP/LOG
		/usr/bin/curl -s -q -L "ftp://$ipaddr/" -Q "-DELE $file"
	    endif
	    # transform image
	    if ($?CAMERA_MODEL_TRANSFORM) then
	      if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- transforming $image with $crop using $CAMERA_MODEL_TRANSFORM" >>! $TMP/LOG
	      ./$APP-transformImage.csh "$image" "$crop" >>! $TMP/LOG
	    endif
	else
	    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- FAILURE ($image)" >>! $TMP/LOG
	    continue
	endif
    else
	if ($?NOFORCE) then
	  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- found existing image ($image); break" >>! $TMP/LOG
	  break
        else
	  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- found existing image ($image); continue (FORCED)" >>! $TMP/LOG
	endif
    endif

end # foreach line ( CHANGES )

rm -f "$CHANGES"

update:

#
# get old DEVICE record
#
set url = "device-$API/$device"
set out = "/tmp/$0:t.$$.json"
/usr/bin/curl --connect-time 10 -m 30 -f -s -q -L "$CU/$url" -o "$out"
if ($status != 22 && $status != 28 && -s "$out") then
  set rev = ( `/usr/local/bin/jq -r '._rev?' "$out"` )
  if ($#rev == 0 || "$rev" == "null") then
    unset rev
  else
    set old_count = ( `/usr/local/bin/jq -r '.count?' "$out"` )
    set old_ids= ( `/usr/local/bin/jq '.ids[]?' "$out"` )
    if ($#old_count == 0 || "$old_count" == "null") unset old_count
    if ($#old_ids == 0 || "$old_ids" == "null") unset old_ids
  endif
endif
rm -f "$out"

#
# update DEVICE record
#
if ($?old_ids && $?old_count) then
  @ count = $nimage + $old_count
  if ($#old_ids) then
    set old_ids = `echo "$old_ids" | sed 's/ /,/g'`
    if ($ids != "") then
      set ids = "$ids,$old_ids"
    else
      set ids = "$old_ids"
    endif
  endif
else
  @ count = $nimage
  set date = $DATE
endif

if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- COMPLETED $nimage ($count) IMAGES for DEVICE $device MODIFIED " `date -r $date '+%a, %d %b %Y %H:%M:%S %Z'` >>&! $TMP/LOG

# create new output
echo \
  '{'\
    '"name":"'"$device"'",'\
    '"seqid":"'"$last_seq"'",'\
    '"date":'"$date"','\
    '"ids":['"$ids"'],'\
    '"count":'"$count"\
  '}' >! "$CHANGES"

# check for previous version
if ($?rev) then
    set url = "device-$API/$device?rev=$rev"
else
    set url = "device-$API/$device"
endif
set out = "/tmp/$0:t.$$.json"
/usr/bin/curl -s -q -f -L -H "Content-type: application/json" -X PUT "$CU/$url" -d "@$CHANGES" -o "$out" >>&! $TMP/LOG
if ($status != 22 && -s "$out") then
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- PUT $url returned {" `cat "$out"` "}" >>&! $TMP/LOG
endif
rm -f "$out"

done:
if ($?VERBOSE) echo `/bin/date` "$0 $$ -- FINISH $QUERY_STRING"  >>! $TMP/LOG

cleanup:
rm -f "$CHANGES" "$CHANGES".$$
