#!/bin/tcsh -b
setenv APP "aah"
setenv API "images"

# setenv DEBUG true
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

# don't update statistics more than once per (in seconds)
setenv TTL 300
setenv SECONDS `date "+%s"`
setenv DATE `echo $SECONDS \/ $TTL \* $TTL | bc`

# default image limit
if ($?IMAGE_LIMIT == 0) setenv IMAGE_LIMIT 10000
if ($?IMAGE_SET_LIMIT == 0) setenv IMAGE_SET_LIMIT 100

if ($?QUERY_STRING) then
    set db = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
    # set class = `echo "$QUERY_STRING" | sed 's/.*class=\([^&]*\).*/\1/'`
    # if ($class == "$QUERY_STRING") unset class
    set id = `echo "$QUERY_STRING" | sed 's/.*id=\([^&]*\).*/\1/'`
    if ($id == "$QUERY_STRING") unset id
    set ext = `echo "$QUERY_STRING" | sed 's/.*ext=\([^&]*\).*/\1/'`
    if ($ext == "$QUERY_STRING") unset ext
    set since = `echo "$QUERY_STRING" | sed 's/.*since=\([^&]*\).*/\1/'`
    if ($since == "$QUERY_STRING") unset since
    set limit = `echo "$QUERY_STRING" | sed 's/.*limit=\([^&]*\).*/\1/'`
    if ($limit == "$QUERY_STRING") unset limit
    set force = `echo "$QUERY_STRING" | sed 's/.*force=\([^&]*\).*/\1/'`
    if ($force == "$QUERY_STRING") unset force
endif

if ($?db == 0 && $?id) unset id
if ($?since && $?id) unset id
if ($?db == 0) set db = all

if ($?limit && $db == "all") then
  unset limit
else if ($?limit) then
  if ($limit > $IMAGE_LIMIT) set limit = $IMAGE_LIMIT
endif

if ($?DEBUG) echo `date` "$0 $$ -- $db -- START" >>&! $LOGTO

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

