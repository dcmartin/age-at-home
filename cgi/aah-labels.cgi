#!/bin/csh -fb
setenv APP "aah"
setenv API "labels"
setenv LAN "192.168.1"
setenv WWW "$LAN".32
setenv DIGITS "$LAN".30
setenv WAN "www.dcmartin.com"
setenv TMP "/var/lib/age-at-home"

# setenv DEBUG true

# don't update statistics more than once per (in seconds)
setenv TTL 1800
setenv SECONDS `date "+%s"`
setenv DATE `/bin/echo $SECONDS \/ $TTL \* $TTL | bc`

if ($?QUERY_STRING) then
    set db = `/bin/echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
    set class = `/bin/echo "$QUERY_STRING" | sed 's/.*class=\([^&]*\).*/\1/'`
    if ($class == "$QUERY_STRING") unset class
endif

if ($?db == 0) set db = rough-fog
if ($?class == 0) set class = all

# standardize QUERY_STRING (rendezvous w/ APP-make-API.csh script)
setenv QUERY_STRING "db=$db"
if ($?class) setenv QUERY_STRING "$QUERY_STRING&class=$class"

/bin/echo `date` "$0 $$ -- START ($QUERY_STRING)" >>! $TMP/LOG

# initiate new output
if ($?DEBUG) /bin/echo `date` "$0 $$ ++ REQUESTING ./$APP-make-$API.bash" >>! $TMP/LOG
./$APP-make-$API.bash

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

#
# find output
#
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

if (! -s "$OUTPUT") then
  rm -f "$OUTPUT:r:r".*

  if ("$class" == "all") then
    set url = "$db-$API/all"
    set out = "$OUTPUT:r:r".$$.json

    /usr/bin/curl -m 5 -s -q -f -L "$CU/$url" -o "$out"
    if ($status != 22 && $status != 28 && -s "$out") then
      set classes = ( `/usr/local/bin/jq -r '.classes[]?.name' "$out"` )
      if ($#classes) then
        if ($?DEBUG) /bin/echo `date` "$0 $$ ++ SUCCESS ($url) -- classes ($classes)" >>&! $TMP/LOG
	mv "$out" "$OUTPUT"
        goto output
      else
        if ($?DEBUG) /bin/echo `date` "$0 $$ ++ FAILURE ($url)" >>&! $TMP/LOG
        unset classes
      endif
    else
      if ($?DEBUG) /bin/echo `date` "$0 $$ ++ FAILURE ($url)" >>&! $TMP/LOG
      rm -f "$out"
    endif
    # FAILURE -- above should suffice
    if ($?classes == 0) then
      set url = "$db-$API/_all_docs"
      /usr/bin/curl -m 5 -s -q -f -L "$CU/$url" -o "$out"
      if ($status != 22 && $status != 28 && -s "$out") then
	set classes = ( `/usr/local/bin/jq -r '.rows[].id' "$out" | egrep -v "all"` )
	if ($?DEBUG) /bin/echo `date` "$0 $$ ++ SUCCESS ($classes)" >>&! $TMP/LOG
        rm -f "$out"
      else
	if ($?DEBUG) /bin/echo `date` "$0 $$ ++ FAILURE ($url)" >>&! $TMP/LOG
	rm -f "$out"
	goto output
      endif
    endif
    @ k = 0
    set all = '{"date":'"$DATE"',"device":"'"$db"'","count":'$#classes',"classes":['
    foreach c ( $classes )
      set URL = "https://$CU/$db-$API/$c"
      set json = ( `curl -s -q -f -L "$URL" | /usr/local/bin/jq '{"name":"'"$c"'","date":.date,"count":.count }'` )
      if ($#json) then
	if ($k) set all = "$all"','
	set all = "$all""$json"
	@ k++
      else
	if ($?DEBUG) /bin/echo `date` "$0 $$ ++ FAILED on class $c" >>&! $TMP/LOG
      endif
    end
    set all = "$all"']}'
    /bin/echo "$all" >! "$OUTPUT"
  else
    set URL = "https://$CU/$db-$API/$class"
    curl -s -q -f -L "$URL" | /usr/local/bin/jq '{"name":.name,"date":.date,"count":.count,"ids":.ids}' >! "$OUTPUT"
  endif
endif

#
# output
#

output:

/bin/echo "Content-Type: application/json; charset=utf-8"
/bin/echo "Access-Control-Allow-Origin: *"

if (-s "$OUTPUT") then
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
    if ($?DEBUG) /bin/echo `date` "$0 $$ -- output ($OUTPUT) Age: $age Refresh: $refresh" >>! $TMP/LOG
else
    /bin/echo "Cache-Control: no-cache"
    /bin/echo "Last-Modified:" `date -r $SECONDS '+%a, %d %b %Y %H:%M:%S %Z'`
    /bin/echo ""
    /bin/echo '{ "error": "not found" }'
endif

# done

done:

/bin/echo `date` "$0 $$ -- FINISH ($QUERY_STRING)" >>! $TMP/LOG
