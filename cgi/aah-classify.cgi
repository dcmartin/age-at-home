#!/bin/csh -fb
setenv APP "aah"
setenv API "classify"
setenv WWW "www.dcmartin.com"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

# don't update review information more than once per (in seconds)
set TTL = 300
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

# default image limit
if ($?IMAGE_LIMIT == 0) setenv IMAGE_LIMIT 100

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($DB == "$QUERY_STRING") unset DB
    set id = `echo "$QUERY_STRING" | sed 's/.*id=\([^&]*\).*/\1/'`
    if ($id == "$QUERY_STRING") unset id
    set match = `echo "$QUERY_STRING" | sed 's/.*match=\([^&]*\).*/\1/'`
    if ($match == "$QUERY_STRING") unset match
    set limit = `echo "$QUERY_STRING" | sed 's/.*limit=\([^&]*\).*/\1/'`
    if ($limit == "$QUERY_STRING") unset limit
    set assign = `echo "$QUERY_STRING" | sed 's/.*assign=\([^&]*\).*/\1/'`
    if ($assign == "$QUERY_STRING") unset assign
endif

#
# defaults (rough-fog; NO_TAGS; <this-month>*)
#
if ($?DB == 0) set DB = rough-fog
if ($?id == 0) set id = NO_TAGS
if ($?match == 0) set match = `date '+%Y%m'`
if ($?limit == 0) set limit = $IMAGE_LIMIT

# standardize QUERY_STRING to cache results
setenv QUERY_STRING "db=$DB&id=$id&match=$match"

echo `date` "$0 $$ -- START ($QUERY_STRING)" >>! $TMP/LOG

# output set
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

# check OUTPUT exists
if (-s "$OUTPUT") then
    if ($?DEBUG) echo `date` "$0 $$ -- using current ($OUTPUT)" >>! $TMP/LOG
