#!/bin/tcsh -b
setenv APP "aah"
setenv API "updates"

# debug on/off
setenv DEBUG true
# setenv VERBOSE true

# environment
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"
if ($?CREDENTIALS == 0) setenv CREDENTIALS /usr/local/etc
if ($?LOGTO == 0) setenv LOGTO /dev/stderr

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

if ($?TTL == 0) set TTL = 60
if ($?SECONDS == 0) set SECONDS = `date "+%s"`
if ($?DATE == 0) set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

# transform image
setenv CAMERA_MODEL_TRANSFORM "CROP"
# do not force continued attempts after failure when processing images

if ($?QUERY_STRING) then
    set device = `echo "$QUERY_STRING" | sed 's/.*device=\([^&]*\).*/\1/'`
    if ($device == "$QUERY_STRING") unset device
    set force = `echo "$QUERY_STRING" | sed 's/.*force=\([^&]*\).*/\1/'`
    if ($force == "$QUERY_STRING") unset force
    set limit = `echo "$QUERY_STRING" | sed 's/.*limit=\([^&]*\).*/\1/'`
    if ($limit == "$QUERY_STRING") unset limit
endif

# DEFAULTS to quiet-water
if ($?device == 0) set device = "quiet-water"

# standardize QUERY_STRING
setenv QUERY_STRING "device=$device"

if ($?DEBUG) echo `date` "$0:t $$ -- START ($QUERY_STRING)"  >>&! $LOGTO

# OUTPUT target
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

if (-s "$OUTPUT") goto done

