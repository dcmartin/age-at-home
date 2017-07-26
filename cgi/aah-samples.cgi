#!/bin/csh -fb
setenv APP "aah"
setenv API "samples"
setenv LAN "192.168.1"
setenv WWW "$LAN".32
setenv DIGITS "$LAN".30
setenv WAN "www.dcmartin.com"
setenv TMP "/var/lib/age-at-home"

# setenv DEBUG true

# don't update statistics more than once per (in seconds)
setenv TTL 1800
setenv SECONDS `/bin/date "+%s"`
setenv DATE `/bin/echo $SECONDS \/ $TTL \* $TTL | bc`

if ($?QUERY_STRING) then
    set db = `/bin/echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
    set class = `/bin/echo "$QUERY_STRING" | sed 's/.*class=\([^&]*\).*/\1/'`
    if ($class == "$QUERY_STRING") unset class
    set id = `/bin/echo "$QUERY_STRING" | sed 's/.*id=\([^&]*\).*/\1/'`
    if ($id == "$QUERY_STRING") unset id
    set ext = `/bin/echo "$QUERY_STRING" | sed 's/.*ext=\([^&]*\).*/\1/'`
    if ($ext == "$QUERY_STRING") unset ext
endif

if ($?db == 0 && $?id) unset id
if ($?ext == 0 && $?id) set ext = "full"
if ($?db == 0) set db = rough-fog
if ($?class == 0) set class = all

# standardize QUERY_STRING (rendezvous w/ APP-make-API.csh script)
setenv QUERY_STRING "db=$db"
if ($?class) setenv QUERY_STRING "$QUERY_STRING&class=$class"

/bin/echo `/bin/date` "$0 $$ -- START ($QUERY_STRING)" >>! $TMP/LOG

# initiate new output
if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ ++ REQUESTING ./$APP-make-$API.bash" >>! $TMP/LOG
./$APP-make-$API.bash

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

# handle singleton (image)
if ($db != "all" && $?id) then
  set url = "$CU/$db/$id"
  set out = "/tmp/$0:t.$$.json"
  set try = 0
  set time = 2
again:
  /usr/bin/curl -s -q -f -m 1 -L "$url" -o "$out"
  if ($status != 22 && $status != 28 && -s "$out") then
    if ($?class == 0) then
      set class = ( `/usr/local/bin/jq -r '.alchemy.text?' "$out" | sed 's/ /_/g'` )
    else if ($class == "all") then
      set class = ( `/usr/local/bin/jq -r '.alchemy.text?' "$out" | sed 's/ /_/g'` )
    endif
    if ($#class && $class != "null") then
      if ($ext == "full") set path = "$TMP/$db/$class/$id.jpg"
      if ($ext == "crop") set path = "$TMP/$db/$class/$id.jpeg"
      if (-s "$path") then
        set stat = ( `/usr/bin/stat -r "$path" | awk '{ print $10 }'` )
        set AGE = `/bin/echo "$SECONDS - $stat" | /usr/bin/bc`
        /bin/echo "Access-Control-Allow-Origin: *"
        /bin/echo "Cache-Control: max-age=14400"
        /bin/echo "Last-Modified:" `/bin/date -r $stat '+%a, %d %b %Y %H:%M:%S %Z'`
        /bin/echo "Content-Location: $WWW/CGI/$APP-$API.cgi?db=$db&class=$class&id=$id&ext=$ext"
        /bin/echo "Content-Type: image/jpeg"
        /bin/echo ""
        if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- SINGLETON ($id)" >>! $TMP/LOG
        /bin/dd if="$path"
        goto done
      endif
      set output = '{"error":"not found","db":"'"$db"'","class":"'"$class"'","id":"'"$id"'"}'
    endif
  else if ($try < 3) then
    @ try++
    @ time += $time
    goto again
  endif
  /bin/rm -f "$out"
  set output = '{"error":"not found","db":"'"$db"'","id":"'"$id"'"}'
  goto output
endif

#
# find output
#
if (! -s "$OUTPUT") then
  /bin/rm -f "$OUTPUT:r:r".*

  if ("$class" == "all") then
    set url = "$db-$API/all"
    set out = "$OUTPUT:r:r".$$.json

    /usr/bin/curl -m 5 -s -q -f -L "$CU/$url" -o "$out"
    if ($status != 22 && $status != 28 && -s "$out") then
      set classes = ( `/usr/local/bin/jq -r '.classes[]?.name' "$out"` )
      if ($#classes) then
        if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ ++ SUCCESS ($url) -- classes ($classes)" >>&! $TMP/LOG
	mv "$out" "$OUTPUT"
        goto output
      else
        if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ ++ FAILURE ($url)" >>&! $TMP/LOG
        unset classes
      endif
    else
      if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ ++ FAILURE ($url)" >>&! $TMP/LOG
      /bin/rm -f "$out"
    endif
    # FAILURE -- above should suffice
    if ($?classes == 0) then
      set url = "$db-$API/_all_docs"
      /usr/bin/curl -m 5 -s -q -f -L "$CU/$url" -o "$out"
      if ($status != 22 && $status != 28 && -s "$out") then
	set classes = ( `/usr/local/bin/jq -r '.rows[].id' "$out" | egrep -v "all"` )
	if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ ++ SUCCESS ($classes)" >>&! $TMP/LOG
        /bin/rm -f "$out"
      else
	if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ ++ FAILURE ($url)" >>&! $TMP/LOG
	/bin/rm -f "$out"
	goto output
      endif
    endif
    @ k = 0
    set all = '{"date":'"$DATE"',"name":"'"$db"'","count":'$#classes',"classes":['
    foreach c ( $classes )
      set URL = "https://$CU/$db-$API/$c"
      set json = ( `/usr/bin/curl -s -q -f -L "$URL" | /usr/local/bin/jq '{"name":"'"$c"'","date":.date,"count":.count }'` )
      if ($#json) then
	if ($k) set all = "$all"','
	set all = "$all""$json"
	@ k++
      else
	if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ ++ FAILED on class $c" >>&! $TMP/LOG
      endif
    end
    set all = "$all"']}'
    /bin/echo "$all" >! "$OUTPUT"
  else
    set URL = "https://$CU/$db-$API/$class"
    /usr/bin/curl -s -q -f -L "$URL" | /usr/local/bin/jq '{"name":.name,"date":.date,"count":.count,"ids":.ids}' >! "$OUTPUT"
  endif
endif

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

/bin/echo `/bin/date` "$0 $$ -- FINISH ($QUERY_STRING)" >>! $TMP/LOG
