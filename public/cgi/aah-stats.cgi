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

if ($?QUERY_STRING != 0 && $QUERY_STRING != "") then
    set DB = `echo $QUERY_STRING | sed "s/.*db=\([^&]*\).*/\1/"`
    set class = `echo $QUERY_STRING | sed "s/.*id=\([A-Z]*[a-z]*\).*/\1/"`
else
    set DB = rough-fog
    set class = person
    setenv QUERY_STRING `echo "db=$DB&id=$class"`
endif

set JSON = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
if (! -e "$JSON") then
    echo "$APP-$API ($0 $$) -- Initiating ./$APP-make-$API.bash ($JSON)" >>! $TMP/LOG
    ./$APP-make-$API.bash
endif

set JSON = ( `ls -1t "$TMP/$APP-$API-$QUERY_STRING".*.json` )

if ($#JSON == 0) then
    echo "$APP-$API ($0 $$) -- Returning Redirect: $CU/$DB-$API/$class" >>! $TMP/LOG
    echo "Status: 303 Temporary Redirect"
    echo "Content-Type: application/json"
    echo "Location: $CU/$DB-$API/$class"
    echo ""
else if ($#JSON > 0) then
    if (-e "$JSON[1]") then
	echo "$APP-$API ($0 $$) -- Using $JSON[1]" >>! $TMP/LOG

	echo "Content-Type: application/json"
	echo "Refresh: $TTL"
	set AGE = `echo "$SECONDS - $DATE" | bc`
	echo "Age: $AGE"
	echo "Cache-Control: max-age=$TTL"
	echo -n "Last-Modified: "
	date -r "$DATE"
	echo ""
	cat "$JSON[1]"
	if ($#JSON > 1) rm -f $JSON[2-]
    else
	echo "$API -- Processing $JSON" >>! $TMP/LOG
	echo "Status: 307 Temporary Redirect"
	echo "Content-Type: application/json"
	echo "Location: $CU/$DB-$API/$class"
	echo ""
    endif
endif
