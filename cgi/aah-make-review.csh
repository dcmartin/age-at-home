#!/bin/tcsh -b
setenv APP "aah"
setenv API "review"

# debug on/off
setenv DEBUG true
setenv VERBOSE true

# environment
if ($?LAN == 0) setenv LAN "192.168.1"
if ($?DIGITS == 0) setenv DIGITS "$LAN".30
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"
if ($?CREDENTIALS == 0) setenv CREDENTIALS /usr/local/etc
if ($?LOGTO == 0) setenv LOGTO /dev/stderr

if ($?TTL == 0) set TTL = 1800
if ($?SECONDS == 0) set SECONDS = `/bin/date "+%s"`
if ($?DATE == 0) set DATE = `/bin/echo $SECONDS \/ $TTL \* $TTL | /usr/bin/bc`

# setenv DEBUG true
setenv NOFORCE true

if ($?QUERY_STRING) then
    set db = `/bin/echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
endif

# DEFAULTS to rough-fog (kitchen) and all classes
if ($?db == 0) set db = rough-fog

# standardize QUERY_STRING
setenv QUERY_STRING "db=$db"

/bin/echo `/bin/date` "$0 $$ -- START ($QUERY_STRING)"  >>&! $LOGTO

#
# OUTPUT target
#
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

if (-s "$OUTPUT") goto done

#
# SINGLE THREADED (by QUERY_STRING)
#
set INPROGRESS = ( `/bin/echo "$OUTPUT:r:r".*.json.*` )
if ($#INPROGRESS) then
  foreach ip ( $INPROGRESS )
    set pid = $ip:e
    set eid = `ps axw | awk '{ print $1 }' | egrep "$pid"`
    if ($pid == $eid) then
      if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- in-progress ($pid)" >>&! $LOGTO
      goto done
    endif
    rm -f $ip
  end
endif

# cleanup if interrupted
onintr cleanup
rm -f "$OUTPUT:r:r".*
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
  /bin/echo `date` "$0:t $$ -- FAILURE: no Cloudant credentials" >>& $LOGTO
  goto done
endif

#
# CREATE <device>-review DATABASE 
#
if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- test if exists ($db-$API)" >>&! $LOGTO
set devdb = `curl -f -s -q -L -X GET "$CU/$db-$API" | jq '.db_name'`
if ( $devdb == "" || "$devdb" == "null" ) then
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- creating $db-$API" >>&! $LOGTO
  # create device
  set devdb = `curl -f -s -q -L -X PUT "$CU/$db-$API" | jq '.ok'`
  # test for success
  if ( "$devdb" != "true" ) then
    # failure
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- failure creating Cloudant database ($db-$API)" >>&! $LOGTO
    goto done
  else
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- success creating database ($db-$API)" >>&! $LOGTO
  endif
endif

#
# GET seqid FROM all RECORD FOR <db>-updates DB
#
set url = "$db-$API/all"
set out = "/tmp/$0:t.$$.json"
curl -m 30 -f -q -s -L "$CU/$url" -o "$out"
if ($status != 22 && $status != 28 && -s "$out") then
  set allrev = ( `jq -r '.rev' "$out"` )
  if ($#allrev == 0 || $allrev == "null") then
    unset allrev
  endif
  set seqid = ( `jq -r '.seqid' "$out"` )
  if ($#seqid) then
    if ($seqid == "null" || $seqid == "") then
      set seqid = 0
    else
      if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- SUCCESS retrieving seqid ($seqid)" >>! $LOGTO
    endif
  else
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- FAILED retrieving seqid" >>! $LOGTO
    set seqid = 0
  endif
else
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- fail ($url)" >>! $LOGTO
  goto done
endif
rm -f "$out"

#
# get new UPDATES since last sequence (seqid from device-updates/<device>)
#
@ try = 0
set url = "$db-updates/_changes?include_docs=true&since=$seqid"
set out = "/tmp/$0:t.$$.json"
set connect = 10
set transfer = 30

again: # try again

if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- download _changes ($url)" >>! $LOGTO
curl -s -q --connect-time $connect -m $transfer -f -L "$CU/$url" -o "$out" >>&! $LOGTO
if ($status != 22 && $status != 28 && -s "$out") then
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- download SUCCESS ($UPDATES)" >>! $LOGTO
  # test JSON
  jq '.' "$out" >&! /dev/null
  if ($status != 0) then
    set result = $status
    if ($try < 4) then
      @ transfer = $transfer + $transfer
      @ try++
      goto again
    endif
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- INVALID ($result) TRY ($try) TRANSFER ($transfer) UPDATES ($out)" >>! $LOGTO
    goto done
  endif
  mv -f "$out" "$UPDATES"
  set last_seq = ( `jq -r '.last_seq' "$UPDATES"` )
  # count updates (w/o all record)
  set count = ( `jq -r '.results[]?|select(.id != "all").id' "$UPDATES" | wc -l | awk '{ print $1 }'` )
  if ($last_seq == $seqid) then
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- up-to-date ($seqid) records ($count)" >>! $LOGTO
  endif
else
  rm -f "$out"
  if ($try < 3) then
    @ transfer = $transfer + $transfer
    @ try++
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- RETRY ($url)" >>! $LOGTO
    goto again
  endif
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- download FAILED ($url)" >>! $LOGTO
  goto done
endif

# check if new events (or start-up == 0)
if ($count == 0) then
  goto update
else
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- $count updates FOR $device since $seqid ($UPDATES)" >>! $LOGTO
endif

# start output
/bin/echo '{"date":'"$DATE"',"seqid":"'"$last_seq"'","classes":[' >! "$OUTPUT.$$"

# get all top1 from UPDATES
set classes = ( `jq -r '.results[]?.doc.top1.classifier_id' "$out"` )
if ($#classes == 0 || $classes == "null") then
  /bin/echo `/bin/date` "$0 $$ !! EXIT --  FOUND NO CLASSES ($UPDATES)" >>! $LOGTO
  exit
endif

if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- got $#classes ($classes)" >>! $LOGTO

#
# PROCESS ALL UPDATES
#

foreach c ( $classes )
  foreach line ( `jq -r -c '.count,",",.min,",",.max,",",.sum,",",.mean,",",.stdev,"\n"' "$UPDATES"` )
    /bin/echo "$line"
  end
end


.results[]?.doc|(.visual.image,",",.alchemy.text,",",.imagebox,"\n")'
#
# PROCESS ALL NEW UPDATES TO CHANGE CLASS STATISTICS
#
set url = "$db-$API/$c"
set out = "/tmp/$0:t.$$.json"
curl -s -q -f -L "$CU/$url" -o "$out"
if ($status == 22 || $status == 28 || ! -s "$out") then
  set count = 0; set min = 1; set max = 0; set sum = 0; set mean = 0; set stdev = 0; set var = 0
else
  set rev = ( `jq -r '._rev' "$old"` )
  if ($#rev && $rev != "null") then
    set count = ( `jq -r '.count' "$old"` )
    set min = ( `jq -r '.min' "$old"` )
    set max = ( `jq -r '.max' "$old"` )
    set sum = ( `jq -r '.sum' "$old"` )
    set mean = ( `jq -r '.mean' "$old"` )
    set stdev = ( `jq -r '.stdev' "$old"` )
    set variance = `/bin/echo "$stdev * $stdev * $count" | bc -l`
  else
    unset rev
  endif
endif

jq -j 
 "$UPDATES"` \
  | awk -F, \
    -v "c=$count" \
    -v "mx=$max" \
    -v "s=$sum" \
    -v "m=$mean" \
    -v "vs=$variance" \
    '{ c++; if ($5 > mx) mx=$5; s+=$5; m=s/c; vs+=(($5-m)^2) } END { sd=0; if (c > 0) sd=sqrt(vs/c); printf "{\"count\":%d,\"max\":%f,\"sum\":%f,\"mean\":%f,\"stdev\":%f}", c, mx, s, m, sd, kt }' >> "$NEW_STATS"


\"count\":%d,\"min\":%f,\"max\":%f,\"sum\":%f,\"mean\":%f,\"stdev\":%f,\"kurtosis\":%f}
end

# finish output
/bin/echo '],"count":'"$#classes"'}' >> "$OUTPUT.$$"

# test output
jq -c '.' "$OUTPUT.$$" >! "$OUTPUT"
if ($status != 0) exit

#
# update "all" record
#

if ($?allrev) then
    set url = "$db-$API/all?rev=$rev"
else
    set url = "$db-$API/all"
endif
set out = "/tmp/$0:t.$$.json"
curl -s -q -f -L -H "Content-type: application/json" -X PUT "$CU/$url" -d "@$OUTPUT" -o "$out" >>&! $LOGTO
if ($status != 22 && -s "$out") then
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- PUT $url returned {" `cat "$out"` "}" >>&! $LOGTO
endif
rm -f "$out"

done:
/bin/echo `/bin/date` "$0 $$ -- FINISH ($QUERY_STRING)" >>&! $LOGTO

cleanup:
rm -f "$OUTPUT.$$"
