#!/bin/csh -fb
setenv APP "aah"
setenv API "classify"
setenv WWW "www.dcmartin.com"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

# don't update statistics more than once per 12 hours
set TTL = 15
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo "BEGIN: $APP-$API ($0 $$) - " $DATE >>! $TMP/LOG

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($DB == "$QUERY_STRING") unset DB
    set class = `echo "$QUERY_STRING" | sed 's/.*id=\([^&]*\).*/\1/'`
    if ($class == "$QUERY_STRING") unset class
    set match = `echo "$QUERY_STRING" | sed 's/.*match=\([^&]*\).*/\1/'`
    if ($match == "$QUERY_STRING") unset match
endif

#
# defaults (rough-fog; NO_TAGS; <this-month>*)
#
if ($?DB == 0) set DB = rough-fog
if ($?class == 0) set class = NO_TAGS
if ($?match == 0) set match = `date '+%Y%m'`

# standardize QUERY_STRING to cache results
setenv QUERY_STRING "db=$DB&id=$class&match=$match"

# output set
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

# check OUTPUT exists
if (-e "$OUTPUT") then
    echo "DEBUG: $APP-$API ($0 $$) -- existing ($OUTPUT)" >>! $TMP/LOG
    goto output
else
    # remove old 
    rm -f "$TMP/$APP-$API-$QUERY_STRING."*".json"
    # get review information (hmmm..)
    set IMAGES = "$TMP/$APP-$API-images.$$.json"
    echo "DEBUG: $APP-$API ($0 $$) -- getting $IMAGES" >>! $TMP/LOG
    curl -L -q -s "http://www.dcmartin.com/CGI/aah-images.cgi?db=$DB&id=$class&match=$match" >! "$IMAGES"
    if ($status == 0 && (-s "$IMAGES")) then
	# get seqid 
	set seqid = ( `/usr/local/bin/jq '.seqid' "$IMAGES"` )
	if ($status == 0 && $#seqid > 0) then
	    echo "DEBUG: $APP-$API ($0 $$) -- SUCCESS: SEQID = $seqid" >>! $TMP/LOG
	else
	    echo "ERROR:$APP-$API ($0 $$) -- no SEQUENCE ID" >>! $TMP/LOG
	    goto done
	endif
    else
	echo "ERROR: $APP-$API ($0 $$) -- no $IMAGES" >>! $TMP/LOG
	goto done
    endif


    set NEW = "$OUTPUT.$$"
    set CDIR = "$TMP/$DB/$class"
    set MIXPANELJS = "http://$WWW/CGI/script/mixpanel-aah.js"

    echo '<HTML>' >! "$NEW"
    echo '<script type="text/javascript" src="'$MIXPANELJS'"></script><script>mixpanel.track('"'"$APP-$API"');</script>" >> "$NEW"
    echo '<BODY>' >> "$NEW"

    echo "<h1>$DB $class $match</h1>" >> "$NEW"
    echo "<b>" `date` "</b>" >> "$NEW"
    echo "<p>$seqid</p>" >> "$NEW"

    foreach image ( `/usr/local/bin/jq '.images[]' "$IMAGES" | sed 's/"//g'` )
	echo '<img src="http://'"$WWW/$APP/$DB/$class/$image"'">' >> "$NEW"
    end

    echo '</BODY>' >> "$NEW"
    echo '</HTML>' >> "$NEW"

    rm -f "$IMAGES"

    mv "$NEW" "$OUTPUT"
endif

output:

#
# prepare for output
#
echo "Content-Type: text/html; charset=utf-8"
set AGE = `echo "$SECONDS - $DATE" | bc`
echo "Age: $AGE"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo ""

cat "$OUTPUT"

done:

echo "FINISH: $APP-$API ($0 $$) - " $DATE >>! $TMP/LOG
