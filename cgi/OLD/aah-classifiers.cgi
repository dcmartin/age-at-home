#!/bin/tcsh
setenv APP "aah"
setenv API "classifiers"

if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

# don't update statistics more than once per 15 minutes
set TTL = `echo "30 * 60" | bc`
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo `date` "$0 $$ -- START" >>! $TMP/LOG

if (-e ~$USER/.cloudant_url) then
    echo `date` "$0 $$ -- ~$USER/.cloudant_url" >>! $TMP/LOG
    set cc = ( `cat ~$USER/.cloudant_url` )
    if ($#cc > 0) set CU = $cc[1]
    if ($#cc > 1) set CN = $cc[2]
endif

if ($?CLOUDANT_URL) then
    set CU = $CLOUDANT_URL
else if ($?CN) then
    set CU = "$CN.cloudant.com"
else
    echo `date` "$0 $$ -- no Cloudant URL" >>! $TMP/LOG
    goto done
endif

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed "s/.*db=\([^&]*\).*/\1/"`
    if ($#DB == 0) set DB = rough-fog
else
    set DB = rough-fog
endif
setenv QUERY_STRING "db=$DB"

set JSON = "$TMP/$APP-$API.$QUERY_STRING$DATE.json"
if (! -e "$JSON") then
    echo `date` "$0 $$ -- removing old ($TMP/$APP-$API.*.json)" >>! $TMP/LOG
    rm -f "$TMP/$APP-$API.$QUERY_STRING".*.json
    echo `date` "$0 $$ -- curl $CU/$DB-stats/_all_docs ($JSON)" >>! $TMP/LOG
    curl -s "$CU/$DB-stats/_all_docs" | /usr/local/bin/jq '.rows[].id' >! "$JSON"
else
    echo `date` "$0 $$ -- using existing ($JSON)" >>! $TMP/LOG
endif


echo "Content-Type: application/json; charset=utf-8"
echo "Access-Control-Allow-Origin: *"
set AGE = `echo "$SECONDS - $DATE" | bc`
echo "Age: $AGE"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo ""
cat "$JSON"

done:
echo `date` "$0 $$ -- FINISH" >>! $TMP/LOG
