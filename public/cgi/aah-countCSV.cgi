#!/bin/csh -fb
setenv APP "aah"
setenv API "countCSV"
setenv WWW "http://www.dcmartin.com/CGI/"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/tmp"
# don't update statistics more than once per 15 minutes
set TTL = `echo "30 * 60" | bc`
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo ">>> $APP-$API ($0 $$)" `date` >>! $TMP/LOG

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed "s/.*db=\([^&]*\).*/\1/"`
    if ($#DB == 0) set DB = rough-fog
else
    set DB = rough-fog
endif
setenv QUERY_STRING "db=$DB"

set OUTPUT = "$TMP/$APP-$API.$DB.$DATE.csv"
if (! -e "$OUTPUT") then
    rm -f $TMP/$APP-$API.$DB.*.csv
    if ($DB == "damp-cloud") then
	curl -L -s -q -o "$OUTPUT" "https://ibmcds.looker.com/looks/vmFgFKSvCpN6qY2JjyZWnCjzrh3qSHK7.csv?apply_formatting=true"
    else
	curl -L -s -q -o "$OUTPUT" "https://ibmcds.looker.com/looks/vQFVvQSgTFKHpgfmrPXKc8bsspQ2pF2Z.csv?apply_formatting=true"
    endif
    if ($DB == "damp-cloud") then
	cat "$OUTPUT" \
	    | sed "s/Intervals Interval/Interval/" \
	    | sed "s/\([^ ]\) Dampcloud Visual Scores Count/\1/g" >> "$OUTPUT".$$
    else
	cat "$OUTPUT" \
	    | sed "s/Intervals Interval/Interval/" \
	    | sed "s/\([^ ]*\) Roughfog Visual Scores Count/\1/g" >> "$OUTPUT".$$
    endif
    mv -f "$OUTPUT".$$ "$OUTPUT"
endif

echo "Content-Type: text/csv; charset=utf-8"
echo "Access-Control-Allow-Origin: *"
set AGE = `echo "$SECONDS - $DATE" | bc`
echo "Age: $AGE"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo ""
cat "$OUTPUT"
