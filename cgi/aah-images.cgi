#!/bin/csh -fb
setenv APP "aah"
setenv API "images"
setenv LAN "192.168.1"
setenv WWW "$LAN".32
setenv DIGITS "$LAN".30
setenv WAN "www.dcmartin.com"
setenv TMP "/var/lib/age-at-home"

setenv DEBUG true

# don't update statistics more than once per (in seconds)
setenv TTL 15
setenv SECONDS `/bin/date "+%s"`
setenv DATE `/bin/echo $SECONDS \/ $TTL \* $TTL | bc`

# default image limit
if ($?IMAGE_LIMIT == 0) setenv IMAGE_LIMIT 10000
if ($?IMAGE_SET_LIMIT == 0) setenv IMAGE_SET_LIMIT 100

if ($?QUERY_STRING) then
    set db = `/bin/echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
    set class = `/bin/echo "$QUERY_STRING" | sed 's/.*class=\([^&]*\).*/\1/'`
    if ($class == "$QUERY_STRING") unset class
    set id = `/bin/echo "$QUERY_STRING" | sed 's/.*id=\([^&]*\).*/\1/'`
    if ($id == "$QUERY_STRING") unset id
    set ext = `/bin/echo "$QUERY_STRING" | sed 's/.*ext=\([^&]*\).*/\1/'`
    if ($ext == "$QUERY_STRING") unset ext
    set since = `/bin/echo "$QUERY_STRING" | sed 's/.*since=\([^&]*\).*/\1/'`
    if ($since == "$QUERY_STRING") unset since
    set limit = `/bin/echo "$QUERY_STRING" | sed 's/.*limit=\([^&]*\).*/\1/'`
    if ($limit == "$QUERY_STRING") unset limit
    set force = `/bin/echo "$QUERY_STRING" | /usr/bin/sed 's/.*force=\([^&]*\).*/\1/'`
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

# standardize QUERY_STRING for cache
setenv QUERY_STRING "db=$db"

if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- START ($QUERY_STRING)" >>! $TMP/LOG

# TARGET 
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

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
    /bin/echo `/bin/date` "$0 $$ -- no Cloudant URL" >>! $TMP/LOG
    goto done
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

# test if singleton && non-image (i.e. json) requested
if ($?singleton && $?ext == 0) then
  if ($?id) then
    set url = "$db-images/$id"
  else
    set url = "$db-images/_all_docs?include_docs=true&descending=true&limit=1"
  endif
  set out = "/tmp/$0:t.$$.json"
  /usr/bin/curl -s -q -f -L "$CU/$url" -o "$out"
  if ($status == 22 || $status == 28 || ! -s "$out") then
    if ($?id) then
    set output = '{"error":"not found","db":"'"$db"'","id":"'"$id"'"}'
    else if ($?limit)
    set output = '{"error":"not found","db":"'"$db"'","limit":"'"$limit"'"}'
    else
    set output = '{"error":"not found","db":"'"$db"'"}'
    endif
  else
    if ($?limit) then
      set id = ( `/usr/local/bin/jq -r '.rows[].doc._id' "$out"` )
    endif
    set class = ( `/usr/bin/curl -s -q -f -L "$WWW/CGI/aah-updates.cgi?db=$db&id=$id" | /usr/local/bin/jq -r '.class?'` )
    if ($#class && $class != "null") then
      if ($?limit) then
        set output = ( `/usr/local/bin/jq '.rows[]?.doc|{"id":._id,"class":"'"$class"'","date":.date,"type":.type,"size":.size,"crop":.crop,"depth":.depth,"color":.color}' "$out"` )
      else
        set output = ( `/usr/local/bin/jq '{"id":._id,"class":"'"$class"'","date":.date,"type":.type,"size":.size,"crop":.crop,"depth":.depth,"color":.color}' "$out"` )
      endif
    else
      set output = '{"error":"not found","db":"'"$db"'","id":"'"$id"'"}'
    endif
  endif
  rm -f "$out"
  goto output
endif

# handle singleton (image)
if ($?singleton && $?ext) then
  if ($?id) then
    set url = "$db-images/$id"
  else if ($?limit) then
    set url = "$db-images/_all_docs?include_docs=true&descending=true&limit=1"
  endif
  set out = "/tmp/$0:t.$$.json"
  /usr/bin/curl -s -q -f -L "$CU/$url" -o "$out"
  if ($status == 22 || $status == 28 || ! -s "$out") then
    if ($?id) then
	set output = '{"error":"not found","db":"'"$db"'","id":"'"$id"'"}'
    else if ($?limit) then
	set output = '{"error":"not found","db":"'"$db"'","limit":"'"$limit"'"}'
    endif
  else
    if ($?limit) then
      set json = ( `/usr/local/bin/jq '.rows[].doc' "$out"` )
      set id = ( `/usr/local/bin/jq -r '.rows[].doc._id' "$out"` )
    else
      set json = ( `/usr/local/bin/jq '.' "$out"` )
    endif
    set id = ( `/bin/echo "$json" | /usr/local/bin/jq -r '._id'` )
    set crop = ( `/bin/echo "$json" | /usr/local/bin/jq -r '.crop'` )
    set class = ( `/usr/bin/curl -s -q -f -L "$WWW/CGI/aah-updates.cgi?db=$db&id=$id" | /usr/local/bin/jq -r '.class?' | /usr/bin/sed 's/ /_/g'` )
    rm -f "$out"
    if ($#class && $class != "null") then
	if ($ext == "full") set path = "$TMP/$db/$class/$id.jpg"
	if ($ext == "crop") set path = "$TMP/$db/$class/$id.jpeg"
	if (-s "$path") then
	  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- SINGLETON ($path)" >>! $TMP/LOG

          set stat = ( `/usr/bin/stat -r "$path" | /usr/bin/awk '{ print $10 }'` )

	  /bin/echo "Cache-Control: max-age=$TTL"
	  /bin/echo "Last-Modified:" `/bin/date -r $stat '+%a, %d %b %Y %H:%M:%S %Z'`
	  /bin/echo "Access-Control-Allow-Origin: *"
	  /bin/echo "Content-Location: $WWW/CGI/$APP-$API.cgi?db=$db&class=$class&id=$id&ext=$ext"
	  /bin/echo "Content-Type: image/jpeg"
	  /bin/echo ""

          ./aah-images-label.csh "$path" "$class" "$crop"
	  goto done
	endif
        set output = '{"error":"does not exist","db":"'"$db"'","class":"'"$class"'","id":"'"$id"'"}'
        goto output
      endif
      set output = '{"error":"not found","db":"'"$db"'","id":"'"$id"'"}'
      goto output
  endif
  /bin/rm -f "$out"
  set output = '{"error":"not found","db":"'"$db"'","id":"'"$id"'"}'
  goto output
endif

#
# NOT A SINGLETON
#

# find updates
set url = "$WWW/CGI/aah-updates.cgi"
set updates = ( `/usr/bin/curl -s -q -f -L "$url" | /usr/local/bin/jq '.'` )
if ($#updates == 0) then
  if ($?VERBOSE) /bin/echo `date` "$0 $$ ++ FAILURE ($url)" >>&! $TMP/LOG
  set output = '{"error":"NO UPDATES -- '"$url"'"}'
  goto output
endif

# get devices
set devices = ( `/bin/echo "$updates" | /usr/local/bin/jq -r '.devices[]?.name'` )
if ($#devices == 0) then
  if ($?VERBOSE) /bin/echo `date` "$0 $$ ++ FAILURE ($url)" >>&! $TMP/LOG
  set output = '{"error":"NO DEVICES -- '"$updates"'"}'
  goto output
endif
# get last check time (seconds since epoch)
set last_update_check = ( `/bin/echo "$updates" | /usr/local/bin/jq -r '.date'`)

if ($?DEBUG) /bin/echo `date` "$0 $$ ++ SUCCESS -- devices ($devices) -- last check" `/bin/date -j -f %s "$last_update_check"` >>&! $TMP/LOG

# check all devices
foreach d ( $devices )
  # initiate new output
  set qs = "$QUERY_STRING"
  setenv QUERY_STRING "device=$d"
  if ($?force) then
    setenv QUERY_STRING "$QUERY_STRING&force=true"
  endif
  if ($?DEBUG) /bin/echo `date` "$0 $$ ++ REQUESTING ./$APP-make-$API.bash ($QUERY_STRING)" >>! $TMP/LOG
  ./$APP-make-$API.bash
  setenv QUERY_STRING "$qs"
  # indicate success
  if ($db == "$d") set found = "$d"
end

if ($db != "all") then
  if  ($?found == 0) then
    set output = '{"error":"not found","db":"'"$db"'"}'
    goto output
  endif
  set devices = ( $db )
endif


#
# PROCESS REQUESTED DEVICES
#

@ k = 0
set all = '{"date":'"$DATE"',"devices":['
# handle all (json)
foreach d ( $devices )
  set lud = ( `/bin/echo "$updates" | /usr/local/bin/jq -r '.devices?[]|select(.name=="'"$d"'")|.date'` )
  if ($?DEBUG) /bin/echo `date` "$0 $$ ++ UPDATES ($d) -- last check" `/bin/date -j -f %s "$lud"` >>&! $TMP/LOG

  # get db data
  set url = "$CU/$d-images/_all_docs?include_docs=true&limit=1&descending=true"
  set out = "/tmp/$0:t.$$.json"
  /usr/bin/curl -s -q -f -L "$url" -o "$out"
  if ($status != 22 && -s "$out") then
    set lid = ( `/usr/local/bin/jq '.rows[].doc.date' "$out"` )
    set total_rows = ( `/usr/local/bin/jq '.total_rows' "$out"` )
    if ($#lid == 0 || $lid == "null")  set lid = 0
    if ($#total_rows == 0 || $total_rows == "null")  set total_rows = 0
  else
    if ($?DEBUG) /bin/echo `date` "$0 $$ ++ NO UPDATES ($d" >>&! $TMP/LOG
    /bin/rm -f "$out"
    goto done
  endif
  /bin/rm -f "$out"

  # get estimated number of images
  if ($?since) then
    @ delay = $lud - $since
  else
    @ delay = $lud - $lid
  endif
  @ estimate = $delay / 60
  if ($estimate > $IMAGE_LIMIT) then
    set estimate = $IMAGE_LIMIT
  else if ($estimate == 0) then
    @ estimate = 1
  endif

  if ($?DEBUG) then
    set LUD = `/bin/date -j -f %s "$lud"` 
    set LID = `/bin/date -j -f %s "$lid"` 
    /bin/echo `date` "$0 $$ ++ UPDATES ($d) -- delay ($delay) -- estimate ($estimate) -- image: $LID -- update: $LUD" >>&! $TMP/LOG
  endif

  # process this db
  if ($db != "all" && $d == "$db") then
    # get recent rows
    set url = "$CU/$d-images/_all_docs?include_docs=true&&descending=true&limit=$estimate"
    set out = "/tmp/$0:t.$$.json"
    @ try = 0
    @ rtt = 5
    while ($try < 3)
      /usr/bin/curl -m "$rtt" -s -q -f  -L "$url" -o "$out"
      if ($status == 22 || $status == 28 || ! -s "$out") then
	/bin/rm -f "$out"
	@ try++
	@ rtt += $rtt
	continue
      endif
      break
    end
    if (! -s "$out") then
      /bin/rm -f "$out"
      set output = '{"error":"failure","db":"'"$d-images"'}'
      goto output
    endif
    if ($?limit == 0) set limit = $IMAGE_SET_LIMIT
    if ($?since == 0) then
      set ids = ( `/usr/local/bin/jq '[limit('"$limit"';.rows?|sort_by(.id)|reverse[].doc|select(.date<='"$lid"')._id)]' "$out"` )
      set len = ( `/bin/echo "$ids" | /usr/local/bin/jq '.|length'` )
      echo '{"name":"'"$d"'","date":'"$lid"',"count":'"$len"',"total":'"$total_rows"',"limit":'"$limit"',"ids":'"$ids"' }' >! "$OUTPUT"
    else
      set all = ( `/usr/local/bin/jq -r '.rows[]?.doc|select(.date<='"$lid"')|select(.date>'"$since"')._id' "$out"` )
      set len = $#all
      if ($limit > $len) then
	set ids = ( $all[1-$len] )
      else
	set ids = ( $all[1-$limit] )
      endif
      set num = $#ids
      if ($num > 0) then
	set all = ( `/bin/echo "$ids" | /usr/bin/sed 's/\([^ ]*\)/"\1"/g' | sed 's/ /,/g'` )
      else
	set all = ""
      endif
      echo '{"name":"'"$d"'","date":'"$lid"',"count":'"$num"',"total":'"$len"',"limit":'"$limit"',"ids":['"$all"']}' >! "$OUTPUT"
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
    /bin/echo "Last-Modified:" `/bin/date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
    /bin/echo ""
    /usr/local/bin/jq -c '.' "$OUTPUT"
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- output ($OUTPUT) Age: $age Refresh: $refresh" >>! $TMP/LOG
else
    /bin/echo "Cache-Control: no-cache"
    /bin/echo "Last-Modified:" `/bin/date -r $SECONDS '+%a, %d %b %Y %H:%M:%S %Z'`
    /bin/echo ""
    if ($?output) then
      /bin/echo "$output"
    else
      /bin/echo '{ "error": "not found" }'
    endif
endif

# done

done:

if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- FINISH ($QUERY_STRING)" >>! $TMP/LOG
