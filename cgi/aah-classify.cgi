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

# default image limit
if ($?IMAGE_LIMIT == 0) setenv IMAGE_LIMIT 100

echo `date` "$0 $$ - START" >>! $TMP/LOG

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($DB == "$QUERY_STRING") unset DB
    set class = `echo "$QUERY_STRING" | sed 's/.*id=\([^&]*\).*/\1/'`
    if ($class == "$QUERY_STRING") unset class
    set match = `echo "$QUERY_STRING" | sed 's/.*match=\([^&]*\).*/\1/'`
    if ($match == "$QUERY_STRING") unset match
    set limit = `echo "$QUERY_STRING" | sed 's/.*limit=\([^&]*\).*/\1/'`
    if ($limit == "$QUERY_STRING") unset limit
endif

#
# defaults (rough-fog; NO_TAGS; <this-month>*)
#
if ($?DB == 0) set DB = rough-fog
if ($?class == 0) set class = NO_TAGS
if ($?match == 0) set match = `date '+%Y%m'`
if ($?limit == 0) set limit = $IMAGE_LIMIT

# standardize QUERY_STRING to cache results
setenv QUERY_STRING "db=$DB&id=$class&match=$match&limit=$limit"

# output set
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

# check OUTPUT exists
if (-e "$OUTPUT") then
    echo `date` "$0 $$ -- returning existing ($OUTPUT)" >>! $TMP/LOG
    goto output
else
    # get review information (hmmm..)
    set IMAGES = "$TMP/$APP-$API-images.$$.json"
    echo `date` "$0 $$ -- curl aah-images $DB $class $match into $IMAGES" >>! $TMP/LOG
    curl -L -q -s "http://www.dcmartin.com/CGI/aah-images.cgi?db=$DB&id=$class&match=$match" >! "$IMAGES"
    if ($status == 0 && (-s "$IMAGES")) then
	# get seqid 
	set seqid = ( `/usr/local/bin/jq '.seqid' "$IMAGES"` )
	if ($status == 0 && $#seqid > 0) then
	    echo `date` "$0 $$ -- success with seqid ($seqid)" >>! $TMP/LOG
	else
	    echo `date` "$0 $$ -- failure bad seqid ($seqid)" >>! $TMP/LOG
	    goto done
	endif
	set date = ( `/usr/local/bin/jq '.date' "$IMAGES"` )
	if ($status == 0 && $#date > 0) then
	    echo `date` "$0 $$ -- success with date ($date)" >>! $TMP/LOG
	else
	    echo `date` "$0 $$ -- failure with date ($date)" >>! $TMP/LOG
	    set date = "Unspecified"
	endif
    else
	echo `date` "$0 $$ -- failure no images" >>! $TMP/LOG
	goto done
    endif


    set NEW = "$OUTPUT.$$"
    set CDIR = "$TMP/$DB/$class"
    set MIXPANELJS = "http://$WWW/CGI/script/mixpanel-aah.js"

    echo '<HTML>' >! "$NEW"
    echo '<script type="text/javascript" src="'$MIXPANELJS'"></script><script>mixpanel.track('"'"$APP-$API"');</script>" >> "$NEW"
    echo '<BODY>' >> "$NEW"

    echo "<h1>$DB $class $match</h1>" >> "$NEW"
    echo "<b>"$date"</b>" >> "$NEW"
    echo "<p>$seqid</p>" >> "$NEW"

    # process images
    foreach image ( `/usr/local/bin/jq '.images[]' "$IMAGES" | sed 's/"//g'` )
	echo '<img src="http://'"$WWW/$APP/$DB/$class/$image"'">' >> "$NEW"
    end

    echo '</BODY>' >> "$NEW"
    echo '</HTML>' >> "$NEW"

    # done with images
    rm -f "$IMAGES"

    # remove old 
    echo `date` "$0 $$ -- removing old $OUTPUT:r:r" >>! $TMP/LOG
    rm -f "$OUTPUT:r:r"*.json

    # new OUTPUT
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

echo `date` "$0 $$ - FINISH" >>! $TMP/LOG
