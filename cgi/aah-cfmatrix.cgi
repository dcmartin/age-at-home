#!/bin/csh -fb
setenv APP "aah"
setenv API "cfmatrix"
setenv WWW "www.dcmartin.com"
setenv LAN "192.168.1"

setenv DEBUG true

if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

# don't update statistics more than once per 15 minutes
set TTL = `echo "0.25 * 60" | bc`
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo `date` "$0 $$ -- START" >>& "$TMP/LOG"

if ($?QUERY_STRING) then
    set db = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
    set model = `echo "$QUERY_STRING" | sed 's/.*model=\([^&]*\).*/\1/'`
    if ($model == "$QUERY_STRING") set model = default
else
    set db = rough-fog
    set model = default
endif

if ($?db && $?model) then
    setenv QUERY_STRING "db=$db&model=$model"
else if ($?model) then
    setenv QUERY_STRING "model=$model"
else if ($?db) then
    setenv QUERY_STRING "db=$db"
else
    setenv QUERY_STRING ""
endif

echo `date` "$0 $$ -- QUERY_STRING ($QUERY_STRING)" >>& "$TMP/LOG"

if (-s ~$USER/.cloudant_url) then
    set cc = ( `cat ~$USER/.cloudant_url` )
    if ($#cc > 0) set CU = $cc[1]
    if ($#cc > 1) set CN = $cc[2]
endif

if ($?CLOUDANT_URL) then
    setenv CU $CLOUDANT_URL
else if ($?CN) then
    set CU = "$CN.cloudant.com"
else
    echo `date` "$0 $$ -- no Cloudant URL" >>& $TMP/LOG
    goto done
endif

set creds = ~$USER/.watson.visual-recognition.json
if (-s $creds) then
    set api_key = ( `/usr/local/bin/jq -r '.[0]|.credentials.api_key' "$creds"` )
    if ($?DEBUG) echo `date` "$0 $$ -- USING APIKEY $api_key" >>& "$TMP/LOG"
    set url = ( `/usr/local/bin/jq -r '.[0]|.credentials.url' "$creds"` )
    if ($?DEBUG) echo `date` "$0 $$ -- USING URL $url" >>& "$TMP/LOG"
    # set base
    set TU = $url
    echo `date` "$0 $$ -- CREDENTIALS ($creds); $TU" >>& "$TMP/LOG"
else if ($?TU == 0) then
    echo `date` "$0 $$ -- NO CREDENTIALS ($creds); create file and copy credentials from visual-recognition service on bluemix.net" >>& "$TMP/LOG"
    goto done
endif

if ($?verid == 0) set verid = "v3"
if ($?vdate == 0) set vdate = "2016-05-20"

if ($model != "default") then
    set classifiers = ( `curl -q -s -L "$TU/$verid/classifiers?api_key=$api_key&version=$vdate" | /usr/local/bin/jq -r '.classifiers[]|select(.classifier_id=="'"$model"'").classifier_id'` )
else if ($?db) then
    set classifiers = ( `curl -q -s -L "$TU/$verid/classifiers?api_key=$api_key&version=$vdate" | /usr/local/bin/jq -r '.classifiers[]|select(.name=="'"$db"'")|select(.status=="ready").classifier_id'` )
endif

if ($#classifiers) then
    set model = $classifiers[1]
else
    echo `date` "$0 $$ -- NO MODEL SPECIFIED" >>& "$TMP/LOG"
endif

set OUTPUT = "$TMP/matrix/$model.json"
if (-s "$OUTPUT") then
    echo "Content-Type: application/json; charset=utf-8"
    echo "Access-Control-Allow-Origin: *"
    set AGE = `echo "$SECONDS - $DATE" | bc`
    echo "Age: $AGE"
    echo "Cache-Control: max-age=$TTL"
    echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
    echo ""
    cat "$OUTPUT"
else
    echo "Content-Type: application/json; charset=utf-8"
    echo "Access-Control-Allow-Origin: *"
    echo "Cache-Control: no-cache"
    echo ""
    echo '{"model":"'"$model"'","status":"notfound"}'
else
    # return redirect
    set URL = "https://$CU/$db-$API/$model?include_docs=true"
    echo `date` "$0 $$ -- returning redirect ($URL)" >>! $TMP/LOG
    set AGE = `echo "$SECONDS - $DATE" | bc`
    echo "Age: $AGE"
    echo "Cache-Control: max-age=$TTL"
    echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
    echo "Status: 302 Found"
    echo "Location: $URL"
    echo ""
endif

done:

echo `date` "$0 $$ -- FINISH" >>& $TMP/LOG
