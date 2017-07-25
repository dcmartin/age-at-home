#!/bin/csh -fb
setenv APP "aah"
setenv API "classify"
setenv LAN "192.168.1"
setenv WWW "$LAN".32
setenv DIGITS "$LAN".30
setenv WAN "www.dcmartin.com"
setenv TMP "/var/lib/age-at-home"

setenv DEBUG true

# don't update file information more than once per (in seconds)
set TTL = 1800
set SECONDS = `date "+%s"`
set DATE = `/bin/echo $SECONDS \/ $TTL \* $TTL | bc`

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
    set db = `/bin/echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
    set class = `/bin/echo "$QUERY_STRING" | sed 's/.*class=\([^&]*\).*/\1/'`
    if ($class == "$QUERY_STRING") unset class
    set match = `/bin/echo "$QUERY_STRING" | sed 's/.*match=\([^&]*\).*/\1/'`
    if ($match == "$QUERY_STRING") unset match
    set limit = `/bin/echo "$QUERY_STRING" | sed 's/.*limit=\([^&]*\).*/\1/'`
    if ($limit == "$QUERY_STRING") unset limit
    set assign = `/bin/echo "$QUERY_STRING" | sed 's/.*assign=\([^&]*\).*/\1/'`
    if ($assign == "$QUERY_STRING") unset assign
    set add = `/bin/echo "$QUERY_STRING" | sed 's/.*add=\([^&]*\).*/\1/'`
    if ($add == "$QUERY_STRING") set add = ""
    set slave = `/bin/echo "$QUERY_STRING" | sed 's/.*slave=\([^&]*\).*/\1/'`
    if ($slave == "$QUERY_STRING") unset slave
else
    /bin/echo "SET QUERY_STRING"
    exit
endif

#
# defaults (rough-fog; all; <this-month>*)
#
if ($?db == 0) set db = rough-fog
if ($?class == 0) set class = all
if ($?match == 0) set match = `date '+%Y%m'`
if ($?limit == 0) set limit = $IMAGE_LIMIT

# standardize QUERY_STRING 
setenv QUERY_STRING "db=$db&class=$class&match=$match&limit=$limit"

# annouce START
/bin/echo `date` "$0 $$ -- START ($QUERY_STRING)" >>&! $TMP/LOG

#
# get read-only access to cloudant
#
if (-e ~$USER/.cloudant_url) then
    set cc = ( `cat ~$USER/.cloudant_url` )
    if ($#cc > 0) set CU = $cc[1]
endif
if ($?CU == 0) then
    /bin/echo `date` "$0 $$ -- no Cloudant URL" >>&! $TMP/LOG
    goto done
endif

set date = "DATE"
set seqid = "SEQID"

# get all LABEL classes for this device
set url = "http://$WAN/CGI/aah-labels.cgi?db=$db" 
set out = "$TMP/$APP-$API-labels-$db.$$.json"
if ($?DEBUG) /bin/echo `date` "$0 $$ -- CALL $url" >>&! $TMP/LOG
/usr/bin/curl -m 2 -s -q -f -L "$url" -o "$out"
if ($status == 22 || $status == 28 || ! -s "$out") then
  if ($?DEBUG) /bin/echo `date` "$0 $$ -- FAIL ($url)" >>&! $TMP/LOG
  set label_classes = ( )
else
  if ($?DEBUG) /bin/echo `date` "$0 $$ -- GOT $out" >>&! $TMP/LOG
  set label_classes = ( `/usr/local/bin/jq -r '.classes|sort_by(.name)[].name' "$out"` )
  set label_date = ( `/usr/local/bin/jq -r '.date' "$out"` )
endif
rm -f "$out"

# choices by end-user on which images to curate
set image_classes = ( "recent" "confusing" "unknown" $label_classes )

set MIXPANELJS = "http://$WAN/CGI/script/mixpanel-aah.js"

set HTML = "$TMP/$APP-$API.$$.html"

# header
/bin/echo "<HTML><HEAD><TITLE>$APP-$API" >! "$HTML"
/bin/echo '{ "device":"'$db'","class":"'$class'","match":"'$match'","limit":"'$limit'" }' >> "$HTML"
/bin/echo "</TITLE></HEAD>" >> "$HTML"
/bin/echo '<script type="text/javascript" src="'$MIXPANELJS'"></script><script>mixpanel.track('"'"$APP-$API"');</script>" >> "$HTML"
/bin/echo '<BODY>' >> "$HTML"

if ($?slave == 0) /bin/echo '<p>'"$db"' : match date by <i>regexp</i>; slide image count (max = '$IMAGE_LIMIT'); select all or <i>class</i>; then press <b>CHANGE</b>' >> "$HTML"

/bin/echo '<form action="http://'"$WWW/CGI/$APP-$API"'.cgi">' >> "$HTML"
/bin/echo '<input type="hidden" name="db" value="'"$db"'">' >> "$HTML"
/bin/echo '<input type="text" name="match" value="'"$match"'">' >> "$HTML"
if ($?slave) /bin/echo '<input type="hidden" name="slave" value="true">' >> "$HTML"
/bin/echo '<input type="range" name="limit" value="'"$limit"'" max="'$IMAGE_LIMIT'" min="1">' >> "$HTML"
/bin/echo '<select name="class">' >> "$HTML"
/bin/echo '<option value="'"$class"'">'"$class"'</option>' >> "$HTML" # current class (dir) is first option
if ($class != "all") /bin/echo '<option value="all">all</option>' >> "$HTML" # all classes is second option
foreach c ( $image_classes )
    if ($c != $class) /bin/echo '<option value="'"$c"'">'"$c"'</option>' >> "$HTML" # don't include current class
end
/bin/echo '</select>' >> "$HTML"
/bin/echo '<input type="submit" style="background-color:#ff9933" value="CHANGE"></form>' >> "$HTML"

# find in one or all directories
if ($class == "all") then
    set CDIR = "$TMP/$db"
else
    set CDIR = "$TMP/$db/$class"
endif

# get location
set location = ( `/usr/bin/curl -s -q "http://$WWW/CGI/aah-devices.cgi?db=$db" | /usr/local/bin/jq -r '.location'` )

#
# get images
#
if (-d "$CDIR") then
  set IMAGES = "/tmp/$0:t.$$-images.csv"
  set url = "$WWW/CGI/aah-images.cgi?db=$db&limit=$limit"
  /usr/bin/curl -s -q -f -L "$url" \
	| /usr/local/bin/jq -r '.ids[]?' \
	| /usr/bin/xargs -I % /usr/bin/curl -s -q -f -L "$WWW/CGI/aah-updates.cgi?db=$db&id=%" \
	| /usr/local/bin/jq -j '.class,"/",.id,".jpg\n"' \
	| /usr/bin/sed "s/ /_/g" >! "$IMAGES.$$"
  if (-s "$IMAGES.$$") then
    foreach i ( `/bin/cat "$IMAGES.$$"` )
      if (-s "$TMP/$db/$i") then
	echo "$i" >>! "$IMAGES"
      else if (-l "$TMP/$db/$i") then
        if ($?DEBUG) /bin/echo `date` "$0 $$ -- $TMP/$db/$i linked" >>&! $TMP/LOG
      else
        if ($?DEBUG) /bin/echo `date` "$0 $$ -- $TMP/$db/$i missing" >>&! $TMP/LOG
      endif
    end 
  endif
  rm -f "$IMAGES.$$"
else
  if ($?DEBUG) /bin/echo `date` "$0 $$ -- no $CDIR exists" >>&! $TMP/LOG
  goto done
endif

if (! -s "$IMAGES") then
  goto done
endif

# check if we moved an image (assignment to new class via aah-label.cgi)
if ($?assign) then
  if ($?DEBUG) /bin/echo `date` "$0 $$ -- removing $assign from cache" >>&! $TMP/LOG
  egrep -v "$assign" "$IMAGES" >! "$IMAGES.$$"
  mv -f "$IMAGES.$$" "$IMAGES"
endif

# find all matching images
if ($?match) then
  egrep "$match" "$IMAGES" >! "$IMAGES.$$"
  rm -f "$IMAGES"
  set IMAGES = "$IMAGES.$$"
endif

# count images
set nimage = `wc -l "$IMAGES" | awk '{ print $1 }'`

@ ncolumns = 4
if ($nimage < $ncolumns) @ ncolumns = $nimage
@ width = 100

# action to label image
set act = "http://$WWW/CGI/$APP-label.cgi"
# do magic
/bin/echo "<script> function hover(e,i) { e.setAttribute('src', i); } function unhover(e) { e.setAttribute('src', i); }</script>" >> "$HTML"
# start table
/bin/echo '<table border="1"><tr>' >> "$HTML"

#
# ITERATE OVER IMAGES (based on limit count)
#
@ k = 0
foreach image ( `head -"$limit" "$IMAGES"` )
  # test if done
  if ($k >= $limit) break

  if ($?DEBUG) /bin/echo `date` "$0 $$ -- PROCESSING IMAGE ($k/$limit) ($image)" >>&! $TMP/LOG

  # setup 
  set jpg = $image:t
  set jpm = `/bin/echo "$jpg:r" | sed "s/\(.*\)-.*-.*/\1/"` # get the image date for matching
  set time = `/bin/echo $jpg | sed "s/\(....\)\(..\)\(..\)\(..\)\(..\).*-.*/\1\/\2\/\3 \4:\5/"` # breakdown image identifier into time components for image label

  # special case for "all"
  if ($class == "all") then
    set dir = $image:h # class of image is encoded as head of path
    set dir = $dir:t # and tail, e.g. <path>/<class>/<jpeg>
    set txt = "$dir"
  else
    set dir = $class
    set txt = "$class"
  endif

  # how to access the image (and sample)
  set img = "http://$WWW/CGI/$APP-images.cgi?db=$db&id=$image:r&ext=full"
  set jpeg = "http://$WWW/CGI/$APP-images.cgi?db=$db&id=$image:r&ext=crop"

  # note change in limit to one (1) as we are inspecting single image (see width specification below)
  if ($?slave) then
    set cgi = "http://$WWW/CGI/$APP-$API.cgi?db=$db&class=$class&match=$jpm&limit=1&slave=true"
  else
    set cgi = "http://$WWW/CGI/$APP-$API.cgi?db=$db&class=$class&match=$jpm&limit=1"
  endif

  # start a new row every $ncolumns
  if ($k % $ncolumns == 0) /bin/echo '</tr><tr>' >> "$HTML"

  # build the figure entry in the table
  /bin/echo '<td><figure>' >> "$HTML"
  /bin/echo '<table><tr><td>' >> "$HTML"
  # FORM 1
  /bin/echo '<form action="'"$act"'" method="get">' >> "$HTML"
  /bin/echo '<input type="hidden" name="db" value="'"$db"'">' >> "$HTML"
  /bin/echo '<input type="hidden" name="class" value="'"$class"'">' >> "$HTML"
  /bin/echo '<input type="hidden" name="image" value="'"$jpg"'">' >> "$HTML"
  /bin/echo '<input type="hidden" name="old" value="'"$dir"'">' >> "$HTML"
  /bin/echo '<input type="hidden" name="match" value="'"$match"'">' >> "$HTML"
  /bin/echo '<input type="hidden" name="limit" value="'"$limit"'">' >> "$HTML"
  if ($?slave) /bin/echo '<input type="hidden" name="slave" value="true">' >> "$HTML"
  /bin/echo '<button style="background-color:#999999" type="submit" name="skip" value="'"$jpg"'">SKIP</button>' >> "$HTML"
  /bin/echo '</form>' >> "$HTML"
  /bin/echo '</td><td>' >> "$HTML"
  # FORM 2
  /bin/echo '<form action="'"$act"'" method="get">' >> "$HTML"
  /bin/echo '<input type="hidden" name="db" value="'"$db"'">' >> "$HTML"
  /bin/echo '<input type="hidden" name="class" value="'"$class"'">' >> "$HTML"
  /bin/echo '<input type="hidden" name="image" value="'"$jpg"'">' >> "$HTML"
  /bin/echo '<input type="hidden" name="old" value="'"$dir"'">' >> "$HTML"
  /bin/echo '<input type="hidden" name="match" value="'"$match"'">' >> "$HTML"
  /bin/echo '<input type="hidden" name="limit" value="'"$limit"'">' >> "$HTML"
  if ($?slave) /bin/echo '<input type="hidden" name="slave" value="true">' >> "$HTML"
  /bin/echo '<select name="new" onchange="this.form.submit()">' >> "$HTML"
  /bin/echo '<option selected value="'"$dir"'">'"$dir"'</option>' >> "$HTML"
  /bin/echo '<option value="'"$location"'">'"$location"'</option>' >> "$HTML"
  if ($?label_classes) then
    foreach i ( $label_classes )
      set j = "$i:t"
      if (($j != $dir) && ($j != $location)) /bin/echo '<option value="'"$i"'">'"$i"'</option>' >> "$HTML"
    end
  endif
  /bin/echo '</select>' >> "$HTML"
  /bin/echo '</form>' >> "$HTML"

  # NEW COLUMN
  /bin/echo '</td><td>' >> "$HTML"
  # FORM 3
  /bin/echo '<form action="'"$act"'" method="get">' >> "$HTML"
  /bin/echo '<input type="hidden" name="db" value="'"$db"'">' >> "$HTML"
  /bin/echo '<input type="hidden" name="class" value="'"$class"'">' >> "$HTML"
  /bin/echo '<input type="hidden" name="image" value="'"$jpg"'">' >> "$HTML"
  /bin/echo '<input type="hidden" name="old" value="'"$dir"'">' >> "$HTML"
  /bin/echo '<input type="hidden" name="match" value="'"$match"'">' >> "$HTML"
  /bin/echo '<input type="hidden" name="limit" value="'"$limit"'">' >> "$HTML"
  if ($?slave) /bin/echo '<input type="hidden" name="slave" value="true">' >> "$HTML"
  /bin/echo '<input type="hidden" name="new" value="'"$dir"'">' >> "$HTML"
  /bin/echo '<input type="text" size="5" name="add" value="'"$add"'">' >> "$HTML"
  /bin/echo '<input type="submit" style="background-color:#ff9933" value="OK">' >> "$HTML"
  /bin/echo '</form>' >> "$HTML"

  /bin/echo '</td>' >> "$HTML"
  /bin/echo '</tr>' >> "$HTML"
  /bin/echo '</table>' >> "$HTML"

  # this conditional is based on inspection in single image mode
  if ($limit > 1) then
    /bin/echo '<a href="'"$cgi"'"><img width="'$MODEL_IMAGE_WIDTH'" height="'$MODEL_IMAGE_HEIGHT'" alt="'"$image:t:r"'" src="'"$img"'" onmouseover="this.src='"'""$jpeg""'"'" onmouseout="this.src='"'""$img""'"'"></a>' >> "$HTML"
  else
    /bin/echo '<a href="'"$cgi"'"><img width="'$CAMERA_IMAGE_WIDTH'" height="'$CAMERA_IMAGE_HEIGHT'" alt="'"$image:t:r"'" src="'"$img"'" onmouseover="this.src='"'""$jpeg""'"'" onmouseout="this.src='"'""$img""'"'"></a>' >> "$HTML"
  endif
  /bin/echo '<figcaption style="font-size:50%;">'"$time"'</figcaption>' >> "$HTML" 
  /bin/echo '</figure>' >> "$HTML"
  /bin/echo '</td>' >> "$HTML"

  # jump over single image stuff
  if ($limit > 1) goto bottom

  #
  # ENTIRE SECTION IS FOR SINGLE IMAGE DETAIL
  #
  set record = ( `/usr/bin/curl -s -q -L "$CU/$db/$jpg:r" | /usr/local/bin/jq -r '.'` )
  set crop = `/bin/echo "$record" | /usr/local/bin/jq -r '.imagebox'`
  set scores = ( `/bin/echo "$record" | /usr/local/bin/jq -r '.visual.scores|sort_by(.score)'` )
  set top1 = ( `/bin/echo "$record" | /usr/local/bin/jq -r '.visual.scores|sort_by(.score)[-1]'` )

  # # get the scores
  /bin/echo "$scores" | /usr/local/bin/jq -c '.[]' >! /tmp/$0:t.$$
  # count them
  set nscore = ( `cat /tmp/$0:t.$$ | /usr/bin/wc -l` )
  if ($nscore == 0) goto bottom
  #
  # report on scores
  #
  /bin/echo '<td><table style="font-size:75%;"><tr><th>CLASS</th><th>SCORE</th><th>MODEL</th></tr>' >> "$HTML"
  @ z = 0
  while ($z < $nscore)
    /bin/echo '<tr>' >> "$HTML"
    @ y = $nscore - $z
    set class_id = `cat /tmp/$0:t.$$ | /usr/bin/head -$y | /usr/bin/tail -1 | /usr/local/bin/jq -r '.classifier_id'`
    set name = `cat /tmp/$0:t.$$ | /usr/bin/head -$y | /usr/bin/tail -1 | /usr/local/bin/jq -r '.name'`
    set score = `cat /tmp/$0:t.$$ | /usr/bin/head -$y | /usr/bin/tail -1 | /usr/local/bin/jq -r '.score'`
    # if a model was specified (name)
    if ($?name) then
      if ($?DEBUG) /bin/echo `date` "$0 $$ -- CHECKING MODEL $name" >>&! $TMP/LOG

      # find out type
      unset type
      # test if model name matches DIGITS convention of date
      set tf = ( `/bin/echo "$name" | sed 's/[0-9]*-[0-9]*-.*/DIGITS/'` )
      if ("$tf" == "DIGITS") then
        set type = "DIGITS"
      else 
	# Watson VR removes hyphens from db name (rough-fog becomes roughfog) 
	set device = ( `/bin/echo "$db" | sed "s/-//g"` )
	set tf = ( `/bin/echo "$name" | sed 's/'"$device"'_.*/CUSTOM/'` )
	if ("$tf" == "CUSTOM") set type = "CUSTOM"
      endif
      # default type if not DIGITS and not CUSTOM
      if ($?type == 0) set type = "default"
      switch ($type)
	case "CUSTOM":
	      /bin/echo '<td>' >> "$HTML"
	      /bin/echo '<a target="'"$name"-"$class_id"'" href="http://www.dcmartin.com/CGI/aah-index.cgi?db='"$db"'&class='"$class_id"'&display=icon">'"$class_id"'</a>' >> "$HTML"
	      /bin/echo '</td><td>'"$score"'</td><td>' >> "$HTML"
	      # http://www.dcmartin.com/AAH/cfmatrix.html?model=roughfog_292216250
	      /bin/echo '<a target="cfmatrix" href="http://age-at-home.mybluemix.net/cfmatrix.html?model='"$name"'">'"$name"'</a>' >> "$HTML"
	      /bin/echo '</td>' >> "$HTML"
	      breaksw
	case "DIGITS":
	      set ds_id = ( `curl -s -q "http://age-at-home.dcmartin.com:5001/models/$name.json" | /usr/local/bin/jq -r '.dataset_id'` )
	      /bin/echo '<td>' >> "$HTML"
	      if ($#ds_id) then
		/bin/echo -n '<a target="'"$name"-"$class_id"'" href="' >> "$HTML"
		/bin/echo -n 'http://age-at-home.dcmartin.com:5001/datasets/'"$ds_id" >> "$HTML"
		/bin/echo '">'"$class_id"'</a>' >> "$HTML"
	      else
		/bin/echo "$class_id" >> "$HTML"
	      endif
	      /bin/echo '</td><td>'"$score"'</td><td>' >> "$HTML"
	      # http://192.168.1.30:5001/models/20170506-235510-f689
	      /bin/echo '<a target="digits" href="http://age-at-home.dcmartin.com:5001/models/'"$name"'">'"$name"'</a>' >> "$HTML"
	      /bin/echo '</td>' >> "$HTML"
	      breaksw
	default:
	      /bin/echo '<td>'"$class_id"'</td><td>'"$score"'</td><td>'"$name"'</td>' >> "$HTML"
	      breaksw
      endsw
      # end row
      /bin/echo '</tr>' >> "$HTML"
      @ z++
  end # while ($z < $nscore)
  # cleanup
  /bin/echo '</table>' >> "$HTML"
  /bin/echo '</td>' >> "$HTML"
bottom:
  rm -f /tmp/$0:t.$$
  # increment to next image
  @ k++
end # foreach 

# end row & table
/bin/echo "</tr></table>" >> "$HTML"

/bin/echo '</BODY>' >> "$HTML"
/bin/echo '</HTML>' >> "$HTML"

output:

#
# prepare for output
#

if (-s "$HTML") then
  /bin/echo "Content-Type: text/html; charset=utf-8"
  /bin/echo "Cache-Control: no-cache"
  @ age = $SECONDS - $DATE
  @ refresh = $TTL - $age
  /bin/echo "Age: $age"
  /bin/echo "Refresh: $refresh"
  /bin/echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
  /bin/echo ""
  cat "$HTML"
else
  /bin/echo "Content-Type: text/html; charset=utf-8"
  /bin/echo "Cache-Control: no-cache"
  /bin/echo ""
  /bin/echo "<HTML><HEAD><TITLE>$APP-$API"
  /bin/echo '{ "device":"'$db'","class":"'$class'","match":"'$match'","limit":"'$limit'" }'
  /bin/echo "</TITLE></HEAD>"
  /bin/echo '<script type="text/javascript" src="'$MIXPANELJS'"></script><script>mixpanel.track('"'"$APP-$API"');</script>"
  /bin/echo '<BODY>'
  /bin/echo '<P><A HREF="HTTP://'"$WWW/CGI/$APP-$API.cgi?$QUERY_STRING"'">RETRY '"$QUERY_STRING"'</A></P>'
  /bin/echo '</BODY>'
  /bin/echo '</HTML>'
endif

done:

if ($?HTML) then
  rm -f "$HTML"
endif
if ($?REVIEW) then
 rm -f "$REVIEW"
endif
if ($?IMAGES) then
  rm -f "$IMAGES" "$IMAGES".$$
endif

/bin/echo `date` "$0 $$ -- FINISH ($QUERY_STRING)" >>&! $TMP/LOG

