#!/bin/csh -fb
setenv APP "aah"
setenv API "averageHuman"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

# don't update output more than once per (in seconds)
set TTL = `echo "30 * 60" | bc`
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo `date` "$0 $$ -- START" >>! $TMP/LOG

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed "s/.*db=\([^&]*\).*/\1/"`
    if ($#DB == 0) set DB = rough-fog
else
    set DB = rough-fog
endif
setenv QUERY_STRING "db=$DB"

set OUTPUT = "$TMP/$APP-$API.$QUERY_STRING.$DATE.json"
if (! -e "$OUTPUT") then
    rm -f $TMP/$APP-$API.$QUERY_STRING.*.json
    if ($DB == "damp-cloud") then
	curl -L -s -q -o "$OUTPUT" "https://ibmcds.looker.com/looks/bhRrfdbXN6vwd5SpFWvGgbRXDW6mxhTD.json?apply_formatting=true"
    else
	curl -L -s -q -o "$OUTPUT" "https://ibmcds.looker.com/looks/ZMdS9gbqv7mvmGqnvZHTbmGY4n53TBXV.json?apply_formatting=true"
    endif
    echo '{"device":"'$DB'", "averages":' >! "$OUTPUT".$$
    if ($DB == "damp-cloud") then
	cat "$OUTPUT" \
	    | sed "s/dampcloud\.15_minute_//" \
	    | sed "s/dampcloud_visual_scores\.//g" >> "$OUTPUT".$$
    else
	cat "$OUTPUT" \
	    | sed "s/roughfog\.15_minute_//" \
	    | sed "s/roughfog_visual_scores\.//g" >> "$OUTPUT".$$
    endif
    echo '}' >> "$OUTPUT.$$"
    mv -f "$OUTPUT".$$ "$OUTPUT"
endif

echo "Content-Type: application/json; charset=utf-8"
echo "Access-Control-Allow-Origin: *"
set AGE = `echo "$SECONDS - $DATE" | bc`
echo "Age: $AGE"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo ""
cat "$OUTPUT"

done:
echo `date` "$0 $$ -- FINISH" >>! $TMP/LOG
