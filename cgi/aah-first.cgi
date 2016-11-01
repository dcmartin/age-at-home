#!/bin/csh -fb
setenv APP "aah"
setenv API "first"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"
# don't update statistics more than once per 15 minutes
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

set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
if (! -e "$OUTPUT") then
    rm -f "$TMP/$APP-$API-$QUERY_STRING".*.json
    if ($DB == "damp-cloud") then
	# new URL for "person" or "people" from Alchemy text
	curl -L -s -q -o "$OUTPUT" "https://ibmcds.looker.com/looks/Bck9m3sbyxX23t4S4tvy7fGpSw4mYPcx.json?apply_formatting=true" 
    else
	# NEED new URL for "person" or "people" from Alchemy text
	curl -L -s -q -o "$OUTPUT" "https://ibmcds.looker.com/looks/Yh9rxzkxzwMBKZdnWSBW7MrpyqYJCSyY.json?apply_formatting=true"
    endif
endif
if ($DB == "damp-cloud") then
    set DATETIME = `/usr/local/bin/jq '.[0]."dampcloud.15_minute_interval"' $OUTPUT`
else
    set DATETIME = `/usr/local/bin/jq '.[0]."roughfog.15_minute_interval"' $OUTPUT`
endif

output:

echo "Content-Type: application/json; charset=utf-8"
echo "Access-Control-Allow-Origin: *"
set AGE = `echo "$SECONDS - $DATE" | bc`
echo "Age: $AGE"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo ""
echo '{"device":"'$DB'", "datetime":'$DATETIME' }'

done:

echo `date` "$0 $$ -- FINISH" >>! $TMP/LOG
