#!/bin/tcsh
setenv APP "aah"
setenv API "stats"
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
        if ($#cc > 2) set CP = $cc[3]
        unset cc
    endif
    if ($?CN && $?CP) then
        setenv CU "https://$CN":"$CP"@"$CN.cloudant.com"
    else
        echo "$APP-$API ($0 $$) -- No Cloudant URL" >>! $TMP/LOG
        exit
    endif
endif

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed "s/.*db=\([^&]*\).*/\1/"`
    set class = `echo "$QUERY_STRING" | sed "s/.*id=\([^&]*\)/\1/"`
endif
if ($?DB == 0) then
    set DB = rough-fog
    set class = person
endif
setenv QUERY_STRING "db=$DB&id=$class"

set JSON = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
if (! -e "$JSON") then
    /bin/rm -f "$TMP/$APP-$API-$QUERY_STRING.*.json"
    echo "$APP-$API ($0 $$) -- initiating ./$APP-make-$API.bash ($JSON)" >>! $TMP/LOG
    ./$APP-make-$API.bash
    echo "$APP-$API ($0 $$) -- Returning Redirect: $CU/$DB-$API/$class" >>! $TMP/LOG
    echo "Status: 303 Temporary Redirect"
    echo "Content-Type: application/json"
    echo "Location: $CU/$DB-$API/$class"
    echo ""
else
    echo "$APP-$API ($0 $$) -- using $JSON" >>! $TMP/LOG
    echo "Content-Type: application/json"
    echo "Refresh: $TTL"
    set AGE = `echo "$SECONDS - $DATE" | bc`
    echo "Age: $AGE"
    echo "Cache-Control: max-age=$TTL"
    echo -n "Last-Modified: "
    date -r "$DATE"
    echo ""
    cat "$JSON"
endif
