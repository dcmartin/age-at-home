#!/bin/tcsh -b
setenv APP "aah"
setenv API "labels"

# debug on/off
setenv DEBUG true
setenv VERBOSE true

# environment
if ($?LAN == 0) setenv LAN "192.168.1"
if ($?DIGITS == 0) setenv DIGITS "$LAN".30
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

/bin/echo `date` "$0 $$ -- START ($QUERY_STRING)" >>! $LOGTO

# initiate new output
if ($?DEBUG) /bin/echo `date` "$0 $$ ++ REQUESTING ./$APP-make-$API.bash" >>! $LOGTO
./$APP-make-$API.bash

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
# find output
#
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

if (! -s "$OUTPUT") then
  rm -f "$OUTPUT:r:r".*

  if ("$class" == "all") then
    set url = "$db-$API/all"
    set out = "$OUTPUT:r:r".$$.json

    curl -m 5 -s -q -f -L "$CU/$url" -o "$out"
    if ($status != 22 && $status != 28 && -s "$out") then
      set classes = ( `jq -r '.classes[]?.name' "$out"` )
      if ($#classes) then
        if ($?DEBUG) /bin/echo `date` "$0 $$ ++ SUCCESS ($url) -- classes ($classes)" >>&! $LOGTO
	mv "$out" "$OUTPUT"
        goto output
      else
        if ($?DEBUG) /bin/echo `date` "$0 $$ ++ FAILURE ($url)" >>&! $LOGTO
        unset classes
      endif
    else
      if ($?DEBUG) /bin/echo `date` "$0 $$ ++ FAILURE ($url)" >>&! $LOGTO
      rm -f "$out"
    endif
    # FAILURE -- above should suffice
    if ($?classes == 0) then
      set url = "$db-$API/_all_docs"
      curl -m 5 -s -q -f -L "$CU/$url" -o "$out"
      if ($status != 22 && $status != 28 && -s "$out") then
	set classes = ( `jq -r '.rows[].id' "$out" | egrep -v "all"` )
	if ($?DEBUG) /bin/echo `date` "$0 $$ ++ SUCCESS ($classes)" >>&! $LOGTO
        rm -f "$out"
      else
	if ($?DEBUG) /bin/echo `date` "$0 $$ ++ FAILURE ($url)" >>&! $LOGTO
	rm -f "$out"
	goto output
      endif
    endif
    @ k = 0
    set all = '{"date":'"$DATE"',"device":"'"$db"'","count":'$#classes',"classes":['
    foreach c ( $classes )
      set URL = "$CU/$db-$API/$c"
      set json = ( `curl -s -q -f -L "$URL" | jq '{"name":"'"$c"'","date":.date,"count":.count }'` )
      if ($#json) then
	if ($k) set all = "$all"','
	set all = "$all""$json"
	@ k++
      else
	if ($?DEBUG) /bin/echo `date` "$0 $$ ++ FAILED on class $c" >>&! $LOGTO
      endif
    end
    set all = "$all"']}'
    /bin/echo "$all" >! "$OUTPUT"
  else
    set URL = "$CU/$db-$API/$class"
    curl -s -q -f -L "$URL" | jq '{"name":.name,"date":.date,"count":.count,"ids":.ids}' >! "$OUTPUT"
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
    /bin/echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
    /bin/echo ""
    jq -c '.' "$OUTPUT"
    if ($?DEBUG) /bin/echo `date` "$0 $$ -- output ($OUTPUT) Age: $age Refresh: $refresh" >>! $LOGTO
else
    /bin/echo "Cache-Control: no-cache"
    /bin/echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $SECONDS`
    /bin/echo ""
    /bin/echo '{ "error": "not found" }'
endif

# done

done:

/bin/echo `date` "$0 $$ -- FINISH ($QUERY_STRING)" >>! $LOGTO
