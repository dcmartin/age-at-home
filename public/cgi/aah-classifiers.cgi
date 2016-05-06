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

if ($?CLOUDANT_URL) then
    setenv CU $CLOUDANT_URL
else
    if (-e ~$USER/.cloudant_url) then
        set cc = ( `cat ~$USER/.cloudant_url` )
        if ($#cc > 0) set CU = $cc[1]
        if ($#cc > 1) set CN = $cc[2]
        unset cc
    endif
    if ($?CN) then
        setenv CU "https://$CN.cloudant.com"
    else
        echo "$APP-$API ($0 $$) -- No Cloudant URL" >>! $TMP/LOG
        exit
    endif
endif

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed "s/.*db=\([^&]*\).*/\1/"`
    set FORCE = `echo "$QUERY_STRING" | sed "s/.*force=\([^&]*\).*/\1/"`
endif
if ($?DB == 0) then
    set DB = rough-fog
    setenv QUERY_STRING "db=$DB"
endif

set JSON = "$TMP/$APP-$API.$DATE.json"
if (! -e "$JSON" || $?FORCE) then
    echo "$APP-$API ($0 $$) -- creating ($JSON)" >>! $TMP/LOG
    rm -f "$TMP/$APP-$API.*.json"
    curl -s "$CU/$DB-stats/_all_docs" | /usr/local/bin/jq '.rows[].id' >! "$JSON"
else
    echo "$APP-$API ($0 $$) -- using $JSON" >>! $TMP/LOG
endif


echo "Content-Type: application/json"
echo "Refresh: $TTL"
set AGE = `echo "$SECONDS - $DATE" | bc`
echo "Age: $AGE"
echo "Cache-Control: max-age=$TTL"
echo -n "Last-Modified: "
date -r "$DATE"
echo ""
cat "$JSON"
