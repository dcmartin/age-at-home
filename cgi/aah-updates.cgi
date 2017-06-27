#!/bin/csh -fb
setenv APP "aah"
setenv API "updates"
setenv LAN "192.168.1"
setenv WWW "$LAN".32
setenv DIGITS "$LAN".30
setenv WAN "www.dcmartin.com"
setenv TMP "/var/lib/age-at-home"

setenv DEBUG true

# don't update statistics more than once per (in seconds)
setenv TTL 5
setenv SECONDS `date "+%s"`
setenv DATE `/bin/echo $SECONDS \/ $TTL \* $TTL | bc`
# default image limit
if ($?IMAGE_LIMIT == 0) setenv IMAGE_LIMIT 100

if ($?QUERY_STRING) then
    set db = `/bin/echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
    set id = `/bin/echo "$QUERY_STRING" | sed 's/.*id=\([^&]*\).*/\1/'`
    if ($id == "$QUERY_STRING") unset id
    set force = `/bin/echo "$QUERY_STRING" | sed 's/.*force=\([^&]*\).*/\1/'`
    if ($force == "$QUERY_STRING") unset force
    set limit = `/bin/echo "$QUERY_STRING" | sed 's/.*limit=\([^&]*\).*/\1/'`
    if ($limit == "$QUERY_STRING") unset limit
endif

if ($?db == 0) set db = all
if ($?id && $db == "all") unset id
if ($?limit && $db == "all") then
  unset limit
else if ($?limit) then
  if ($limit > $IMAGE_LIMIT) set limit = $IMAGE_LIMIT
else
  set limit = $IMAGE_LIMIT
endif

# standardize QUERY_STRING (rendezvous w/ APP-make-API.csh script)
setenv QUERY_STRING "db=$db"

if ($?DEBUG) /bin/echo `date` "$0 $$ -- START ($QUERY_STRING)" >>! $TMP/LOG

# output target
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
if (-s "$OUTPUT") then
  goto output
endif
rm -f "$OUTPUT:r:r".*

#
# get read-only access to cloudant
#
if (-e ~$USER/.cloudant_url) then
    set cc = ( `cat ~$USER/.cloudant_url` )
    if ($#cc > 0) set CU = $cc[1]
    if ($#cc > 1) set CN = $cc[2]
    if ($#cc > 2) set CP = $cc[3]
    set CU = "$CN":"$CP"@"$CU"
endif
if ($?CU == 0) then
    /bin/echo `date` "$0 $$ -- no Cloudant URL" >>! $TMP/LOG
    goto done
endif

# handle singleton
if ($db != "all" && $?id) then
  set url = "$CU/$db-updates/$id"
  set out = "/tmp/$0:t.$$.json"
  /usr/bin/curl -s -q -f -m 1 -L "$url" -o "$out"
  if ($status == 22 || $status == 28 || ! -s "$out") then
    set output = '{"error":"not found","db":"'"$db"'","id":"'"$id"'"}'
  else
    set output = ( `/usr/local/bin/jq '.' "$out"` )
  endif
  rm -f "$out"
  goto output
endif

# handle singleton (deprecated)
if ($db != "all" && $?id) then
  set url = "$CU/$db/$id"
  set out = "/tmp/$0:t.$$.json"
  /usr/bin/curl -s -q -f -m 1 -L "$url" -o "$out"
  if ($status == 22 || $status == 28 || ! -s "$out") then
    set output = '{"error":"not found","db":"'"$db"'","id":"'"$id"'"}'
  else
    set epoch = ( `/usr/local/bin/jq -j '.year,",",.month,",",.day,",",.hour,",",.minute,",",.second' "$out" | /usr/local/bin/gawk '{ t=mktime(sprintf("%4d %2d %2d %2d %2d %2d", $1, $2, $3, $4, $5, $6)); printf "%d\n", strftime("%s",t) }'` )
    set output = ( `/usr/local/bin/jq '{"id":._id,"date":'"$epoch"',"scores":[.visual.scores?|sort_by(.score)|reverse[]|{"class":.classifier_id?,"model":.name?,"score":.score?}]}' "$out"` )
  endif
  rm -f "$out"
  goto output
endif

# find devices
if ($db == "all") then
  set devices = ( `curl "$WWW/CGI/aah-devices.cgi" | /usr/local/bin/jq -r '.name'` )
  if ($#devices == 0) then
    if ($?VERBOSE) /bin/echo `date` "$0 $$ ++ FAILURE ($url)" >>&! $TMP/LOG
    goto done
  endif
else
  set devices = ($db)
endif

if ($?VERBOSE) /bin/echo `date` "$0 $$ ++ SUCCESS -- devices ($devices)" >>&! $TMP/LOG
@ k = 0
set all = '{"date":'"$DATE"',"devices":['
foreach d ( $devices )

  if ($db == "all" || $d == "$db") then
    # initiate new output
    set qs = "$QUERY_STRING"
    setenv QUERY_STRING "device=$d"
    if ($?force) then
      setenv QUERY_STRING "$QUERY_STRING&force=true"
    endif
    if ($?DEBUG) /bin/echo `date` "$0 $$ ++ REQUESTING ./$APP-make-$API.bash ($QUERY_STRING)" >>! $TMP/LOG
    ./$APP-make-$API.bash
    setenv QUERY_STRING "$qs"
  endif

  # get device entry
  set url = "device-$API/$d"
  set out = "/tmp/$0:t.$$.json"
  curl -m 5 -s -q -f -L "$CU/$url" -o "$out"
  if ($status == 22 || $status == 28 || ! -s "$out") then
    if ($?VERBOSE) /bin/echo `date` "$0 $$ ++ FAILURE ($url) ($status)" >>&! $TMP/LOG
    rm -f "$out"
    continue
  endif
  set cd = `/usr/local/bin/jq -r '.date?' "$out"`; if ($cd == "null") set cd = 0
  set cc = `/usr/local/bin/jq -r '.count?' "$out"`; if ($cc == "null") set cc = 0
  set ct = `/usr/local/bin/jq -r '.total?' "$out"`; if ($ct == "null") set ct = 0
  if ($db != "all" && $d == "$db") then
    set url = "$db-updates/_all_docs?descending=true&limit=$limit"
    curl -s -q -f -L "$CU/$url" -o "$out"
    if ($status == 22 || $status == 28 || ! -s "$out") then
      if ($?VERBOSE) /bin/echo `date` "$0 $$ ++ FAILURE ($url) ($status)" >>&! $TMP/LOG
      echo '{"device":"'"$d"',","date":'"$cd"',"count":'"$cc"',"total":'"$ct"' }' >! "$OUTPUT"
    else
      set ids = ( `/usr/local/bin/jq '[.rows|(sort_by(.id)|reverse)[]?.id]' "$out"` )
      echo '{"device":"'"$d"',","date":'"$cd"',"count":'"$cc"',"total":'"$ct"',"limit":'"$limit"',"ids":'"$ids"' }' >! "$OUTPUT"
    endif
    rm -f "$out"
    goto output
  else if ($db == "all") then
    set json = '{"device":"'"$d"',","date":'"$cd"',"count":'"$cc"',"total":'"$ct"'}'
  else
    unset json
  endif
  if ($k) set all = "$all"','
  @ k++
  if ($?json) then
    set json = '{ "name":"'"$d"'","date":'"$cd"',"count":'"$cc"',"total":'"$ct"'}'
    set all = "$all""$json"
  endif
end
set all = "$all"']}'

/bin/echo "$all" | /usr/local/bin/jq -c '.' >! "$OUTPUT"

#
# output
#

output:

/bin/echo "Content-Type: application/json; charset=utf-8"
/bin/echo "Access-Control-Allow-Origin: *"

if ($?output == 0 && -s "$OUTPUT") then
  @ age = $SECONDS - $DATE
  /bin/echo "Age: $age"
  @ refresh = $TTL - $age
  # check back if using old
  if ($refresh < 0) @ refresh = $TTL
  /bin/echo "Refresh: $refresh"
  /bin/echo "Cache-Control: max-age=$TTL"
  /bin/echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
  /bin/echo ""
  /usr/local/bin/jq -c '.' "$OUTPUT"
 " if ($?VERBOSE) /bin/echo `date` "$0 $$ -- output ($OUTPUT) Age: $age Refresh: $refresh" >>! $TMP/LOG
else
  /bin/echo "Cache-Control: no-cache"
  /bin/echo "Last-Modified:" `date -r $SECONDS '+%a, %d %b %Y %H:%M:%S %Z'`
  /bin/echo ""
  if ($?output) then
    /bin/echo "$output"
  else
    /bin/echo '{ "error": "not found" }'
  endif
endif

# done

done:

if ($?DEBUG) /bin/echo `date` "$0 $$ -- FINISH ($QUERY_STRING)" >>! $TMP/LOG