##
## SINGLE THREADED (by QUERY_STRING)
##
set INPROGRESS = ( `echo "$OUTPUT".*` )
if ($#INPROGRESS) then
    foreach ip ( $INPROGRESS )
      set pid = $ip:e
      set eid = ( `ps axw | awk '{ print $1 }' | egrep "$pid"` )
      if ($pid == $eid) then
        if ($?DEBUG) echo `date` "$0:t $$ -- PID $pid in-progress ($QUERY_STRING)" >>&! $LOGTO
        goto done
      else
        if ($?DEBUG) echo `date` "$0:t $$ -- removing $ip" >>&! $LOGTO
        rm -f "$ip"
      endif
    end
    if ($?VERBOSE) echo `date` "$0:t $$ -- NO PROCESSES FOUND ($QUERY_STRING)" >>&! $LOGTO
else
    if ($?VERBOSE) echo `date` "$0:t $$ -- NOTHING IN-PROGRESS ($QUERY_STRING)" >>&! $LOGTO
endif
# remove all old files for this device (drop .$DATE.json)
rm -f "$OUTPUT:r:r".*

##
## PREPARE TO PROCESS
##
# start output
touch "$OUTPUT".$$
# cleanup if interrupted
onintr cleanup

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
  echo `date` "$0:t $$ -- FAILURE: no Cloudant credentials" >>& $LOGTO
  goto done
endif

#
# CREATE device-updates DATABASE 
#
if ($?VERBOSE) echo `date` "$0:t $$ -- test if device exists (device-$API)" >>&! $LOGTO
set devdb = `curl -f -s -q -L -X GET "$CU/device-$API" | jq '.db_name'`
if ( $devdb == "" || "$devdb" == "null" ) then
  if ($?VERBOSE) echo `date` "$0:t $$ -- creating device-$API" >>&! $LOGTO
  # create device
  set devdb = `curl -f -s -q -L -X PUT "$CU/device-$API" | jq '.ok'`
  # test for success
  if ( "$devdb" != "true" ) then
    # failure
    if ($?VERBOSE) echo `date` "$0:t $$ -- failure creating Cloudant database (device-$API)" >>&! $LOGTO
    goto done
  else
    if ($?VERBOSE) echo `date` "$0:t $$ -- success creating device (device-$API)" >>&! $LOGTO
  endif
else
  if ($?VERBOSE) echo `date` "$0:t $$ -- DB device-$API exists" >>&! $LOGTO
endif

#
# CREATE <device>-updates DATABASE 
#
if ($?VERBOSE) echo `date` "$0:t $$ -- test if exists ($device-$API)" >>&! $LOGTO
set devdb = `curl -f -s -q -L -X GET "$CU/$device-$API" | jq '.db_name'`
if ( $devdb == "" || "$devdb" == "null" ) then
  if ($?VERBOSE) echo `date` "$0:t $$ -- creating $device-$API" >>&! $LOGTO
  # create device
  set devdb = `curl -f -s -q -L -X PUT "$CU/$device-$API" | jq '.ok'`
  # test for success
  if ( "$devdb" != "true" ) then
    # failure
    if ($?VERBOSE) echo `date` "$0:t $$ -- failure creating Cloudant database ($device-$API)" >>&! $LOGTO
    goto done
  else
    if ($?VERBOSE) echo `date` "$0:t $$ -- success creating device ($device-$API)" >>&! $LOGTO
  endif
endif

##
## GET device-updates/<device> (2 second connect; 30 second transfer; no retry)
##
set url = "device-$API/$device"
set out = "/tmp/$0:t.$$.json"
set connect = 2
set transfer = 30
curl --connect-time $connect -m $transfer -f -q -s -L "$CU/$url" -o "$out"
if ($status == 22 || $status == 28 || ! -s "$out") then
  if ($?DEBUG) echo `date` "$0:t $$ -- FAILED retrieving for device $device; setting SEQID to zero" >>&! $LOGTO
  set seqid = 0
  set date = 0
  set last_total = 0 
else
  set devrev = ( `jq -r '._rev' "$out"` )
  if ($#devrev == 0 || $devrev == "null") then
    if ($?DEBUG) echo `date` "$0:t $$ -- no previous revision ($devrev)" >>&! $LOGTO
    unset devrev
  endif
  set seqid = ( `jq -r '.seqid' "$out"` )
  if ($#seqid) then
    if ($seqid == "null" || $seqid == "") then
      if ($?DEBUG) echo `date` "$0:t $$ -- no previous SEQID ($seqid) for device $device; setting SEQID to zero" >>&! $LOGTO
      set seqid = 0
    else
      if ($?DEBUG) echo `date` "$0:t $$ -- SUCCESS retrieving seqid from device ($seqid)" >>&! $LOGTO
    endif
  else
      if ($?DEBUG) echo `date` "$0:t $$ -- no previous SEQID ($seqid) for device $device; setting SEQID to zero" >>&! $LOGTO
    set seqid = 0
  endif
  set date = ( `jq -r '.date' "$out"` )
  set last_total = ( `jq -r '.total' "$out"` )
  if ($?DEBUG) echo `date` "$0:t $$ -- prior date ($date); last total ($last_total)" >>&! $LOGTO
endif
rm -f "$out"

# CHANGES target
set CHANGES = "/tmp/$0:t.$$.$device.$DATE.json"

#
# QUICK TEST
#
set update_seq = ( `curl -s -q -f -m 1 "$CU/$device" | jq -r '.update_seq'` )
if ($#update_seq != 0 && $update_seq != "null") then
  if ($update_seq == $seqid) then
    if ($?DEBUG) echo `date` "$0:t $$ -- up-to-date ($seqid)" >>&! $LOGTO
    goto done
  endif
  if ($?DEBUG) echo `date` "$0:t $$ -- updating from SEQID: $update_seq" >>&! $LOGTO
endif

#
# get new CHANGES since last sequence (seqid from device-updates/<device>)
#
@ try = 0
if ($?limit) then
  set url = "$device/_changes?include_docs=true&since=$seqid&descending=true&limit=$limit"
else
  set url = "$device/_changes?include_docs=true&since=$seqid"
endif
set out = "/tmp/$0:t.$$.json"
set trys = 3
set connect = 2
set transfer = 10

again: # try again

if ($?DEBUG) echo `date` "$0:t $$ -- download _changes ($url)" >>&! $LOGTO
curl -s -q --connect-time $connect -m $transfer -f -L "$CU/$url" -o "$out" >>&! $LOGTO
if ($status != 22 && $status != 28 && -s "$out") then
  # test JSON
  jq '.' "$out" >&! /dev/null
  set result = $status
  if ($result != 0) then
    rm -f "$out"
    if ($?DEBUG) echo `date` "$0:t $$ -- INVALID ($result) TRY ($try) TRANSFER ($transfer) CHANGES ($out)" >>&! $LOGTO
    if ($try < $trys) then
      @ transfer = $transfer + $transfer
      @ try++
      goto again
    else if ($try > $trys) then
      goto done
    else if ($?limit == 0) then
      set limit = 1000
      set url = "$url&descending=true&limit=$limit"
      @ try++
      if ($?DEBUG) echo `date` "$0:t $$ -- limiting results to last $limit results" >>&! $LOGTO
      goto again
    endif
    if ($?DEBUG) echo `date` "$0:t $$ -- download FAILED ($url)" >& $LOGTO
    goto done
  endif

  if ($?DEBUG) echo `date` "$0:t $$ -- $device -- changes downloaded ($out)" >>&! $LOGTO

  # get last sequence
  set last_seq = `jq -r '.last_seq' "$out"`
  if ($last_seq == $seqid) then
    if ($?DEBUG) echo `date` "$0:t $$ -- $device -- up-to-date ($seqid)" >>&! $LOGTO
    rm -f "$out"
    goto done
  endif

  if ($?limit == 0) then
    if ($?DEBUG) echo `date` "$0:t $$ -- $device -- processing" `jq '.results|length' "$out"` "results; reversing to LIFO order" >>&! $LOGTO
    jq '{"results":.results|sort_by(.id)|reverse}' "$out" | jq -c '.results[].doc' >! "$CHANGES"
    rm -f "$out"
  else
    if ($?DEBUG) echo `date` "$0:t $$ -- $device -- processing $limit results; already in LIFO order" >>&! $LOGTO
    jq '{"results":.results|sort_by(.id)}' "$out" | jq -c '.results[].doc' >! "$CHANGES"
    rm -f "$out"
  endif
  set total_changes = `wc -l "$CHANGES" | awk '{ print $1 }'`
else
  # try again
  rm -f "$out"
  if ($try < $trys) then
    @ transfer = $transfer + $transfer
    @ try++
    if ($?DEBUG) echo `date` "$0:t $$ -- RETRY #$try transfer ($transfer) from ($url)" >& $LOGTO
    goto again
  else if ($try > $trys) then
    goto done
  else if ($?limit == 0) then
    set limit = 1000
    set url = "$url&limit=$limit"
    @ try++
    if ($?DEBUG) echo `date` "$0:t $$ -- limiting results to last $limit results" >>&! $LOGTO
    goto again
  endif
  if ($?DEBUG) echo `date` "$0:t $$ -- download FAILED ($url)" >& $LOGTO
  goto done
endif

if ($?DEBUG) echo `date` "$0:t $$ -- $total_changes EVENTS FOR $device ($seqid)" >& $LOGTO

# check if new events (or start-up == 0)
if ($total_changes == 0) then
  goto update
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
  set change = ( `tail -n +$idx "$CHANGES" | head -1 | jq '.'` )

  if ($#change == 0) then
    if ($?DEBUG) echo `date` "$0:t $$ -- BLANK CHANGE ($device @ $idx of $total_changes) in $CHANGES" >& $LOGTO
    @ idx++
    continue
  endif

  set file = ( `echo "$change" | jq -r '.visual.image'` )
  set scores = ( `echo "$change" | jq '.visual.scores|sort_by(.score)'` )
  set class = ( `echo "$change" | jq -r '.alchemy.text' | sed 's/ /_/g'` )
  set crop = ( `echo "$change" | jq -r '.imagebox'` )
  set u = "$file:r"

  # test if all good
  if ($#file == 0 || $#scores == 0 || $#class == 0 || $#crop == 0) then
    if ($?DEBUG) echo `date` "$0:t $$ -- INVALID CHANGE ($device @ $idx of $total_changes) in $CHANGES -- $file $class $crop $scores -- $change" >& $LOGTO
    @ idx++
    continue
  endif

  if ($?VERBOSE) echo `date` "$0:t $$ -- PROCESSING CHANGE ($device @ $idx of $total_changes) is $u" >& $LOGTO

  @ idx++

  # test if event (<device>/$u) already processed into update (<device>-updates/$u)
  set url = "$device-$API/$u"
  set out = "/tmp/$0:t.$$.json"
  curl -m 1 -s -q -f -L -H "Content-type: application/json" "$CU/$url" -o "$out" >>&! $LOGTO
  if ($status == 22 || $status == 28 || ! -s "$out") then
    if ($?VERBOSE) echo `date` "$0:t $$ -- GOOD: no existing update ($u)" >>&! $LOGTO
    rm -f "$out"
    unset idrev
  else
    set idrev = ( `jq -r '._rev' "$out"` )
    if ($#idrev && $idrev != "null") then
      if ($?force == 0) then
        if ($?DEBUG) echo `date` "$0:t $$ -- STOPPING ($device) CHANGES: $nchange INDEX: $idx COUNT: $total_changes -- existing $u update ($idrev)" >& $LOGTO
        rm -f "$out"
        break
      else
        if ($?DEBUG) echo `date` "$0:t $$ -- FORCING -- EXISTING RECORD ($u) ($idrev)" >& $LOGTO
      endif
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

  # breakdownscore data into individual records 
  echo "$scores" | jq -r -j '.[]|"'"$u"'",",",.classifier_id,",",.name,",",.score,"\n"' | sed 's/ /_/g' >! "$event"
  if (! -s "$event") then
    if ($?VERBOSE) echo `date` "$0:t $$ -- failed events (a)" >& $LOGTO
    exit
  else
    if ($?VERBOSE) echo `date` "$0:t $$ -- made events (a): $event" >& $LOGTO
  endif

  # calculare count (c), min (n), max (x), sum (s) of events (1:"id",2:"class",3:"model",4:score)
  awk -F, 'BEGIN { c=0;n=1;x=0;s=0; }{ if($4>0){if($4>x){x=$4};if($4<n){n=$4};c++;s+=$4}} END {if(c!=0){m=s/c}else{m=0}; printf("%s,%d,%f,%f,%f,%f\n",$1,c,n,x,s,m)}' "$event" >! "$stats"
  if (! -s "$stats") then
    if ($?VERBOSE) echo `date` "$0:t $$ -- failed statistics (a)" >& $LOGTO
    exit
  else
    if ($?VERBOSE) echo `date` "$0:t $$ -- made statistics (a): $stats" >& $LOGTO
  endif

  # join events to statistics on first column (id)
  csvjoin -H -c 1 "$event" "$stats" | tail -n +2 >! "$stats.$$"
  if (! -s "$stats.$$") then
    if ($?VERBOSE) echo `date` "$0:t $$ -- failed join (b)" >& $LOGTO
    exit
  else
    mv -f "$stats.$$" "$stats"
    if ($?VERBOSE) echo `date` "$0:t $$ -- joined data (b)" >& $LOGTO
  endif

  # process joined data statistics (1:"id",2:"class",3:"model",4:score,5:count,6:min,7:max,8:sum,9:mean) 
  awk -F, 'BEGIN  { v=0;vs=0;e=0 } { c=$5;n=$6;x=$7;s=$8;m=$9;if ($4>0){vs+=($4-m)^2;e+=($4-m)^4;v=vs/c}} END {sd=sqrt(v);if(vs!=0){k=e/vs^2}else{k=0}; printf("%s,%d,%f,%f,%f,%f,%f,%f\n",$1,c,n,x,s,m,sd,k)}' "$stats" >! "$stats.$$"
  if (! -s "$stats.$$") then
    if ($?VERBOSE) echo `date` "$0:t $$ -- failed statistics (b)" >& $LOGTO
    exit
  else
    mv -f "$stats.$$" "$stats"
    if ($?VERBOSE) echo `date` "$0:t $$ -- made statistics (b)" >& $LOGTO
  endif

  # join events to statistics on first column (id)
  csvjoin -H -c 1 "$event" "$stats" | tail -n +2 >! "$stats.$$"
  if (! -s "$stats.$$") then
    if ($?VERBOSE) echo `date` "$0:t $$ -- failed join (c)" >& $LOGTO
    exit
  else
    mv -f "$stats.$$" "$stats"
    if ($?VERBOSE) echo `date` "$0:t $$ -- joined data (c)" >& $LOGTO
  endif

  # sort joined data (c) on score for highest value
  sort -t, -k4,4 -nr "$stats" | head -1 >! "$stats.$$"
  if (! -s "$stats.$$") then
    if ($?VERBOSE) echo `date` "$0:t $$ -- failed sort (c)" >& $LOGTO
    exit
  else
    mv -f "$stats.$$" "$stats"
    if ($?VERBOSE) echo `date` "$0:t $$ -- sorted data (c)" >& $LOGTO
  endif

  # get date in seconds since epoch
  
  set date = ( `echo "$change" | jq -j '.year,"/",.month,"/",.day," ",.hour,":",.minute,":",.second'` )
  set date = ( `$dateconv -f "%s" -i "%Y/%m/%d %H:%M:%S" "$date"` )

  # create JSON update record for event id
  awk -F, '{printf"{\"date\":'"$date"',\"class\":\"%s\",\"model\":\"%s\",\"score\":%f,\"count\":%d,\"min\":%f,\"max\":%f,\"sum\":%f,\"mean\":%f,\"stdev\":%f,\"kurtosis\":%f}\n",$2,$3,$4,$5,$6,$7,$8,$9,$10,$11}' "$stats" >! "$id"

  # store in <device>-updates/<id>
  set url = "$device-$API/$u"
  if ($?idrev) then
    set url = "$url&rev=$idrev"
  endif
  if (-s "$id") then
    curl -s -q -f -L -H "Content-type: application/json" -X PUT "$CU/$url" -d "@$id" -o /tmp/curl.$$.json >>&! $LOGTO
    if ($status == 22 || $status == 28) then
      if ($?DEBUG) echo `date` "$0:t $$ -- PUT stats FAILURE ($device/$class/$u)"  >>&! $LOGTO
      set failures = ( $failures $u )
    else
      # another successful change
      if ($?DEBUG) echo `date` "$0:t $$ -- PUT stats SUCCESS ($device/$class/$u) ($idx/$total_changes)" >>&! $LOGTO
      set changes = ( $changes $u )
      @ nchange++
    endif
  endif
  rm -f /tmp/curl.$$.json
  # cleanup
  rm -f "$event" "$stats" "$id"

end

if ($?failures) then
  if ($?DEBUG) echo `date` "$0:t $$ -- WARNING -- FAILURES ($failures)" >& $LOGTO
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
  if ($?VERBOSE) echo `date` "$0:t $$ -- FAILURE (no sequence id)" >>&! $LOGTO
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
    set dev = "$dev"`echo "$failures" | sed "s/ /,/"`']'
  endif
endif
set dev = "$dev"'}'

# create output
echo "$dev" | jq -c '.' >! "$OUTPUT.$$"

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

if ($?DEBUG) echo `date` "$0:t $$ -- UPDATING $device ($url)" >& $LOGTO

# update record
set put = ( `curl -s -q -f -L -H "Content-type: application/json" -X PUT "$CU/$url" -d "@$OUTPUT" | jq '.ok'` )
if ($put != "true") then
  if ($?VERBOSE) echo `date` "$0:t $$ -- PUT $url failed returned " `cat /tmp/curl.$$.json` >>&! $LOGTO
else
endif

done:
if ($?DEBUG) echo `date` "$0:t $$ -- FINISH ($QUERY_STRING)" >& $LOGTO

cleanup:
rm -f "$OUTPUT.$$"
