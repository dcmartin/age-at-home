#!/bin/csh -fb
setenv APP "aah"
setenv API "classify"
setenv LAN "192.168.1"
setenv WWW "$LAN".32
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

setenv DEBUG true

# don't update file information more than once per (in seconds)
set TTL = 1800
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

# default image limit
if ($?IMAGE_LIMIT == 0) setenv IMAGE_LIMIT 8
# default camera specifications
if ($?CAMERA_IMAGE_WIDTH == 0) setenv CAMERA_IMAGE_WIDTH 640
if ($?CAMERA_IMAGE_HEIGHT == 0) setenv CAMERA_IMAGE_HEIGHT 480
# default model specifications
if ($?MODEL_IMAGE_WIDTH == 0) setenv MODEL_IMAGE_WIDTH 224
if ($?MODEL_IMAGE_HEIGHT == 0) setenv MODEL_IMAGE_HEIGHT 224
# default transformation from camera output to model input
if ($?CAMERA_MODEL_TRANSFORM == 0) setenv CAMERA_MODEL_TRANSFORM "CROP"

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
    set slave = `echo "$QUERY_STRING" | sed 's/.*slave=\([^&]*\).*/\1/'`
    if ($slave != "$QUERY_STRING") setenv SLAVE_MODE
else
    echo "SET QUERY_STRING"
    exit
endif

#
# defaults (rough-fog; all; <this-month>*)
#
if ($?DB == 0) set DB = rough-fog
if ($?id == 0) set id = all
if ($?match == 0) set match = `date '+%Y%m'`
if ($?limit == 0) set limit = $IMAGE_LIMIT

# standardize QUERY_STRING 
setenv QUERY_STRING "db=$DB&id=$id&match=$match&limit=$limit"

# annouce START
echo `date` "$0 $$ -- START ($QUERY_STRING)" >>! $TMP/LOG

