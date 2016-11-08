#!/bin/csh -fb
setenv APP "aah"
setenv API "classify"
setenv WWW "www.dcmartin.com"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

# don't update file information more than once per (in seconds)
set TTL = 120
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

# default image limit
if ($?IMAGE_LIMIT == 0) setenv IMAGE_LIMIT 20

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
    set add = `echo "$QUERY_STRING" | sed 's/.*add=\([^&]*\).*/\1/'`
    if ($add == "$QUERY_STRING") set add = ""
endif

#
# defaults (rough-fog; NO_TAGS; <this-month>*)
#
if ($?DB == 0) set DB = rough-fog
if ($?id == 0) set id = NO_TAGS
if ($?match == 0) set match = `date '+%Y%m'`
if ($?limit == 0) set limit = $IMAGE_LIMIT

#
# location
#
if ($DB == "rough-fog") set location = "kitchen"
if ($DB == "damp-cloud") set location = "bathroom"

# standardize QUERY_STRING to cache results
setenv QUERY_STRING "db=$DB&id=$id&match=$match"

echo `date` "$0 $$ -- START ($QUERY_STRING)" >>! $TMP/LOG

set HTML = "$TMP/$APP-$API-$QUERY_STRING.$$.html"

# get review status
set REVIEW = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
curl -s -q -L "http://$WWW/CGI/aah-review.cgi?db=$DB" -o "$REVIEW"
if ($status != 0) then
    if ($?DEBUG) echo `date` "$0 $$ -- FAILURE: aah-review db=$DB" >>! $TMP/LOG
    goto done
endif

# get date and seqid of results
set date = `/usr/local/bin/jq -c '.date' "$REVIEW" | sed 's/"//g'`
set seqid = `/usr/local/bin/jq -c '.seqid' "$REVIEW" | sed 's/"//g'`
# get all classes in order of prevelance (small to large) from initial classification
set allclasses = ( `/usr/local/bin/jq -c '.classes|sort_by(.count)[]|.name' "$REVIEW" | sed 's/"//g'` )

set MIXPANELJS = "http://$WWW/CGI/script/mixpanel-aah.js"

