#!/bin/tcsh -b
setenv APP "aah"
setenv API "updates"

# setenv DEBUG true
setenv VERBOSE true

# environment
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
if ($?device == 0) set device = "lively-paper"

# standardize QUERY_STRING
setenv QUERY_STRING "device=$device"

if ($?DEBUG) echo `date` "$0:t $$ -- $device -- START ($QUERY_STRING)"  >>&! $LOGTO

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
        if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- PID $pid in-progress ($QUERY_STRING)" >>&! $LOGTO
        goto done
      else
        if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- removing $ip" >>&! $LOGTO
        rm -f "$ip"
      endif
    end
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- NO PROCESSES FOUND ($QUERY_STRING)" >>&! $LOGTO
else
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- NOTHING IN-PROGRESS ($QUERY_STRING)" >>&! $LOGTO
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
  echo `date` "$0:t $$ -- $device -- FAILURE: no Cloudant credentials" >>&! $LOGTO
  goto done
endif

#
# CREATE device-updates DATABASE 
#
if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- test if device exists (device-$API)" >>&! $LOGTO
set devdb = `curl -f -s -q -L -X GET "$CU/device-$API" | jq '.db_name'`
if ( $devdb == "" || "$devdb" == "null" ) then
  if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- creating device-$API" >>&! $LOGTO
  # create device
  set devdb = `curl -f -s -q -L -X PUT "$CU/device-$API" | jq '.ok'`
  # test for success
  if ( "$devdb" != "true" ) then
    # failure
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- failure creating Cloudant database (device-$API)" >>&! $LOGTO
    goto done
  else
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- success creating device (device-$API)" >>&! $LOGTO
  endif
else
  if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- DB device-$API exists" >>&! $LOGTO
endif

#
# CREATE <device>-updates DATABASE 
#
if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- test if exists ($device-$API)" >>&! $LOGTO
set devdb = `curl -f -s -q -L -X GET "$CU/$device-$API" | jq '.db_name'`
if ( $devdb == "" || "$devdb" == "null" ) then
  if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- creating $device-$API" >>&! $LOGTO
  # create device
  set devdb = `curl -f -s -q -L -X PUT "$CU/$device-$API" | jq '.ok'`
  # test for success
  if ( "$devdb" != "true" ) then
    # failure
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- failure creating Cloudant database ($device-$API)" >>&! $LOGTO
    goto done
  else
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- success creating device ($device-$API)" >>&! $LOGTO
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
  if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- FAILED retrieving for device $device; setting SEQID to zero" >>&! $LOGTO
  set seqid = 0
  set force = true