else
    set old = ( `find "$TMP" -name "$APP-$API*" -print` )
    if ($#old > 0) then
	if ($?DEBUG) echo `date` "$0 $$ -- removing $old" >>! $TMP/LOG
	rm -f $old
    endif
    curl -s -q -L "http://$WWW/CGI/aah-review.cgi?db=$DB" -o "$OUTPUT"
endif

if (-s "$OUTPUT") then
    set MIXPANELJS = "http://$WWW/CGI/script/mixpanel-aah.js"
    set HTML = "$OUTPUT.$$"
    set CDIR = "$TMP/$DB/$id"

    # search all classes
    if ($id == all) set CDIR = "$TMP/$DB"

    # get date and seqid of results
    set date = `/usr/local/bin/jq -c '.date' "$OUTPUT" | sed 's/"//g'`
    set seqid = `/usr/local/bin/jq -c '.seqid' "$OUTPUT" | sed 's/"//g'`
    # get all classes in order of prevelance (small to large) from initial classification
    set allclasses = ( `/usr/local/bin/jq -c '.classes|sort_by(.count)[]|.name' "$OUTPUT" | sed 's/"//g'` )

    # header
    echo "<HTML><HEAD><TITLE>$APP-$API" >> "$HTML"
    echo '{ "device":"'$DB'","id":"'$id'","match":"'$match'","limit":"'$limit'" }' >> "$HTML"
    echo "</TITLE></HEAD>" >> "$HTML"
    echo '<script type="text/javascript" src="'$MIXPANELJS'"></script><script>mixpanel.track('"'"$APP-$API"');</script>" >> "$HTML"
    echo '<BODY><H1>LABEL IMAGES</H1>' >> "$HTML"

    if ($#date > 0) echo "<h3>Last updated: <i>" `date -r $date` "</i></h3>" >> "$HTML"
    if ($#seqid > 0) echo "<h4>$seqid</h4>" >> "$HTML"

    echo '<form action="http://'"$WWW/CGI/$APP-$API"'.cgi">' >> "$HTML"
    echo '<input type="hidden" name="db" value="'"$DB"'">' >> "$HTML"
    echo '<input type="text" name="match" value="'"$match"'">' >> "$HTML"
    echo '<input type="range" name="limit" value="'"$limit"'" max="'$IMAGE_LIMIT'" min="1">' >> "$HTML"
    echo '<select name="id">' >> "$HTML"
    echo '<option value="'"$id"'">'"$id"'</option>' >> "$HTML" # current class (dir) is first option
    echo '<option value="all">all</option>' >> "$HTML" # current class (dir) is first option
    foreach c ( $allclasses )
	if ($c != $id) echo '<option value="'"$c"'"">'"$c"'</option>' >> "$HTML" # don't include current class
    end
    echo '</select>' >> "$HTML"
    echo '<input type="submit" value="OK"></form>' >> "$HTML"

    echo '<p><b>Instructions:</b> Click on an image to label as "person" or choose class from menu and click "OK"</p>' >> "$HTML"

    if (-d "$CDIR") then
	set IMAGES = "$TMP/$APP-$API-$QUERY_STRING.$DATE.txt"
	if (-e "$IMAGES") then
	    if ($?assign) then
		if ($?DEBUG) echo `date` "$0 $$ -- removing $assign from old images for ($CDIR) matching ($match)" >>! $TMP/LOG
		cat "$IMAGES" | egrep -v "$assign" >! "$IMAGES.$$"
		mv -f "$IMAGES.$$" "$IMAGES"
	    endif
	else
	    set old = ( `ls -1 "$TMP/$APP-$API-$QUERY_STRING".*.txt` )
	    if ($#old > 1) then
		if ($?DEBUG) echo `date` "$0 $$ -- removing old find results ($old)" >>! $TMP/LOG
	    endif
	    if ($?DEBUG) echo `date` "$0 $$ -- finding images for ($CDIR) matching ($match)" >>! $TMP/LOG
	    find "$CDIR" -type f -name "$match*.jpg" -print | sort -t / -k 7,7 -n -r >! $IMAGES
	endif

	set nimage = `wc -l "$IMAGES" | awk '{ print $1 }'`

	@ ncolumns = 5
	if ($nimage < $ncolumns) @ ncolumns = $nimage
	@ width = 100

	# start table
	echo '<table border="1"><tr>' >> "$HTML"

        @ k = 0
        foreach image ( `head -"$limit" "$IMAGES"` )
            if ($k < $limit) then
                if ($?DEBUG) echo `date` "$0 $$ -- file ($image)" >>! $TMP/LOG

		if ($id == all) then
		    set dir = $image:h # class of image is encoded as head of path
		    set dir = $dir:t # and tail, e.g. <path>/<class>/<jpeg>
		    set jpg = $image:t
		    set txt = "$dir"
		else
		    set dir = $id
		    set jpg = $image:t
		    set txt = "$id"
		endif

		set img = "http://$WWW/$APP/$DB/$dir/$jpg"
		set ref = "http://$WWW/CGI/$APP-classify.cgi?db=$DB&match=$match&limit=$limit&id=$id&old=$dir"
		set act = "http://$WWW/CGI/$APP-label.cgi"
		set cgi = "$act?db=$DB&id=$id&match=$match&limit=$limit&image=$jpg&old=$dir&new=person"
		set time = `echo $jpg | sed "s/\(....\)\(..\)\(..\)\(..\)\(..\).*-.*/\1\/\2\/\3 \4:\5/"`

		if ($k % $ncolumns == 0) echo '</tr><tr>' >> "$HTML"

		echo '<td><figure>' >> "$HTML"
		echo '<form action="'"$act"'" method="get">' >> "$HTML"
		echo '<input type="hidden" name="db" value="'"$DB"'">' >> "$HTML"
		echo '<input type="hidden" name="id" value="'"$id"'">' >> "$HTML"
		echo '<input type="hidden" name="match" value="'"$match"'">' >> "$HTML"
		echo '<input type="hidden" name="limit" value="'"$limit"'">' >> "$HTML"
		echo '<input type="hidden" name="old" value="'"$dir"'">' >> "$HTML"
		echo '<input type="hidden" name="image" value="'"$jpg"'">' >> "$HTML"
		echo '<select name="new">' >> "$HTML"
		echo '<option value="'"$dir"'"">'"$dir"'</option>' >> "$HTML" # current class (dir) is first option
		foreach c ( $allclasses )
		    if ($c != $dir) echo '<option value="'"$c"'"">'"$c"'</option>' >> "$HTML" # don't include current class
		end
		echo '</select>' >> "$HTML"
		echo '<input type="submit" value="OK">' >> "$HTML"
		echo '</form>' >> "$HTML"
		echo '<a href="'"$cgi"'"><img width="'$width'%" alt="'$id/$image'" src="'"$img"'"></a>' >> "$HTML"
		# if ($id == all) echo '<figcaption><a href="'"$ref"'">'"$txt"'</a> '"$time"'</figcaption>' >> "$HTML" 
		echo '<figcaption>'"$time"'</figcaption>' >> "$HTML" 
		echo '</figure></td>' >> "$HTML"
	    else
	    	break
	    endif
	    @ k++
	end
	echo "</tr></table>" >> "$HTML"
    else
        if ($?DEBUG) echo `date` "$0 $$ -- directory $CDIR does not exist" >>! $TMP/LOG
    endif

    echo '</BODY>' >> "$HTML"
    echo '</HTML>' >> "$HTML"
endif

output:

#
# prepare for output
#
echo "Content-Type: text/html; charset=utf-8"
echo "Cache-Control: no-cache"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo ""
cat "$HTML"
rm "$HTML"

done:

echo `date` "$0 $$ -- FINISH ($QUERY_STRING)" >>! $TMP/LOG