# header
echo "<HTML><HEAD><TITLE>$APP-$API" >> "$HTML"
echo '{ "device":"'$DB'","id":"'$id'","match":"'$match'","limit":"'$limit'" }' >> "$HTML"
echo "</TITLE></HEAD>" >> "$HTML"
echo '<script type="text/javascript" src="'$MIXPANELJS'"></script><script>mixpanel.track('"'"$APP-$API"');</script>" >> "$HTML"
echo '<BODY><H1>LABEL IMAGES</H1>' >> "$HTML"
if ($#date > 0) echo '<p style="font-size:50%;">Last updated: <i>' `date -r $date` "</i></p>" >> "$HTML"
# if ($#seqid > 0) echo "<i>$seqid</i>" >> "$HTML"

echo '<form action="http://'"$WWW/CGI/$APP-$API"'.cgi">' >> "$HTML"
echo '<input type="hidden" name="db" value="'"$DB"'">' >> "$HTML"
echo '<input type="text" name="match" value="'"$match"'">' >> "$HTML"
echo '<input type="range" name="limit" value="'"$limit"'" max="'$IMAGE_LIMIT'" min="1">' >> "$HTML"
echo '<select name="id">' >> "$HTML"
echo '<option value="'"$id"'">'"$id"'</option>' >> "$HTML" # current class (dir) is first option
if ($id != "all") echo '<option value="all">all</option>' >> "$HTML" # all classes is second option
foreach c ( $allclasses )
    if ($c != $id) echo '<option value="'"$c"'"">'"$c"'</option>' >> "$HTML" # don't include current class
end
echo '</select>' >> "$HTML"
echo '<input type="submit" style="background-color:#ff9933" value="CHANGE"></form>' >> "$HTML"

echo '<p><b>Instructions:</b>  Click the button (e.g. <b>person</b>) when the image contains ONLY that entity.' >> "$HTML"
echo '<p>If the scene is empty, click the red button.  If the image contains multiple entities, click the SKIP button.' >> "$HTML"
echo '<p>To create a new entity, type the label and click the CREATE button.  You may also click on the image to label as <b>person</b><p>' >> "$HTML"

# find in one or all directories
if ($id == all) then
    set CDIR = "$TMP/$DB"
else
    set CDIR = "$TMP/$DB/$id"
endif

if (-d "$CDIR") then
    set IMAGES = "$TMP/$APP-$API-db=$DB&id=$id&match=$match.$DATE.txt"
    if (-s "$IMAGES") then
	if ($?assign) then
	    if ($?DEBUG) echo `date` "$0 $$ -- removing $assign from old images for ($CDIR) matching ($match)" >>! $TMP/LOG
	    cat "$IMAGES" | egrep -v "$assign" >! "$IMAGES.$$"
	    mv -f "$IMAGES.$$" "$IMAGES"
	endif
    else
	set old = ( `echo "$TMP/$APP-$API-db=$DB&id=$id&match=$match".*.txt` )
	if ($#old > 1) then
	    if ($?DEBUG) echo `date` "$0 $$ -- removing old find results ($old)" >>! $TMP/LOG
	    rm -f $old
	endif
	if ($?DEBUG) echo `date` "$0 $$ -- finding images for ($CDIR) matching ($match)" >>! $TMP/LOG
	find "$CDIR" -type f -name "$match*.jpg" -print | sort -t / -k 7,7 -n -r >! $IMAGES
    endif

    set nimage = `wc -l "$IMAGES" | awk '{ print $1 }'`

    @ ncolumns = 4
    if ($nimage < $ncolumns) @ ncolumns = $nimage
    @ width = 100

    # action to label image
    set act = "http://$WWW/CGI/$APP-label.cgi"

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
	    set cgi = "$act?db=$DB&id=$id&match=$match&limit=$limit&image=$jpg&old=$dir&new=person"
	    set time = `echo $jpg | sed "s/\(....\)\(..\)\(..\)\(..\)\(..\).*-.*/\1\/\2\/\3 \4:\5/"`

	    if ($k % $ncolumns == 0) echo '</tr><tr>' >> "$HTML"

	    echo '<td><figure>' >> "$HTML"
	    echo '<form action="'"$act"'" method="get">' >> "$HTML"
	    echo '<input type="hidden" name="db" value="'"$DB"'">' >> "$HTML"
	    echo '<input type="hidden" name="id" value="'"$id"'">' >> "$HTML"
	    echo '<input type="hidden" name="image" value="'"$jpg"'">' >> "$HTML"
	    echo '<input type="hidden" name="old" value="'"$dir"'">' >> "$HTML"
	    echo '<input type="hidden" name="match" value="'"$match"'">' >> "$HTML"
	    echo '<input type="hidden" name="limit" value="'"$limit"'">' >> "$HTML"
	    echo '<button style="background-color:#999999" type="submit" name="skip" value="'"$jpg"'"">SKIP</button>' >> "$HTML"
	    echo '<button style="background-color:#ff0033" type="submit" name="new" value="'"$location"'">'"$location"'</button>' >> "$HTML"
	    echo '<button style="background-color:#33cc00" type="submit" name="new" value="person">person</button>' >> "$HTML"
	    foreach i ( $TMP/label/$DB/* )
	        set j = "$i:t"
		if ($j != "$location" && $j != "person") then
		    echo '<button style="background-color:#6699ff" type="submit" name="new" value="'"$j"'">'"$j"'</button>' >> "$HTML"
		endif
	    end
	    echo '</form>' >> "$HTML"
	    echo '<a href="'"$cgi"'"><img width="'$width'%" alt="'$id/$image'" src="'"$img"'"></a>' >> "$HTML"
	    echo '<figcaption><i>'"$dir"'</i>  '"$time"'</figcaption>' >> "$HTML" 
	    echo '<form action="'"$act"'" method="get">' >> "$HTML"
	    echo '<input type="hidden" name="db" value="'"$DB"'">' >> "$HTML"
	    echo '<input type="hidden" name="id" value="'"$id"'">' >> "$HTML"
	    echo '<input type="hidden" name="image" value="'"$jpg"'">' >> "$HTML"
	    echo '<input type="hidden" name="old" value="'"$dir"'">' >> "$HTML"
	    echo '<input type="hidden" name="match" value="'"$match"'">' >> "$HTML"
	    echo '<input type="hidden" name="limit" value="'"$limit"'">' >> "$HTML"
	    # current classification
	    echo '<input type="text" size="5" name="add" value="'"$add"'">' >> "$HTML"
	    # echo '<select name="new">' >> "$HTML"
	    # if ($dir != "NO_TAGS") echo '<option value="'"$dir"'"">'"$dir"'</option>' >> "$HTML" # current class (dir) is first option
	    # foreach c ( $allclasses )
		# if ($c != $dir && $c != "NO_TAGS") echo '<option value="'"$c"'"">'"$c"'</option>' >> "$HTML" # don't include current class or NO_TAGS
	    # end
	    # echo '</select>' >> "$HTML"
	    echo '<input style="background-color:#6699ff" type="submit" value="CREATE">' >> "$HTML"
	    echo '</form>' >> "$HTML"
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

output:

#
# prepare for output
#
echo "Content-Type: text/html; charset=utf-8"
echo "Cache-Control: no-cache"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo ""
cat "$HTML"

done:

rm -f "$HTML"
echo `date` "$0 $$ -- FINISH ($QUERY_STRING)" >>! $TMP/LOG
