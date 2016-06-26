#!/bin/tcsh
setenv APP "aah"
setenv API "classifiers"
setenv WWW "http://www.dcmartin.com/CGI/"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/tmp"
# don't update statistics more than once per 15 minutes
set TTL = `echo "30 * 60" | bc`
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo "$APP-$API ($0 $$) -- $SECONDS" >>! $TMP/LOG

set JSON = ~$USER/.aah-classifierSets.json
if (! -e "$JSON") then
    echo "$APP-$API ($0 $$) -- no $JSON" >>! $TMP/LOG
else
    echo "$APP-$API ($0 $$) -- using $JSON" >>! $TMP/LOG
endif


echo "Content-Type: application/json; charset=utf-8"
echo "Access-Control-Allow-Origin: http://age-at-home.mybluemix.net/*"
set AGE = `echo "$SECONDS - $DATE" | bc`
echo "Age: $AGE"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo ""
/usr/local/bin/jq '.humans[].name' "$JSON"
