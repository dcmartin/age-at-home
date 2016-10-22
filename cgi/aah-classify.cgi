#!/bin/csh -fb
setenv APP "aah"
setenv API "classify"
setenv WWW "www.dcmartin.com"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

# don't update statistics more than once per (in seconds)
set TTL = 15
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

# default image limit
if ($?IMAGE_LIMIT == 0) setenv IMAGE_LIMIT 100

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

echo `date` "$0 $$ -- START ($QUERY_STRING)" >>! $TMP/LOG

# output set
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

# check OUTPUT exists
if (-e "$OUTPUT") then
    echo `date` "$0 $$ -- returning existing ($OUTPUT)" >>! $TMP/LOG
    goto output
else
    # get review information (hmmm..)
    set IMAGES = "$TMP/$APP-$API-images.$$.json"
    echo `date` "$0 $$ -- get http://www.dcmartin.com/CGI/aah-images.cgi?db=$DB&id=$class&match=$match&limit=$limit" >>! $TMP/LOG
    curl -L -q -s "http://$WWW/CGI/$APP-images.cgi?db=$DB&id=$class&match=$match&limit=$limit" >! "$IMAGES"
    if ($status == 0 && (-s "$IMAGES")) then
	echo -n `date` "$0 $$ -- got " >>! $TMP/LOG
	/usr/local/bin/jq -c '.' "$IMAGES" >>! $TMP/LOG
	# get seqid 
	set seqid = ( `/usr/local/bin/jq '.seqid' "$IMAGES"` )
	if ($status == 0 && $#seqid > 0) then
	    echo `date` "$0 $$ -- success with seqid ($seqid)" >>! $TMP/LOG
	else
	    echo `date` "$0 $$ -- failure bad seqid ($seqid)" >>! $TMP/LOG
	    set seqid = ()
	endif
	set date = ( `/usr/local/bin/jq '.date' "$IMAGES" | sed 's/"//g'` )
	if ($status == 0 && $#date > 0) then
	    echo `date` "$0 $$ -- success with date ($date)" >>! $TMP/LOG
	else
	    echo `date` "$0 $$ -- failure with date ($date)" >>! $TMP/LOG
	    set date = () 
	endif
    else
	echo `date` "$0 $$ -- failure no images" >>! $TMP/LOG
	goto done
    endif


    set NEW = "$OUTPUT.$$"
    set CDIR = "$TMP/$DB/$class"
    set MIXPANELJS = "http://$WWW/CGI/script/mixpanel-aah.js"

    echo '<HTML>' >! "$NEW"
    echo "<HEAD><TITLE>$DB $class $match $limit</TITLE></HEAD>" >> "$NEW"
    echo '<script type="text/javascript" src="'$MIXPANELJS'"></script><script>mixpanel.track('"'"$APP-$API"');</script>" >> "$NEW"
    echo '<BODY>' >> "$NEW"

    echo "<H1>" >> "$NEW"
    echo '{ "device":"'$DB'","id":"'$class'","match":"'$match'","limit":"'$limit'" }' >> "$NEW"
    echo "</H1>" >> "$NEW"
    if ($#date > 0) then
	echo `date` "$0 $$ -- date ($date)" >>! $TMP/LOG
	echo "<h2>" `date -r $date` "</h2>" >> "$NEW"
    endif
    if ($#seqid > 0) then
	echo `date` "$0 $$ -- seqid ($seqid)" >>! $TMP/LOG
	echo "<h3>$seqid</h3>" >> "$NEW"
    endif

    # process images
    foreach image ( `/usr/local/bin/jq '.images[]' "$IMAGES" | sed 's/"//g'` )
	set url = "http://$WWW/CGI/$APP-label.cgi?db=$DB&id=$class&image=$image"
	echo '<a href="'"$url"'">' >> "$NEW"
	set url = "http://$WWW/$APP/$DB/$class/$image"
	echo '<img alt="'$class/$image'" width="20%" src="'"$url"'"></a>' >> "$NEW"
    end

    echo '</BODY>' >> "$NEW"
    echo '</HTML>' >> "$NEW"

    # done with images
    rm -f "$IMAGES"

    # remove old 
    set old = ( `ls -1 "$OUTPUT:r:r"*.json` )
    if ($#old > 0) then
	echo `date` "$0 $$ -- removing old ($old)" >>! $TMP/LOG
	rm -f $old
    endif

    # new OUTPUT
    mv "$NEW" "$OUTPUT"
endif

output:

#
# prepare for output
#
echo "Content-Type: text/html; charset=utf-8"
set age = `echo "$SECONDS - $DATE" | bc`
set refresh = `echo "$TTL - $age" | bc`
echo "Age: $age"
echo "Refresh: $refresh"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo ""
cat "$OUTPUT"

done:

echo `date` "$0 $$ -- FINISH ($QUERY_STRING)" >>! $TMP/LOG
