#!/bin/csh -fb
setenv APP "aah"
setenv API "last"
setenv WWW "http://www.dcmartin.com/CGI/"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/tmp"
# don't update statistics more than once per 15 minutes
set TTL = `echo "30 * 60" | bc`
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo "$APP-$API ($0 $$) -- $SECONDS" >>! $TMP/LOG

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed "s/.*db=\([^&]*\).*/\1/"`
    if ($#DB == 0) set DB = rough-fog
else
    set DB = rough-fog
endif
setenv QUERY_STRING "db=$DB"

set OUTPUT = "$TMP/$APP-$API.$DB.$DATE.json"
if (! -e "$OUTPUT") then
    rm -f $TMP/$APP-$API.$DB.*.json
    if ($DB == "damp-cloud") then
	curl -L -s -q -o "$OUTPUT" "https://ibmcds.looker.com/looks/QYMvmW69kbcPxf3MkN43jSrgJ2NvBg9D.json"
    else
	curl -L -s -q -o "$OUTPUT" "https://ibmcds.looker.com/looks/P7QkTrRjNVpGfj4Vgz8m8Qzb7cFw8Z4X.json"
    endif
endif
if ($DB == "damp-cloud") then
    set DATETIME = `/usr/local/bin/jq '.[]."dampcloud.alchemy_time"' $OUTPUT`
else
    set DATETIME = `/usr/local/bin/jq '.[]."roughfog.alchemy_time"' $OUTPUT`
endif

echo "Content-Type: application/json; charset=utf-8"
echo "Access-Control-Allow-Origin: *"
set AGE = `echo "$SECONDS - $DATE" | bc`
echo "Age: $AGE"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo ""
echo '{"device":"'$DB'", "datetime":'$DATETIME' }'
