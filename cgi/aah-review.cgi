#!/bin/csh -fb
setenv APP "aah"
setenv API "review"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

# don't update statistics more than once per 12 hours
set TTL = `echo "12 * 60 * 60" | bc`
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo "BEGIN: $APP-$API ($0 $$) " $DATE >>! $TMP/LOG

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($DB == "$QUERY_STRING") unset DB
    # set class = `echo "$QUERY_STRING" | sed 's/.*id=\([^&]*\).*/\1/'`
    # if ($class == "$QUERY_STRING") unset class
    # set day = `echo "$QUERY_STRING" | sed 's/.*day=\([^&]*\).*/\1/'`
    # if ($day == "$QUERY_STRING") unset day
    # set interval = `echo "$QUERY_STRING" | sed 's/.*interval=\([^&]*\).*/\1/'`
    # if ($interval == "$QUERY_STRING") unset interval
endif

if ($?DB == 0) set DB = rough-fog
if ($?class == 0) set class = all
setenv QUERY_STRING "db=$DB&id=$class"

if (-e ~$USER/.cloudant_url) then
    set cc = ( `cat ~$USER/.cloudant_url` )
    if ($#cc > 0) set CU = $cc[1]
    if ($#cc > 1) set CN = $cc[2]
endif

if ($?CLOUDANT_URL) then
    set CU = $CLOUDANT_URL
else if ($?CN) then
    set CU = "$CN"@"$CN.cloudant.com"
else
    echo "DEBUG: $APP-$API ($0 $$) -- no Cloudant URL" >>! $TMP/LOG
    goto done
endif

# output set
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

# check OUTPUT exists
if (-s "$OUTPUT") then
    echo "DEBUG: $APP-$API ($0 $$) -- existing ($OUTPUT)" >>! $TMP/LOG
    goto output
else
    echo "DEBUG: $APP-$API ($0 $$) ++ requesting ($OUTPUT)" >>! $TMP/LOG
    ./$APP-make-$API.bash
    # find old results
    set OLD = ( `ls -1t "$TMP/$APP-$API-$QUERY_STRING".*.json` )
    if ($#OLD == 0) then
        set URL = "https://$CU/$DB-$API/$class"
	echo "DEBUG: $APP-$API ($0 $$) -- returning redirect ($URL)" >>! $TMP/LOG
	echo "Status: 302 Found"
	echo "Location: $URL"
	echo ""
	goto done
    else if ($#OLD > 0) then
	echo "DEBUG: $APP-$API ($0 $$) == OLD $OUTPUT ($OLD)" >>! $TMP/LOG
	set OUTPUT = "$OLD[1]"
	if ($#OLD > 1) then
	    echo "DEBUG: $APP-$API ($0 $$) -- DELETING $OLD[2-]" >>! $TMP/LOG
	    /bin/rm -f "$OLD[2-]"
	endif
    endif
endif

if ($#OUTPUT == 0) then
    echo "DEBUG: $APP-$API ($0 $$) ** NONE ($OUTPUT)" >>! $TMP/LOG
    echo "Status: 202 Accepted"
    goto done
else if (-s "$OUTPUT") then
    echo "DEBUG: $APP-$API ($0 $$) -- FOUND ($OUTPUT)" >>! $TMP/LOG
endif

# output
output:

#
# prepare for output
#
echo "Content-Type: application/json; charset=utf-8"
echo "Access-Control-Allow-Origin: *"
set AGE = `echo "$SECONDS - $DATE" | bc`
echo "Age: $AGE"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo ""

cat "$OUTPUT"

# done
done:

echo "FINISH: $APP-$API ($0 $$) " $DATE >>! $TMP/LOG
