#!/bin/csh -fb
setenv APP "aah"
setenv API "review"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

setenv DEBUG true

# don't update statistics more than once per (in seconds)
setenv TTL 1800
setenv SECONDS `date "+%s"`
setenv DATE `echo $SECONDS \/ $TTL \* $TTL | bc`

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($DB == "$QUERY_STRING") unset DB
    set class = `echo "$QUERY_STRING" | sed 's/.*id=\([^&]*\).*/\1/'`
    if ($class == "$QUERY_STRING") unset class
endif

if ($?DB == 0) set DB = rough-fog
if ($?class == 0) set class = all
setenv QUERY_STRING "db=$DB&id=$class"

echo `date` "$0 $$ -- START ($QUERY_STRING)" >>! $TMP/LOG

if (-e ~$USER/.cloudant_url) then
    set cc = ( `cat ~$USER/.cloudant_url` )
    if ($#cc > 0) set CU = $cc[1]
    if ($#cc > 1) set CN = $cc[2]
endif

if ($?CLOUDANT_URL) then
    set CU = $CLOUDANT_URL
else if ($?CN) then
    set CU = "$CN"@"$CN.cloudant.com"
else
    if ($?DEBUG) echo `date` "$0 $$ -- no Cloudant URL" >>! $TMP/LOG
    goto done
endif

# output set
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

# check OUTPUT exists
if (-s "$OUTPUT") then
    if ($?DEBUG) echo `date` "$0 $$ -- existing ($OUTPUT)" >>! $TMP/LOG
    goto output
else
    # find old output
    set ALL_OUTPUT = "$TMP/$APP-$API-$QUERY_STRING."*".json"
    # initiate new output
    if ($?DEBUG) echo `date` "$0 $$ ++ CALLING ./$APP-make-$API.bash to create ($OUTPUT)" >>! $TMP/LOG
    ./$APP-make-$API.bash
    # find newest output
    if ($#ALL_OUTPUT > 0) then
      @ d = 0
      foreach i ( $ALL_OUTPUT )
        if ($i:r:e > $d) then
          @ d = $i:r:e
	  if ($?old) rm -f "$old"
          set old = $i
        endif
      end
    endif
    if ($?old) then
        setenv DATE  "$old:r:e"
        set OUTPUT = $old
        if ($?DEBUG) echo `date` "$0 $$ -- using old output ($OUTPUT)" >>! $TMP/LOG
        goto output
      endif
    endif
    # return redirect
    set URL = "https://$CU/$DB-$API/$class"
    if ($?DEBUG) echo `date` "$0 $$ -- returning redirect ($URL)" >>! $TMP/LOG
    set age = `echo "$SECONDS - $DATE" | bc`
    echo "Age: $age"
    set refresh = `echo "$TTL - $age | bc`
    if ($refresh < 0) set refresh = 0
    echo "Refresh: $refresh"
    echo "Cache-Control: max-age=$TTL"
    echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
    echo "Status: 302 Found"
    echo "Location: $URL"
    echo ""
    goto done
endif

output:

#
# prepare for output
#
echo "Content-Type: application/json; charset=utf-8"
echo "Access-Control-Allow-Origin: *"
@ age = $SECONDS - $DATE
echo "Age: $age"
@ refresh = $TTL - $age
# check back if using old
if ($refresh < 0) @ refresh = 90
echo "Refresh: $refresh"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo ""
/usr/local/bin/jq -c '.' "$OUTPUT"

# done
done:

echo `date` "$0 $$ -- FINISH ($QUERY_STRING)" >>! $TMP/LOG
