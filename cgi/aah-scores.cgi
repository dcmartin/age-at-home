#!/bin/csh -fb
setenv APP "aah"
setenv API "scores"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"
# don't update statistics more than once per 12 hours
set TTL = `echo "12 * 60 * 60" | bc`
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
    echo `date` "$0 $$ -- No Cloudant URL" >>! $TMP/LOG
    exit
endif

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed "s/.*db=\([^&]*\).*/\1/"` 
    set class = `echo "$QUERY_STRING" | sed "s/.*id=\([^&]*\)/\1/"`
endif
if ($#DB == 0) set DB = rough-fog
if ($#class == 0) set class = all
setenv QUERY_STRING "db=$DB&id=$class"

set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

if (-e "$OUTPUT") then
    echo `date` "$0 $$ == CURRENT $OUTPUT $DATE" >>! $TMP/LOG
else
    echo `date` "$0 $$ -- requesting output ($OUTPUT)" >>! $TMP/LOG
    ./$APP-make-$API.bash
    # remove old results
    rm -f "$OUTPUT:r:r".*.json
    # return redirect
    set URL = "https://$CU/$DB-$API/$class?include_docs=true"
    echo `date` "$0 $$ -- returning redirect ($URL)" >>! $TMP/LOG
    set AGE = `echo "$SECONDS - $DATE" | bc`
    echo "Age: $AGE"
    echo "Cache-Control: max-age=$TTL"
    echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
    echo "Status: 302 Found"
    echo "Location: $URL"
    echo ""
    goto done
endif

output:

# prepare for output
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
