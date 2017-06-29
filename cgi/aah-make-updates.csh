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

if ($?QUERY_STRING) then
    set device = `/bin/echo "$QUERY_STRING" | sed 's/.*device=\([^&]*\).*/\1/'`
    if ($device == "$QUERY_STRING") unset device
    set force = `/bin/echo "$QUERY_STRING" | sed 's/.*force=\([^&]*\).*/\1/'`
    if ($force == "$QUERY_STRING") unset force
endif

# DEFAULTS to quiet-water
if ($?device == 0) set device = "quiet-water"

# standardize QUERY_STRING
setenv QUERY_STRING "device=$device"

if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- START ($QUERY_STRING)"  >>&! $TMP/LOG

# OUTPUT target
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

if (-s "$OUTPUT") goto done

#
# SINGLE THREADED (by QUERY_STRING)
#
set INPROGRESS = ( `/bin/echo "$OUTPUT:r:r".*` )
if ($#INPROGRESS) then
    foreach ip ( $INPROGRESS )
      set pid = $ip:e
      set eid = ( `ps axw | awk '{ print $1 }' | egrep "$pid"` )
      if ($pid == $eid) then
        if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- PID $pid in-progress ($QUERY_STRING)" >>&! $TMP/LOG
        goto done
      else
        if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- removing $ip" >>&! $TMP/LOG
        rm -f "$ip"
      endif
    end
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- NO PROCESSES FOUND ($QUERY_STRING)" >>&! $TMP/LOG
else
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- NO EXISTING $0 ($QUERY_STRING)" >>&! $TMP/LOG
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
# CREATE <device>-updates DATABASE 
#
if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- test if exists ($device-$API)" >>&! $TMP/LOG
set devdb = `/usr/bin/curl -f -s -q -L -X GET "$CU/$device-$API" | /usr/local/bin/jq '.db_name'`
if ( $devdb == "" || "$devdb" == "null" ) then
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- creating $device-$API" >>&! $TMP/LOG
  # create device
  set devdb = `/usr/bin/curl -f -s -q -L -X PUT "$CU/$device-$API" | /usr/local/bin/jq '.ok'`
  # test for success
  if ( "$devdb" != "true" ) then
    # failure
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- failure creating Cloudant database ($device-$API)" >>&! $TMP/LOG
    goto done
  else
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- success creating device ($device-$API)" >>&! $TMP/LOG
  endif
endif

#
# GET device-updates/<device>
#
set url = "device-$API/$device"
set out = "/tmp/$0:t.$$.json"
/usr/bin/curl --connect-time 2 -m 30 -f -q -s -L "$CU/$url" -o "$out"
if ($status == 22 || $status == 28 || ! -s "$out") then
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- FAILED retrieving seqid from device" >>! $TMP/LOG
    set seqid = 0
else
  set devrev = ( `/usr/local/bin/jq -r '._rev' "$out"` )
  if ($#devrev == 0 || $devrev == "null") then
    unset devrev
  endif
  set seqid = ( `/usr/local/bin/jq -r '.seqid' "$out"` )
  set date = ( `/usr/local/bin/jq -r '.date' "$out"` )
  set last_total = ( `/usr/local/bin/jq -r '.total' "$out"` )
  if ($#seqid) then
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- SUCCESS retrieving seqid from device ($seqid)" >>! $TMP/LOG
    if ($seqid == "null" || $seqid == "") then
       set seqid = 0
    endif
  endif
else
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- fail ($url)" >>! $TMP/LOG
  set date = 0
  set seqid = 0
  set last_total = 0
endif
rm -f "$out"

# CHANGES target
set CHANGES = "/tmp/$0:t.$$.$device.$DATE.json"

#
# QUICK TEST
#
set update_seq = ( `curl -s -q -f -m 1 "$CU/$device" | /usr/local/bin/jq -r '.update_seq'` )
if ($#update_seq != 0 && $update_seq != "null") then
  if ($update_seq == $seqid) then
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- up-to-date ($seqid)" >>! $TMP/LOG
    goto done
  endif
endif

#
# get new CHANGES since last sequence (seqid from device-updates/<device>)
#
@ try = 0
set url = "$device/_changes?include_docs=true&since=$seqid"
set out = "/tmp/$0:t.$$.json"
set connect = 2 
set transfer = 30

again: # try again

if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- download _changes ($url)" >>! $TMP/LOG
/usr/bin/curl -s -q --connect-time $connect -m $transfer -f -L "$CU/$url" -o "$out" >>&! $TMP/LOG
if ($status != 22 && $status != 28 && -s "$out") then
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
  # get last sequence
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- $device -- changes downloaded" >>! $TMP/LOG
  set last_seq = `/usr/local/bin/jq -r '.last_seq' "$out"`
  if ($last_seq == $seqid) then
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- $device -- up-to-date ($seqid)" >>! $TMP/LOG
    goto done
  endif

  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- $device -- preprocessing into lines reversing order to LIFO" >>! $TMP/LOG
  /usr/local/bin/jq '{"results":.results|sort_by(.id)|reverse}' "$out" | /usr/local/bin/jq -c '.results[].doc' >! "$CHANGES"
  rm -f "$out"
  set total_changes = `/usr/bin/wc -l "$CHANGES" | /usr/bin/awk '{ print $1 }'`
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

# check if new events (or start-up == 0)
if ($total_changes == 0) then
  goto update
else
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- $total_changes EVENTS FOR $device ($seqid)" >>! $TMP/LOG
endif

# get IP address of device
set ipaddr = ( `/usr/bin/curl -s -q -f -L "$WWW/CGI/aah-devices.cgi" | /usr/local/bin/jq -r '.|select(.name=="'"$device"'")' | /usr/local/bin/jq -r ".ip_address"` )
if ($#ipaddr) then
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- FOUND $device :: $ipaddr" >>! $TMP/LOG
else
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- NOT FOUND $device" >>! $TMP/LOG
  goto done
endif

#
# PROCESS ALL CHANGES
#

@ idx = 1
@ nchange = 0
set changes = ()
set failures = ()

while ($idx <= $total_changes) 
  # get the change
  set change = ( `/usr/bin/tail +$idx "$CHANGES" | /usr/bin/head -1 | /usr/local/bin/jq '.'` )

  if ($#change == 0) then
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- BLANK CHANGE ($device @ $idx of $total_changes) in $CHANGES" >>! $TMP/LOG
    @ idx++
    continue
  endif

  set file = ( `/bin/echo "$change" | /usr/local/bin/jq -r '.visual.image'` )
  set scores = ( `/bin/echo "$change" | /usr/local/bin/jq '.visual.scores|sort_by(.score)'` )
  set class = ( `/bin/echo "$change" | /usr/local/bin/jq -r '.alchemy.text' | sed 's/ /_/g'` )
  set crop = ( `/bin/echo "$change" | /usr/local/bin/jq -r '.imagebox'` )
  set u = "$file:r"

  # test if all good
  if ($#file == 0 || $#scores == 0 || $#class == 0 || $#crop == 0) then
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- INVALID CHANGE ($device @ $idx of $total_changes) in $CHANGES -- $file $class $crop $scores -- $change" >>! $TMP/LOG
    @ idx++
    continue
  endif

  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- PROCESSING CHANGE ($device @ $idx of $total_changes) is $u" >>! $TMP/LOG

  @ idx++

  # test if event (<device>/$u) already processed into update (<device>-updates/$u)
  set url = "$device-$API/$u"
  set out = "/tmp/$0:t.$$.json"
  /usr/bin/curl -m 1 -s -q -f -L -H "Content-type: application/json" "$CU/$url" -o "$out" >>&! $TMP/LOG
  if ($status == 22 || $status == 28 || ! -s "$out") then
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- no existing update ($u)" >>&! $TMP/LOG
    rm -f "$out"
    unset idrev
  else
    set idrev = ( `/usr/local/bin/jq -r '._rev' "$out"` )
    if ($#idrev && $idrev != "null") then
      if ($?force == 0) then
        if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- BREAKING ($device) CHANGES: $nchange INDEX: $idx COUNT: $total_changes -- existing $u update ($idrev)" >>! $TMP/LOG
        rm -f "$out"
        break
      endif
      if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- WARNING -- EXISTING RECORD ($u) ($idrev)" >>! $TMP/LOG
    else
      unset idrev
    endif
    rm -f "$out"
  endif

  #
  # CALCULATE SCORING STATISTICS
  #

  set event = "/tmp/$0:t.$$.$u.csv"
  set stats = "/tmp/$0:t.$$.$u.stats.csv"
  set id = "/tmp/$0:t.$$.$u.json"

  # 1 create event scores CSV from JSON scores
  # 2 calculate base statistics across all classifications for each ID 
  #   a (1:"id",2:"class",3:"model",4:score)
  #   b (1:"id",2:"class",3:"model",4:score,5:count,6:min,7:max,8:sum,9:mean) 
  #   c (1:"id",2:"class",3:"model",4:score,5:count,6:min,7:max,8:sum,9:mean,10:stdev,11:kurtosis)
  # 3 sort by score
  # 4 choose top1
  /bin/echo "$scores" | /usr/local/bin/jq -j '.[]|"'"$u"'",",",.classifier_id,",",.name,",",.score,"\n"' | /usr/bin/sed 's/ /_/g' >! "$event"
  /usr/bin/awk -F, 'BEGIN { c=0;n=1;x=0;s=0; }{ if($4>0){if($4>x){x=$4};if($4<n){n=$4};c++;s+=$4}} END {m=s/c; printf("%s,%d,%f,%f,%f,%f\n",$1,c,n,x,s,m)}' "$event" >! "$stats"
  if (! -s "$stats") exit
  /usr/local/bin/csvjoin -H -c 1 "$event" "$stats" \
    | /usr/bin/tail +2 >! "$stats.$$"
  if (! -s "$stats.$$") exit
  /bin/mv -f "$stats.$$" "$stats"
  /usr/bin/awk -F, 'BEGIN  { v=0;vs=0;e=0 } { c=$5;n=$6;x=$7;s=$8;m=$9;if ($4>0){vs+=($4-m)^2;e+=($4-m)^4;v=vs/c}} END {sd=sqrt(v);k=e/vs^2; printf("%s,%d,%f,%f,%f,%f,%f,%f\n",$1,c,n,x,s,m,sd,k)}' "$stats" >! "$stats.$$"
  if (! -s "$stats.$$") exit
  /bin/mv -f "$stats.$$" "$stats"
  /usr/local/bin/csvjoin -H -c 1 "$event" "$stats" \
    | /usr/bin/tail +2 >! "$stats.$$"
  if (! -s "$stats.$$") exit
  /bin/mv -f "$stats.$$" "$stats"
  /usr/bin/sort -t, -k4,4 -nr "$stats" | /usr/bin/head -1 >! "$stats.$$"
  if (! -s "$stats.$$") exit
  /bin/mv -f "$stats.$$" "$stats"
  # get date in seconds since epoch
  set date = ( `/bin/echo "$change" | /usr/local/bin/jq -j '.year,",",.month,",",.day,",",.hour,",",.minute,",",.second' | /usr/local/bin/gawk -F, '{ t=mktime(sprintf("%4d %2d %2d %2d %2d %2d -1", $1, $2, $3, $4, $5, $6)); printf "%d\n", strftime("%s",t) }'` )
  /usr/bin/awk -F, '{printf"{\"date\":'"$date"',\"class\":\"%s\",\"model\":\"%s\",\"score\":%f,\"count\":%d,\"min\":%f,\"max\":%f,\"sum\":%f,\"mean\":%f,\"stdev\":%f,\"kurtosis\":%f}\n",$2,$3,$4,$5,$6,$7,$8,$9,$10,$11}' "$stats" >! "$id"

  # store in <device>-updates/<id>
  set url = "$device-$API/$u"
  if ($?idrev) then
    set url = "$url&rev=$idrev"
  endif
  /usr/bin/curl -s -q -f -L -H "Content-type: application/json" -X PUT "$CU/$url" -d "@$id" -o /tmp/curl.$$.json >>&! $TMP/LOG
  if ($status == 22 || $status == 28) then
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- PUT stats FAILURE ($device/$class/$u) :: " `cat /tmp/curl.$$.json` >>&! $TMP/LOG
    set failures = ( $failures $u )
  else
    # another successful change
    if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- PUT stats SUCCESS ($device/$class/$u) ($idx/$total_changes)" >>&! $TMP/LOG
    set changes = ( $changes $u )
    @ nchange++
  endif
  rm /tmp/curl.$$.json
  # cleanup
  rm -f "$event" "$stats" "$id"
end

if ($?failures) then
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- WARNING -- FAILURES ($failures)" >>! $TMP/LOG
endif

if ($?CHANGES) then
  rm -f "$CHANGES"
endif

update:

#
# UPDATE device-updates/<device> record
#

# start new record
set dev = '{'
if ($?last_seq) then
  set dev = "$dev"'"seqid":"'"$last_seq"'"'
else if ($?update_seq) then
  set dev = "$dev"'"seqid":"'"$update_seq"'"'
else
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- FAILURE (no sequence id)" >>&! $TMP/LOG
  goto done
endif

# calculate updated statistics
if ($?total_changes == 0) then
  set count = 0
else
  set count = $total_changes
endif
set total = ( $count )
if ($?devrev) then
  if ($?last_total) then
    if ($last_total != "null") @ total = $last_total + $total
  endif
endif
if ($?nchange) then
  set count = $nchange
endif
set dev = "$dev"',"count":'$count',"total":'$total',"date":'"$date"
if ($?failures) then
  if ($#failures) then
    set dev = "$dev"',"fail":null'
  else
    set dev = "$dev"',"fail":['
    foreach f ( $failures )
      set dev = "$dev"',"'"$f"'"'
    end
    set dev = "$dev"']'
  endif
endif
set dev = "$dev"'}'

# create output
/bin/echo "$dev" | /usr/local/bin/jq -c '.' >! "$OUTPUT.$$"
if (-s "$OUTPUT.$$") then
  mv -f "$OUTPUT.$$" "$OUTPUT"
else
  echo "FAIL"
  cat "$OUTPUT.$$"
  exit
endif

# specify target (& previous revision iff)
set url = "device-$API/$device"
if ($?devrev) then
  set url = "$url?rev=$devrev"
endif

if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- UPDATING $device ($url)" >>! $TMP/LOG

# update record
set put = ( `/usr/bin/curl -s -q -f -L -H "Content-type: application/json" -X PUT "$CU/$url" -d "@$OUTPUT" | /usr/local/bin/jq '.ok'` )
if ($put != "true") then
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- PUT $url failed returned " `cat /tmp/curl.$$.json` >>&! $TMP/LOG
else
endif

done:
if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- FINISH ($QUERY_STRING)"  >>! $TMP/LOG

cleanup:
rm -f "$OUTPUT.$$"