else
  set devrev = ( `jq -r '._rev' "$out"` )
  if ($#devrev == 0 || $devrev == "null") then
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- no previous revision ($devrev)" >>&! $LOGTO
    unset devrev
  endif
  set seqid = ( `jq -r '.seqid' "$out"` )
  if ($#seqid) then
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- SUCCESS retrieving SEQID from device $device" >>&! $LOGTO
    if ($seqid == "null" || $seqid == "") then
      if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- no previous SEQID ($seqid) for device $device; setting SEQID to zero" >>&! $LOGTO
      set seqid = 0
      set force = true
    else
      set prior_date = ( `jq -r '.date' "$out"` )
      set last_total = ( `jq -r '.total' "$out"` )
      if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- prior date ($prior_date); last total ($last_total)" >>&! $LOGTO
    endif
  else
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- no previous SEQID ($seqid) for device $device; setting SEQID to zero" >>&! $LOGTO
    set seqid = 0
    set force = true
  endif
endif
rm -f "$out"

# CHANGES target
set CHANGES = "/tmp/$0:t.$$.$device.$DATE.json"

#
# QUICK TEST
#
set update_seq = ( `curl -s -q "$CU/$device" | jq -r '.update_seq'` )
if ($#update_seq != 0 && $update_seq != "null") then
  if ($update_seq == $seqid) then
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- up-to-date ($seqid)" >>&! $LOGTO
    goto done
  endif
  if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- updating from SEQID: $update_seq" >>&! $LOGTO
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
set out = "/tmp/$0:t.$device.$$.json"
set trys = 3
set connect = 2
set transfer = 10

again: # try again

if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- download _changes ($url)" >>&! $LOGTO
curl -s -q --connect-time $connect -m $transfer -f -L "$CU/$url" -o "$out" >>&! $LOGTO
if ($status != 22 && $status != 28 && -s "$out") then
  # test JSON
  jq '.' "$out" >&! /dev/null
  set result = $status
  if ($result != 0) then
    rm -f "$out"
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- INVALID ($result) TRY ($try) TRANSFER ($transfer) CHANGES ($out)" >>&! $LOGTO
    if ($try < $trys) then
      @ transfer = $transfer + $transfer
      @ try++
      goto again
    else if ($try > $trys) then
      goto done
    else if ($?limit == 0) then
      set limit = 100000
      set url = "$url&descending=true&limit=$limit"
      @ try++
      if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- limiting results to last $limit results" >>&! $LOGTO
      goto again
    endif
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- download FAILED ($url)" >>&! $LOGTO
    goto done
  endif

  if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- changes downloaded ($out)" >>&! $LOGTO

  # get last sequence
  set last_seq = `jq -r '.last_seq' "$out"`
  if ($last_seq == $seqid) then
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- up-to-date ($seqid)" >>&! $LOGTO
    rm -f "$out"
    goto done
  endif

  if ($?limit == 0) then
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- processing" `jq '.results|length' "$out"` "results; reversing to LIFO order" >>&! $LOGTO
    jq '{"results":.results|sort_by(.id)|reverse}' "$out" | jq -c '.results[].doc' >! "$CHANGES"
    rm -f "$out"
  else
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- processing $limit results; already in LIFO order" >>&! $LOGTO
    jq '{"results":.results|sort_by(.id)}' "$out" | jq -c '.results[].doc' >! "$CHANGES"
    rm -f "$out"
  endif
  set download_total = `wc -l "$CHANGES" | awk '{ print $1 }'`
else
  # try again
  rm -f "$out"
  if ($try < $trys) then
    @ transfer = $transfer + $transfer
    @ try++
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- RETRY #$try transfer ($transfer) from ($url)" >>&! $LOGTO
    goto again
  else if ($try > $trys) then
    goto done
  else if ($?limit == 0) then
    set limit = 100
    set url = "$url&limit=$limit"
    @ try++
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- limiting results to last $limit results" >>&! $LOGTO
    goto again
  endif
  if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- download FAILED ($url)" >>&! $LOGTO
  goto done
endif


# check if new events (or start-up == 0)
if ($download_total == 0) then
  if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- zero records" >>&! $LOGTO
  goto done
else
  if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- downloaded $download_total records for device $device" >>&! $LOGTO
endif

###
### PROCESS ALL CHANGES (while)
###

@ idx = 1
@ update_total = 0
set changes = ()
set failures = ()

while ($idx <= $download_total) 

  # get the change
  set change = ( `tail -n +$idx "$CHANGES" | head -1 | jq '.'` )

  if ($#change == 0) then
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- BLANK CHANGE ($device @ $idx of $download_total) in $CHANGES" >>&! $LOGTO
    @ idx++
    continue
  endif

  set file = ( `echo "$change" | jq -r '.visual.image'` )
  set scores = ( `echo "$change" | jq '.visual.scores|sort_by(.score)'` )
  set class = ( `echo "$change" | jq -r '.alchemy.text' | sed 's/ /_/g'` )
  set imagebox = ( `echo "$change" | jq -r '.imagebox'` )
  set u = "$file:r"

  # test if all good
  if ($#file == 0 || $#scores == 0 || $#class == 0 || $#imagebox == 0) then
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- invalid change ($device @ $idx of $download_total) in $CHANGES -- $file $class $imagebox $scores -- $change" >>&! $LOGTO
    @ idx++
    continue
  endif

  if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- processing ($u) for device ($device); index $idx of $download_total" >>&! $LOGTO

  @ idx++

  # test if event (<device>/$u) already processed into update (<device>-updates/$u)
  set url = "$device-$API/$u"
  set out = "/tmp/$0:t.$$.$u.json"
  curl -m 1 -s -q -f -L -H "Content-type: application/json" "$CU/$url" -o "$out" >>&! $LOGTO
  if ($status == 22 || $status == 28 || ! -s "$out") then
    rm -f "$out"
    unset idrev
  else
    set idrev = ( `jq -r '._rev' "$out"` )
    if ($#idrev && $idrev != "null") then
      if ($?force == 0 && $?prior_date) then
        if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- stop processing $u ($idrev) at $idx for device ($device); changes: $update_total of $download_total" >>&! $LOGTO
        rm -f "$out"
        break
      else
        if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- continuing after existing record found ($u) ($idrev)" `jq -c '.' "$out"` >>&! $LOGTO
        set update_date = `jq -r '.date' "$out"`
        @ update_total++
      endif
    else
      unset idrev
    endif
    rm -f "$out"
  endif


# test if record processed previously
if ($?idrev) goto update

###
### CALCULATE SCORING STATISTICS
###
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
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- failed events (a)" >>&! $LOGTO
    exit
  else
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- made events (a): $event" >>&! $LOGTO
  endif

  # calculare count (c), min (n), max (x), sum (s) of events (1:"id",2:"class",3:"model",4:score)
  awk -F, 'BEGIN { c=0;n=1;x=0;s=0; }{ if($4>0){if($4>x){x=$4};if($4<n){n=$4};c++;s+=$4}} END {if(c!=0){m=s/c}else{m=0}; printf("%s,%d,%f,%f,%f,%f\n",$1,c,n,x,s,m)}' "$event" >! "$stats"
  if (! -s "$stats") then
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- failed statistics (a)" >>&! $LOGTO
    exit
  else
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- made statistics (a): $stats" >>&! $LOGTO
  endif

  # join events to statistics on first column (id)
  csvjoin -H -c 1 "$event" "$stats" | tail -n +2 >! "$stats.$$"
  if (! -s "$stats.$$") then
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- failed join (b)" >>&! $LOGTO
    exit
  else
    mv -f "$stats.$$" "$stats"
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- joined data (b)" >>&! $LOGTO
  endif

  # process joined data statistics (1:"id",2:"class",3:"model",4:score,5:count,6:min,7:max,8:sum,9:mean) 
  awk -F, 'BEGIN  { v=0;vs=0;e=0 } { c=$5;n=$6;x=$7;s=$8;m=$9;if ($4>0){vs+=($4-m)^2;e+=($4-m)^4;v=vs/c}} END {sd=sqrt(v);if(vs!=0){k=e/vs^2}else{k=0}; printf("%s,%d,%f,%f,%f,%f,%f,%f\n",$1,c,n,x,s,m,sd,k)}' "$stats" >! "$stats.$$"
  if (! -s "$stats.$$") then
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- failed statistics (b)" >>&! $LOGTO
    exit
  else
    mv -f "$stats.$$" "$stats"
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- made statistics (b)" >>&! $LOGTO
  endif

  # join events to statistics on first column (id)
  csvjoin -H -c 1 "$event" "$stats" | tail -n +2 >! "$stats.$$"
  if (! -s "$stats.$$") then
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- failed join (c)" >>&! $LOGTO
    exit
  else
    mv -f "$stats.$$" "$stats"
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- joined data (c)" >>&! $LOGTO
  endif

  # sort joined data (c) on score for highest value
  sort -t, -k4,4 -nr "$stats" | head -1 >! "$stats.$$"
  if (! -s "$stats.$$") then
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- failed sort (c)" >>&! $LOGTO
    exit
  else
    mv -f "$stats.$$" "$stats"
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- sorted data (c)" >>&! $LOGTO
  endif

  # get date in seconds since epoch
  
  set thisdate = ( `echo "$change" | jq -j '.year,"/",.month,"/",.day," ",.hour,":",.minute,":",.second'` )
  set thisdate = ( `$dateconv -f "%s" -i "%Y/%m/%d %H:%M:%S" "$thisdate"` )

##
## ADD/UPDATE <device>-updates RECORD for inference statistics
##

  # create JSON update record for event id
  awk -F, '{printf"{\"date\":'"$thisdate"',\"class\":\"%s\",\"model\":\"%s\",\"score\":%f,\"count\":%d,\"min\":%f,\"max\":%f,\"sum\":%f,\"mean\":%f,\"stdev\":%f,\"kurtosis\":%f}\n",$2,$3,$4,$5,$6,$7,$8,$9,$10,$11}' "$stats" >! "$id"

  # store in <device>-updates/<id>
  set url = "$device-$API/$u"
  if ($?idrev) then
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- updating device $device record $u ($idrev)" >>&! $LOGTO
    set url = "$url&rev=$idrev"
  endif
  # test if output was successfully created AND not updating a prior record due to force flag
  if (-s "$id") then
    curl -s -q -f -L -H "Content-type: application/json" -X PUT "$CU/$url" -d "@$id" -o /tmp/curl.$$.json >>&! $LOGTO
    if ($status == 22 || $status == 28) then
      if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- PUT stats FAILURE ($device/$class/$u)"  >>&! $LOGTO
      set failures = ( $failures $u )
    else
      # another successful change
      if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- PUT stats SUCCESS ($device/$class/$u) ($idx/$download_total)" >>&! $LOGTO
      set changes = ( $changes $u )
      @ update_total++
      set update_date = $thisdate
    endif
  else
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- no JSON for device $device record $u" >>&! $LOGTO
  endif
  rm -f /tmp/curl.$$.json
  # cleanup
  rm -f "$event" "$stats" "$id"
  
###
### UPDATE device-updates RECORD for processed updates
###
update:


  ## UPDATE device-updates/<device> every 10 records (and on last record)
  if ($update_total % 10 == 0 || $idx == $download_total ) then
    if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- updating device-updates at record $idx ($update_total) of $download_total" >>&! $LOGTO

    # calculate progress
    if ($?last_total) then
      @ last_total += $update_total
    else 
      @ last_total = $update_total
    endif

    # start new JSON
    set dev = '{"seqid":"'"$update_seq"'","count":'$update_total',"total":'$last_total',"date":'$update_date',"failures":'
    if ($?failures) then
      set dev = "$dev"'['`echo "$failures" | sed "s/ /,/g"`']'
    else
      set dev = "$dev"'null'
    endif
    # finish new JSON
    set dev = "$dev"'}'

    # create output
    echo "$dev" | jq '.' >! "$OUTPUT"
    if ($status == 0 && -s "$OUTPUT") then
      if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- created $OUTPUT " `jq -c '.' "$OUTPUT"` >>&! $LOGTO
    else
      if ($?DEBUG) echo `date` "$0:t $$ -- $device -- failed to create $OUTPUT" >>&! $LOGTO
      goto done
    endif

    # specify target (& previous revision iff)
    set url = "device-updates/$device"
    curl -q -s -L "$CU/$url" -o "$out"
    set devrev = ( `jq -r '._rev' "$out"` )
    if ($#devrev && $devrev != "null" && "$devrev" != "") then
      set url = "$url?rev=$devrev"
    endif
    # update record
    set out = "$TMP/$0:t.$device.$$.json"
    curl -o "$out" -s -q -L -H "Content-type: application/json" -X PUT "$CU/$url" -d "@$OUTPUT"
    set put = ( `jq '.ok' "$out"` )
    if ($put != "true") then
      if ($?DEBUG) echo `date` "$0:t $$ -- $device -- FAILED to write to $url" `jq -c '.' "$out"` `cat "$OUTPUT"` >>&! $LOGTO
    else
      if ($?VERBOSE) echo `date` "$0:t $$ -- $device -- SUCCESS writing to $url" `jq -c '.' "$OUTPUT"` >>&! $LOGTO
    endif
    rm -f "$out" "$OUTPUT"
  endif

### COMPLETE while

end


###
### DONE
###
done:

if ($?CHANGES) then
  rm -f "$CHANGES"
endif

if ($?DEBUG) echo `date` "$0:t $$ -- $device -- FINISH ($QUERY_STRING)" >>&! $LOGTO

###
### CLEANUP
###

cleanup:
rm -f "$OUTPUT.$$"
