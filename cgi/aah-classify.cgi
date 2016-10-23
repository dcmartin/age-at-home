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
    echo `date` "$0 $$ -- get http://$WWW/CGI/$APP-images.cgi?db=$DB&id=$class&match=$match&limit=$limit" >>! $TMP/LOG
    curl -L -q -s "http://$WWW/CGI/$APP-images.cgi?db=$DB&id=$class&match=$match&limit=$limit" >! "$IMAGES"
    if ($status == 0 && (-s "$IMAGES")) then
	# echo -n `date` "$0 $$ -- got " >>! $TMP/LOG
	# /usr/local/bin/jq -c '.' "$IMAGES" >>! $TMP/LOG
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
    echo "<HEAD><TITLE>Label Images ($DB/$class/$match/$limit)</TITLE></HEAD>" >> "$NEW"
    echo '<script type="text/javascript" src="'$MIXPANELJS'"></script><script>mixpanel.track('"'"$APP-$API"');</script>" >> "$NEW"
    echo '<BODY>' >> "$NEW"

    echo "<H1>" >> "$NEW"
    echo "LABEL IMAGES" >> "$NEW"
    echo "</H1>" >> "$NEW"
    # echo '{ "device":"'$DB'","id":"'$class'","match":"'$match'","limit":"'$limit'" }' >> "$NEW"
    if ($#date > 0) echo "<h3>Last updated: <i>" `date -r $date` "</i></h3>" >> "$NEW"
    # if ($#seqid > 0) echo "<h4>$seqid</h4>" >> "$NEW"
    echo '<p><b>Instructions:</b> Click on an image to label as "person" or choose class from menu and click "OK"</p>' >> "$NEW"

    # get all classes
    set allclasses = ( `curl -s -q -L "http://$WWW/CGI/aah-review.cgi?db=$DB" | /usr/local/bin/jq -c '.classes|sort_by(.count)[]|.name' | sed 's/"//g'` )

    # start table
    echo '<table border="1"><tr>' >> "$NEW"
    @ nimg = 0
    @ ncolumns = 5
    @ width = 100

    # process images
    foreach image ( `/usr/local/bin/jq '.images[]' "$IMAGES" | sed 's/"//g'` )
	if ($class == all) then
	    # class of image is encoded as head of path, e.g. <class>/<jpeg>
	    set dir = $image:h
	    set jpg = $image:t
	    set txt = "$image:h"
	else
	    set dir = $class
	    set jpg = $image
	    set txt = "$class"
	endif
	set img = "http://$WWW/$APP/$DB/$dir/$jpg"
	set ref = "http://$WWW/CGI/$APP-classify.cgi?db=$DB&match=$match&limit=$limit&id=$dir"
	set act = "http://$WWW/CGI/$APP-label.cgi"
	set cgi = "$act?db=$DB&id=$dir&image=$jpg&class=person"

        if ($nimg % $ncolumns == 0) echo '</tr><tr>' >> "$NEW"
	echo '<td><figure>' >> "$NEW"

	echo '<form id="classform" action="'"$act"'" method="get">' >> "$NEW"
	echo '<input type="hidden" name="DB" value="'"$DB"'">' >> "$NEW"
	echo '<input type="hidden" name="id" value="'"$dir"'">' >> "$NEW"
	echo '<input type="hidden" name="image" value="'"$jpg"'">' >> "$NEW"
	# create selection list
	echo '<select name="class">' >> "$NEW"
	foreach c ( $allclasses )
	    if ($c != "NO_TAGS") echo '<option value="'"$c"'"">'"$c"'</option>' >> "$NEW"
	end
	echo '</select>' >> "$NEW"
	echo '<input type="submit" value="OK">' >> "$NEW"
	echo '</form>' >> "$NEW"

	echo '<a href="'"$cgi"'"><img width="'$width'%" alt="'$class/$image'" src="'"$img"'"></a>' >> "$NEW"
	if ($class == all) echo '<figcaption>Class <a href="'"$ref"'">'"$txt"'</a></figcaption>' >> "$NEW" 

	echo '</figure></td>' >> "$NEW"
	@ nimg++
    end

    echo "</tr></table>" >> "$NEW"

    echo '</BODY>' >> "$NEW"
    echo '</HTML>' >> "$NEW"

    # done with images
    rm -f "$IMAGES"

    # remove old 
    set old = ( `ls -1 "$TMP/$APP-$API-$QUERY_STRING".*.json` )
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
echo "Age: $age"
set refresh = `echo "$TTL - $age" | bc`
echo "Refresh: $refresh"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo ""
cat "$OUTPUT"

done:

echo `date` "$0 $$ -- FINISH ($QUERY_STRING)" >>! $TMP/LOG