# find devices
if ($db == "all") then
  set url = "$HTTP_HOST/CGI/aah-devices.cgi"
  set devices = ( `curl -s -q -L "$url" | jq -r '.devices[].name'` )
  if ($#devices == 0) then
    if ($?DEBUG) echo `date` "$0 $$ -- FAILURE: cannot find devices" >>&! $LOGTO
    goto done
  endif
else
  set devices = ($db)
endif

if ($?VERBOSE) echo `date` "$0 $$ ++ SUCCESS -- devices ($devices)" >>&! $LOGTO

# check all devices
foreach d ( $devices )
  if ($db == "$d") then
    # get time of last update from device (should be a local call)
    set last_update_check = ( `curl -s -q -f -L "$CU/$d/_all_docs?include_docs=true&descending=true&limit=1" | jq -j '.rows[].doc|.year,"/",.month,"/",.day," ",.hour,":",.minute,":",.second' | $dateconv -f '%s' -i '%Y/%m/%d %H:%M:%S'` )
    if ($#last_update_check == 0 || $last_update_check == "null" ) then
      if ($?DEBUG) echo `date` "$0 $$ -- $d -- WARNING: cannot determine last_update_check; using $DATE" >>&! $LOGTO
      set last_update_check = $DATE
    endif
    set last_image_check = ( `curl -s -q -f -L "$CU/$db-$API/_all_docs?include_docs=true&descending=true&limit=1" | jq -r '.rows[].doc.date'` )
    if ($#last_image_check == 0 || $last_image_check == "null") then
      if ($?DEBUG) echo `date` "$0 $$ -- $d -- WARNING: cannot determine last_update_check; using zero" >>&! $LOGTO
      set last_image_check = 0
    endif
    @ delay = $last_update_check - $last_image_check
    if ($delay > $TTL) then
      # initiate new output
      set qs = "$QUERY_STRING"
      setenv QUERY_STRING "device=$d"
      # unimplemented
      if ($?force) then
        setenv QUERY_STRING "$QUERY_STRING&force=true"
      endif
      if ($?DEBUG) echo `date` "$0 $$ ++ DELAY ($delay) -- REQUESTING ./$APP-make-$API.bash ($QUERY_STRING)" >>&! $LOGTO
      ./$APP-make-$API.bash
      setenv QUERY_STRING "$qs"
    endif
    set found = "$d"
    break
  endif
end

if ($db != "all") then
  if ($?found == 0) then
    set output = '{"error":"not found","db":"'"$db"'"}'
    goto output
  endif
  set devices = ( $db )
endif

# test if singleton requested
if ($db != "all" && ( $?id || $?limit )) then
  if ($?id) then
    set singleton = true
  else if ($?limit) then
    if ($limit == 1) set singleton = true
  else
    # not a singleton request
    unset singleton
  endif
endif

# define OUTPUT
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

###
### HANDLE SINGLETON
###

if ($?singleton) then
  if ($?id) then
    set url = "$db-$API/$id"
  else if ($?limit) then
    set url = "$db-$API/_all_docs?include_docs=true&descending=true&limit=$limit"
  endif
  set out = "/tmp/$0:t.$$.json"
  curl -s -q -f -L "$CU/$url" -o "$out"
  if ($status == 22 || $status == 28 || ! -s "$out") then
    rm -f "$out"
    if ($?id) then
      set output = '{"error":"not found","db":"'"$db"'","id":"'"$id"'"}'
      goto output
    else if ($?limit)
      set output = '{"error":"not found","db":"'"$db"'","limit":"'"$limit"'"}'
      goto output
    else
      # should never happen
      set output = '{"error":"not found","db":"'"$db"'"}'
      goto output
    endif
  endif
  # one result only
  if ($?limit) then
    set json = ( `jq '.rows[].doc' "$out"` )
  else
    set json = ( `jq '.' "$out"` )
  endif
  # clean-up
  /bin/rm -f "$out"

  # test if non-image (i.e. json) requested
  if ($?ext == 0) then
    echo "$json" | jq '{"id":._id,"date":.date,"imagebox":.imagebox}'  >! "$OUTPUT"
    goto output
  else
    set dirpath = `echo "$json" | jq -r '.path'` 
  endif

  # find original
  if ($ext == "full") set imgpath = "$AAHDIR/$dirpath/$id.jpg"
  if ($ext == "crop") set imgpath = "$AAHDIR/$dirpath/$id.jpeg"
  if (-s "$imgpath") then
    if ($?DEBUG) echo `date` "$0 $$ -- SINGLETON ($imgpath)" >>&! $LOGTO
    echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
    echo "Access-Control-Allow-Origin: *"
    echo "Content-Location: $HTTP_HOST/CGI/$APP-$API.cgi?db=$db&id=$id&ext=$ext"
    echo "Content-Type: image/jpeg"
    echo ""
    # dump image
    dd if="$imgpath" of=/dev/stdout
    # ./aah-images-label.csh "$imgpath" "$class" "$imagebox"
    goto done
  endif
  set output = '{"error":"not found","db":"'"$db"'","id":"'"$id"'"}'
  goto output
endif

###
### HANDLE MULTIPLE (ALWAYS JSON)
###

@ k = 0
set all = '{"date":'"$DATE"',"devices":['
# handle all (json)
foreach d ( $devices )
  # get most recent image available
  set url = "$CU/$d-$API/_all_docs?include_docs=true&descending=true&limit=1"
  set out = "/tmp/$0:t.$$.json"
  curl -s -q -f -L "$url" -o "$out"
  if ($status != 22 && -s "$out") then
    set lid = ( `jq '.rows[].doc.date' "$out"` )
    set total_rows = ( `jq '.total_rows' "$out"` )
    /bin/rm -f "$out"
    if ($#lid == 0 || $lid == "null") set lid = 0
    if ($#total_rows == 0 || $total_rows == "null") set total_rows = 0
  else
    if ($?DEBUG) echo `date` "$0 $$ -- $d -- cannot find last image; continuing..." >>&! $LOGTO
    /bin/rm -f "$out"
    continue
  endif

  if ($?VERBOSE) echo `date` "$0 $$ -- $d -- total images: $total_rows; last update: $lid" >>&! $LOGTO

  # process this db
  if ($db != "all" && $d == "$db") then
    # get recent rows
    set url = "$CU/$d-$API/_all_docs?include_docs=true&descending=true&limit=$IMAGE_LIMIT"
    set out = "/tmp/$0:t.$d.$$.json"
    curl -s -q -f  -L "$url" -o "$out"
    if ($status == 22 || $status == 28 || ! -s "$out") then
      /bin/rm -f "$out"
      if ($?DEBUG) echo `date` "$0 $$ -- $d -- cannot find any images; continuing..." >>&! $LOGTO
      set output = '{"error":"failure","db":"'"$d-$API"'}'
      continue
    endif
    # select subset based on limit specified and date
    if ($?limit && $?since) then
      set ids = ( `jq '[limit('"$limit"';.rows?|sort_by(.id)|reverse[].doc|select(.date>'"$since"')._id]' "$out"` )
      set len = ( `echo "$ids" | jq '.|length'` )
      set output = '{"name":"'"$d"'","date":'"$since"',"count":'"$len"',"total":'"$total_rows"',"limit":'"$limit"',"ids":'"$ids"' }'
      if ($?DEBUG)  echo `date` "$0:t $$ -- found $len ids since $since w/ limit $limit" >>&! $LOGTO
    else if ($?limit) then
      set ids = ( `jq '[limit('"$limit"';.rows?|sort_by(.id)|reverse[].doc|._id)]' "$out"` )
      set len = ( `echo "$ids" | jq '.|length'` )
      set output = '{"name":"'"$d"'","date":'"$DATE"',"count":'"$len"',"total":'"$total_rows"',"limit":'"$limit"',"ids":'"$ids"' }'
      if ($?DEBUG)  echo `date` "$0:t $$ -- found $len ids w/ limit $limit" >>&! $LOGTO
    else if ($?since) then
      set ids = ( `jq '[.rows?|sort_by(.id)|reverse[].doc|select(.date>'"$since"')._id]' "$out"` )
      set len = ( `echo "$ids" | jq '.|length'` )
      set output = '{"name":"'"$d"'","date":'"$since"',"count":'"$len"',"total":'"$total_rows"',"limit":'"$IMAGE_LIMIT"',"ids":'"$ids"' }'
      if ($?DEBUG)  echo `date` "$0:t $$ -- found $len ids since $since" >>&! $LOGTO
    else
      set ids = ( `jq '[.rows?|sort_by(.id)|reverse[].doc|._id]' "$out"` )
      set len = ( `echo "$ids" | jq '.|length'` )
      set output = '{"name":"'"$d"'","date":'"$DATE"',"count":'"$len"',"total":'"$total_rows"',"limit":'"$IMAGE_LIMIT"',"ids":'"$ids"' }'
      if ($?DEBUG)  echo `date` "$0:t $$ -- found $len ids" >>&! $LOGTO
     endif
     rm -f "$out"
     goto output
  else if ($db == "all") then
    set json = '{"name":"'"$d"'","date":'"$lid"',"total":'"$total_rows"'}'
  else
    unset json
  endif
  if ($k) set all = "$all"','
  @ k++
  if ($?json) then
    set all = "$all""$json"
  endif
end

set all = "$all"']}'
echo "$all" | jq -c '.' >! "$OUTPUT"

#
# output
#

output:

echo "Content-Type: application/json; charset=utf-8"
echo "Access-Control-Allow-Origin: *"

if ($?output == 0 && -s "$OUTPUT") then
  @ age = $SECONDS - $DATE
  echo "Age: $age"
  @ refresh = $TTL - $age
  if ($refresh < 0) @ refresh = $TTL
  echo "Refresh: $refresh"
  echo "Cache-Control: max-age=$TTL"
  echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
  echo ""
  jq -c '.' "$OUTPUT"
  if ($?DEBUG) echo `date` "$0 $$ -- output ($OUTPUT) Age: $age Refresh: $refresh" >>&! $LOGTO
  /bin/rm -f "$OUTPUT"
  goto done
else
  echo "Cache-Control: no-cache"
  echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
  echo ""
  if ($?output) then
     echo "$output"
  else
     echo '{ "error": "not found" }'
  endif
endif

###
### done
###
done:
  if ($?DEBUG) echo `date` "$0 $$ -- $db -- FINISH" >>&! $LOGTO
