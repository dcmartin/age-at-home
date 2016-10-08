#!/bin/csh -fb
setenv APP "aah"
setenv API "countCSV"
setenv WWW "http://www.dcmartin.com/CGI/"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"
# don't update statistics more than once per 15 minutes
set TTL = `echo "30 * 60" | bc`
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo ">>> $APP-$API ($0 $$)" `date` >>! $TMP/LOG

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed "s/.*db=\([^&]*\).*/\1/"`
    if ($#DB == 0) set DB = rough-fog
    set ALG = `echo "$QUERY_STRING" | sed "s/.*alg=\([^&]*\).*/\1/"`
    if ($#ALG == 0) set ALG = visual
else
    set DB = rough-fog
    set ALG = visual
endif
setenv QUERY_STRING "db=$DB&alg=$ALG"

set OUTPUT = "$TMP/$APP-$API.$QUERY_STRING.$DATE.csv"
if (! -e "$OUTPUT") then
    rm -f $TMP/$APP-$API.$QUERY_STRING.*.csv
    if ($DB == "damp-cloud") then
	if ($ALG == "visual") then
	    curl -L -s -q -o "$OUTPUT" "https://ibmcds.looker.com/looks/vmFgFKSvCpN6qY2JjyZWnCjzrh3qSHK7.csv?apply_formatting=true"
	else if ($ALG == "alchemy") then
	    # ALCHEMY ALL - https://ibmcds.looker.com/looks/NGrbjz6SFfWspMzQ8pb7VN92Cr9qZNtr.csv?apply_formatting=true
	endif
    else if ($DB == "rough-fog") then
	if ($ALG == "visual") then
	    curl -L -s -q -o "$OUTPUT" "https://ibmcds.looker.com/looks/vQFVvQSgTFKHpgfmrPXKc8bsspQ2pF2Z.csv?apply_formatting=true"
	else
	    # ALCHEMY ALL - https://ibmcds.looker.com/looks/4qFmv5338FTCnbRWG47K6fG5vggfNxwN.csv?apply_formatting=true
	endif
    endif
    if ($DB == "damp-cloud") then
	if ($ALG == "visual") then
	    cat "$OUTPUT" \
		| sed "s/Intervals Interval/Interval/" \
		| sed "s/\([^ ]*\) Dampcloud Visual Scores Count/\1/g" >> "$OUTPUT".$$
	else if ($ALG == "alchemy") then
	    cat "$OUTPUT" \
		| sed "s/Intervals Interval/Interval/" \
		| sed "s/\([^ ]*\) Dampcloud Count/\1/g" >> "$OUTPUT".$$
	endif
    else if ($DB == "rough-fog") then
	if ($ALG == "visual") then
	    cat "$OUTPUT" \
		| sed "s/Intervals Interval/Interval/" \
		| sed "s/\([^ ]*\) Roughfog Visual Scores Count/\1/g" >> "$OUTPUT".$$
	else if ($ALG == "alchemy") then
	    cat "$OUTPUT" \
		| sed "s/Intervals Interval/Interval/" \
		| sed "s/\([^ ]*\) Roughfog Count/\1/g" >> "$OUTPUT".$$

	    # ALCHEMY
	endif
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