#
# location
#
set location = `/usr/bin/curl -s -q -L "http://$WWW/CGI/aah-resinDevice.cgi" | /usr/local/bin/jq -r '.|select(.name=="'"$DB"'")|.location'`
if ($?location) then
  if ($#location && $location != "") then
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- found LOCATION ($location)" >>! $TMP/LOG
  endif
else 
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- no LOCATION" >>! $TMP/LOG
  set location = "NEGATIVE"
endif

# get review state
set REVIEW = "$TMP/$APP-$API-review-$DB.$DATE.json"
if (! -s "$REVIEW") then
    set old = ( `echo "$REVIEW:r:r".*` )
    if ($?old) then
      rm -f $old
    endif
    set url = "http://$WWW/CGI/aah-review.cgi?db=$DB" 
    if ($?DEBUG) echo `date` "$0 $$ -- CALL aah-review for $DB" >>! $TMP/LOG
    curl -s -q -f -L \
	"$url" \
	-o "$REVIEW.$$"
    if ($status == 22 || ! -s "$REVIEW.$$") then
      if ($?DEBUG) echo `date` "$0 $$ -- FAIL aah-review for $DB" >>! $TMP/LOG
      rm -f "$REVIEW.$$"
    else
      mv -f "$REVIEW.$$" "$REVIEW"
    if ($?DEBUG) echo `date` "$0 $$ -- SUCCESS aah-review for $DB" >>! $TMP/LOG
    endif
endif

# check for cache
if (-s "$REVIEW") then
    # get date and seqid of results
    set date = `/usr/local/bin/jq -c '.date' "$REVIEW" | sed 's/"//g'`
    set seqid = `/usr/local/bin/jq -c '.seqid' "$REVIEW" | sed 's/"//g'`
    if ($?DEBUG) echo `date` "$0 $$ -- $date $seqid" >>! $TMP/LOG
else
    if ($?DEBUG) echo `date` "$0 $$ -- NO $REVIEW" >>! $TMP/LOG
    goto done
endif

#
# should cache classes and test by modification time of directory
#
set CLASSES = "$TMP/$APP-$API-classes-$DB.json"
# ensure  directory for labeled images
set dir = "$TMP/label/$DB" 
if (! -d "$dir") then
  if ($?DEBUG) echo `date` "$0 $$ -- create directory ($dir)" >>! $TMP/LOG
  mkdir -p "$dir"
  set allclasses = ()
else if ((-M "$dir") > (-M "$CLASSES")) then
  if ($?DEBUG) echo `date` "$0 $$ -- updating $CLASSES" >>! $TMP/LOG
  # get all classes in order of prevalence (small to large) from initial classification
  set allclasses = ( `echo "$TMP/$DB/"*` )
  @ i = 1
  while ($i <= $#allclasses)
    set allclasses[$i] = "$allclasses[$i]:t"
    echo -n "$allclasses[$i] " >>! "$CLASSES"
    @ i++
  end
  echo "" >>! "$CLASSES"
else
  set allclasses = ( `cat "$CLASSES"` )
endif

set MIXPANELJS = "http://$WWW/CGI/script/mixpanel-aah.js"

set HTML = "$TMP/$APP-$API.$$.html"

# header
echo "<HTML><HEAD><TITLE>$APP-$API" >> "$HTML"
echo '{ "device":"'$DB'","id":"'$id'","match":"'$match'","limit":"'$limit'" }' >> "$HTML"
echo "</TITLE></HEAD>" >> "$HTML"
echo '<script type="text/javascript" src="'$MIXPANELJS'"></script><script>mixpanel.track('"'"$APP-$API"');</script>" >> "$HTML"
echo '<BODY>' >> "$HTML"

if ($?DEBUG) then
  echo -n '<p style="font-size:50%;">' >> "$HTML"
  if ($?date) then
    echo -n 'Last updated: <i>' `date -r $date` >> "$HTML"
  else
    echo -n 'Cache stored: <i>' `date -r $REVIEW:r:e` >> "$HTML"
  endif
  echo "</i>($?seqid)</p>" >> "$HTML"
endif

if ($?SLAVE_MODE == 0) then
  echo '<p>'"$DB"' : match date by <i>regexp</i>; slide image count (max = '$IMAGE_LIMIT'); select all or <i>class</i>; then press <b>CHANGE</b>' >> "$HTML"
else
  if ($?DEBUG) echo `date` "$0 $$ -- SLAVE_MODE" >>! $TMP/LOG
endif

echo '<form action="http://'"$WWW/CGI/$APP-$API"'.cgi">' >> "$HTML"
echo '<input type="hidden" name="db" value="'"$DB"'">' >> "$HTML"
echo '<input type="text" name="match" value="'"$match"'">' >> "$HTML"
echo '<input type="range" name="limit" value="'"$limit"'" max="'$IMAGE_LIMIT'" min="1">' >> "$HTML"
echo '<select name="id">' >> "$HTML"
echo '<option value="'"$id"'">'"$id"'</option>' >> "$HTML" # current class (dir) is first option
if ($id != "all") echo '<option value="all">all</option>' >> "$HTML" # all classes is second option
foreach c ( $allclasses )
    if ($c != $id) echo '<option value="'"$c"'">'"$c"'</option>' >> "$HTML" # don't include current class
end
echo '</select>' >> "$HTML"
echo '<input type="submit" style="background-color:#ff9933" value="CHANGE"></form>' >> "$HTML"

# find in one or all directories
if ($id == all) then
    set CDIR = "$TMP/$DB"
else
    set CDIR = "$TMP/$DB/$id"
endif

if (-d "$CDIR") then
    set IMAGES = "$TMP/$APP-$API-db=$DB&id=$id&match=$match.$DATE.txt"
    if (-s "$IMAGES") then
	if ($?DEBUG) echo `date` "$0 $$ -- using cached $IMAGES" >>! $TMP/LOG
	if ($?assign) then
	    if ($?DEBUG) echo `date` "$0 $$ -- removing $assign from cache" >>! $TMP/LOG
	    cat "$IMAGES" | egrep -v "$assign" >! "$IMAGES.$$"
	    mv -f "$IMAGES.$$" "$IMAGES"
	endif
    else
	if ($?DEBUG) echo `date` "$0 $$ -- creating cache $IMAGES" >>! $TMP/LOG
	set old = ( `echo "$IMAGES:r:r".*.txt` ) 
	if ($#old >= 1) then
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

    # do magic
    echo "<script> function hover(e,i) { e.setAttribute('src', i); } function unhover(e) { e.setAttribute('src', i); }</script>" >> "$HTML"

    # start table
    echo '<table border="1"><tr>' >> "$HTML"

    set label_dirs = ( `echo $TMP/label/$DB/*` )

    @ k = 0
    foreach image ( `head -"$limit" "$IMAGES"` )
	if ($k < $limit) then
	    if ($?DEBUG) echo `date` "$0 $$ -- file ($image)" >>! $TMP/LOG

	    set jpg = $image:t
	    if ($id == all) then
		set dir = $image:h # class of image is encoded as head of path
		set dir = $dir:t # and tail, e.g. <path>/<class>/<jpeg>
		set txt = "$dir"
	    else
		set dir = $id
		set txt = "$id"
	    endif

	    set img = "http://$WWW/$APP/$DB/$dir/$jpg"
	    set jpeg = "$img:r.jpeg"
	    set jpm = `echo "$jpg:r" | sed "s/\(.*\)-.*-.*/\1/"`
	    # note change in limit to one (1) as we are inspecting single image (see width specification below)
	    set cgi = "http://$WWW/CGI/$APP-$API.cgi?db=$DB&id=$id&match=$jpm&limit=1"
	    set time = `echo $jpg | sed "s/\(....\)\(..\)\(..\)\(..\)\(..\).*-.*/\1\/\2\/\3 \4:\5/"`

	    if ($k % $ncolumns == 0) echo '</tr><tr>' >> "$HTML"

	    echo '<td><figure>' >> "$HTML"

	    echo '<table><tr><td>' >> "$HTML"

	    echo '<form action="'"$act"'" method="get">' >> "$HTML"
	      echo '<input type="hidden" name="db" value="'"$DB"'">' >> "$HTML"
	      echo '<input type="hidden" name="id" value="'"$id"'">' >> "$HTML"
	      echo '<input type="hidden" name="image" value="'"$jpg"'">' >> "$HTML"
	      echo '<input type="hidden" name="old" value="'"$dir"'">' >> "$HTML"
	      echo '<input type="hidden" name="match" value="'"$match"'">' >> "$HTML"
	      echo '<input type="hidden" name="limit" value="'"$limit"'">' >> "$HTML"
	      echo '<button style="background-color:#999999" type="submit" name="skip" value="'"$jpg"'">SKIP</button>' >> "$HTML"
	    echo '</form>' >> "$HTML"

	    echo '</td><td>' >> "$HTML"

	    echo '<form action="'"$act"'" method="get">' >> "$HTML"
	      echo '<input type="hidden" name="db" value="'"$DB"'">' >> "$HTML"
	      echo '<input type="hidden" name="id" value="'"$id"'">' >> "$HTML"
	      echo '<input type="hidden" name="image" value="'"$jpg"'">' >> "$HTML"
	      echo '<input type="hidden" name="old" value="'"$dir"'">' >> "$HTML"
	      echo '<input type="hidden" name="match" value="'"$match"'">' >> "$HTML"
	      echo '<input type="hidden" name="limit" value="'"$limit"'">' >> "$HTML"
	      echo '<select name="new" onchange="this.form.submit()">' >> "$HTML"
	      echo '<option selected value="'"$dir"'">'"$dir"'</option>' >> "$HTML"
	      echo '<option value="'"$location"'">'"$location"'</option>' >> "$HTML"
	      if ($#label_dirs) then
		foreach i ( $label_dirs )
		  set j = "$i:t"
		  if (($j != $dir) && ($j != $location)) echo '<option value="'"$j"'">'"$j"'</option>' >> "$HTML"
		end
	      endif
	      echo '</select>' >> "$HTML"
	    echo '</form>' >> "$HTML"

	    echo '</td><td>' >> "$HTML"
	    echo '<form action="'"$act"'" method="get">' >> "$HTML"
	    echo '<input type="hidden" name="db" value="'"$DB"'">' >> "$HTML"
	    echo '<input type="hidden" name="id" value="'"$id"'">' >> "$HTML"
	    echo '<input type="hidden" name="image" value="'"$jpg"'">' >> "$HTML"
	    echo '<input type="hidden" name="old" value="'"$dir"'">' >> "$HTML"
	    echo '<input type="hidden" name="match" value="'"$match"'">' >> "$HTML"
	    echo '<input type="hidden" name="limit" value="'"$limit"'">' >> "$HTML"
	    echo '<input type="hidden" name="new" value="'"$dir"'">' >> "$HTML"
	    echo '<input type="text" size="5" name="add" value="'"$add"'">' >> "$HTML"
	    echo '<input type="submit" style="background-color:#ff9933" value="OK">' >> "$HTML"
	    echo '</form>' >> "$HTML"

	    echo '</td>' >> "$HTML"
	    echo '</tr>' >> "$HTML"
	    echo '</table>' >> "$HTML"

	    # this conditional is based on inspection in single image mode
	    if ($limit > 1) then
	      echo '<a href="'"$cgi"'"><img width="'$MODEL_IMAGE_WIDTH'" height="'$MODEL_IMAGE_HEIGHT'" alt="'"$image:t:r"'" src="'"$img"'" onmouseover="this.src='"'""$jpeg""'"'" onmouseout="this.src='"'""$img""'"'"></a>' >> "$HTML"
	    else
	      echo '<a href="'"$cgi"'"><img width="'$CAMERA_IMAGE_WIDTH'" height="'$CAMERA_IMAGE_HEIGHT'" alt="'"$image:t:r"'" src="'"$img"'" onmouseover="this.src='"'""$jpeg""'"'" onmouseout="this.src='"'""$img""'"'"></a>' >> "$HTML"
	    endif
	    echo '<figcaption style="font-size:50%;">'"$time"'</figcaption>' >> "$HTML" 
	    echo '</figure>' >> "$HTML"
	    echo '</td>' >> "$HTML"
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
@ age = $SECONDS - $DATE
@ refresh = $TTL - $age
echo "Age: $age"
echo "Refresh: $refresh"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo ""
cat "$HTML"

done:

if ($?HTML) then
  rm -f "$HTML"
endif

echo `date` "$0 $$ -- FINISH ($QUERY_STRING)" >>! $TMP/LOG
