#!/bin/tcsh -b
setenv APP "aah"
setenv API "classify"

setenv DEBUG true
setenv VERBOSE true

# environment
if ($?LAN == 0) setenv LAN "192.168.1"
if ($?DIGITS == 0) setenv DIGITS "$LAN".30
if ($?TMP == 0) setenv TMP "/tmp"
if ($?AAHDIR == 0) setenv AAHDIR "/var/lib/age-at-home"
if ($?CREDENTIALS == 0) setenv CREDENTIALS /usr/local/etc
if ($?LOGTO == 0) setenv LOGTO $TMP/$APP.log

###
### dateutils REQUIRED
###

if ( -e /usr/bin/dateutils.dconv ) then
   set dateconv = /usr/bin/dateutils.dconv
else if ( -e /usr/local/bin/dateconv ) then
   set dateconv = /usr/local/bin/dateconv
else
  echo "No date converter; install dateutils" >& /dev/stderr
  exit 1
endif

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
    set db = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
    set class = `echo "$QUERY_STRING" | sed 's/.*class=\([^&]*\).*/\1/'`
    if ($class == "$QUERY_STRING") unset class
    set match = `echo "$QUERY_STRING" | sed 's/.*match=\([^&]*\).*/\1/'`
    if ($match == "$QUERY_STRING") unset match
    set limit = `echo "$QUERY_STRING" | sed 's/.*limit=\([^&]*\).*/\1/'`
    if ($limit == "$QUERY_STRING") unset limit
    set assign = `echo "$QUERY_STRING" | sed 's/.*assign=\([^&]*\).*/\1/'`
    if ($assign == "$QUERY_STRING") unset assign
    set add = `echo "$QUERY_STRING" | sed 's/.*add=\([^&]*\).*/\1/'`
    if ($add == "$QUERY_STRING") set add = ""
    set slave = `echo "$QUERY_STRING" | sed 's/.*slave=\([^&]*\).*/\1/'`
    if ($slave == "$QUERY_STRING") unset slave
else
    echo "SET QUERY_STRING"
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
echo `date` "$0 $$ -- START ($QUERY_STRING)" >>&! $LOGTO

##
## ACCESS CLOUDANT
##
if ($?CLOUDANT_URL) then
  set CU = $CLOUDANT_URL
else if (-s $CREDENTIALS/.cloudant_url) then
  set cc = ( `cat $CREDENTIALS/.cloudant_url` )
  if ($#cc > 0) set CU = $cc[1]
  if ($#cc > 1) set CN = $cc[2]
  if ($#cc > 2) set CP = $cc[3]
  if ($?CP && $?CN && $?CU) then
    set CU = 'https://'"$CN"':'"$CP"'@'"$CU"
  else if ($?CU) then
    set CU = "https://$CU"
  endif
else
  echo `date` "$0:t $$ -- FAILURE: no Cloudant credentials" >>&! $LOGTO
  goto done
endif

###
###
###

set date = "DATE"
set seqid = "SEQID"

# get all LABEL classes for this device
set url = "http://$HTTP_HOST/CGI/aah-labels.cgi?db=$db" 
set out = "$TMP/$APP-$API-labels-$db.$$.json"
if ($?DEBUG) echo `date` "$0 $$ -- CALL $url" >>&! $LOGTO
curl -m 2 -s -q -f -L "$url" -o "$out"
if ($status == 22 || $status == 28 || ! -s "$out") then
  if ($?DEBUG) echo `date` "$0 $$ -- FAIL ($url)" >>&! $LOGTO
  set label_classes = ( )
else
  if ($?VERBOSE) echo `date` "$0 $$ -- GOT $out" >>&! $LOGTO
  set label_classes = ( `jq -r '.classes|sort_by(.name)[].name' "$out"` )
  set label_date = ( `jq -r '.date' "$out"` )
endif
rm -f "$out"

# choices by end-user on which images to curate
set image_classes = ( "recent" "confusing" "unknown" $label_classes )

set MIXPANELJS = "http://$HTTP_HOST/script/mixpanel-aah.js"

set HTML = "$TMP/$APP-$API.$$.html"

# header
echo "<HTML><HEAD><TITLE>$APP-$API" >! "$HTML"
echo '{ "device":"'$db'","class":"'$class'","match":"'$match'","limit":"'$limit'" }' >> "$HTML"
echo "</TITLE></HEAD>" >> "$HTML"
echo '<script type="text/javascript" src="'$MIXPANELJS'"></script><script>mixpanel.track('"'"$APP-$API"');</script>" >> "$HTML"
echo '<BODY>' >> "$HTML"

if ($?slave == 0) echo '<p>'"$db"' : match date by <i>regexp</i>; slide image count (max = '$IMAGE_LIMIT'); select all or <i>class</i>; then press <b>CHANGE</b>' >> "$HTML"

echo '<form action="http://'"$HTTP_HOST/CGI/$APP-$API"'.cgi">' >> "$HTML"
echo '<input type="hidden" name="db" value="'"$db"'">' >> "$HTML"
echo '<input type="text" name="match" value="'"$match"'">' >> "$HTML"
if ($?slave) echo '<input type="hidden" name="slave" value="true">' >> "$HTML"
echo '<input type="range" name="limit" value="'"$limit"'" max="'$IMAGE_LIMIT'" min="1">' >> "$HTML"
echo '<select name="class">' >> "$HTML"
echo '<option value="'"$class"'">'"$class"'</option>' >> "$HTML" # current class (dir) is first option
if ($class != "all") echo '<option value="all">all</option>' >> "$HTML" # all classes is second option
foreach c ( $image_classes )
    if ($c != $class) echo '<option value="'"$c"'">'"$c"'</option>' >> "$HTML" # don't include current class
end
echo '</select>' >> "$HTML"
echo '<input type="submit" style="background-color:#ff9933" value="CHANGE"></form>' >> "$HTML"

# get location
set location = ( `curl -s -q "$HTTP_HOST/CGI/aah-devices.cgi?db=$db" | jq -r '.location'` )

# get images
set images = ( `curl -s -q "$HTTP_HOST/CGI/aah-images.cgi?db=$db&limit=$limit" | jq -r '.ids[]?'` )
if ($#images == 0 || $images == "null") then
  if ($?DEBUG) echo "$0:t $$ -- $db -- failed to find images" >>&! $LOGTO
  goto done
else
  if ($?VERBOSE) echo "$0:t $$ -- $db -- found $#images images" >>&! $LOGTO
  set nimage = $#images
endif

@ ncolumns = 4
if ($nimage < $ncolumns) @ ncolumns = $nimage
@ width = 100

# action to label image
set act = "http://$HTTP_HOST/CGI/$APP-label.cgi"
# do magic
echo "<script> function hover(e,i) { e.setAttribute('src', i); } function unhover(e) { e.setAttribute('src', i); }</script>" >> "$HTML"
# start table
echo '<table border="1"><tr>' >> "$HTML"

#
# ITERATE OVER IMAGES (based on limit count)
#
@ k = 0
foreach image ( $images )
  # test if done
  if ($k >= $limit) break

  if ($?DEBUG) echo `date` "$0 $$ -- PROCESSING IMAGE ($k/$limit) ($image)" >>&! $LOGTO

  # get image details
  set imginfo = ( `curl -s -q "$HTTP_HOST/CGI/aah-images.cgi?db=$db&id=$image" | jq '.'` )
  # {
  #   "id": "20170802094803-7134-00",
  #   "path": "<device>/<year>/<month>/<day>",
  #   "date": 1501692483,
  #   "imagebox": "494x160+68+150",
  #   "formats": [ { "ext": "jpg|jpeg", "size": "", "depth"
  # }
  set date = ( `echo "$imginfo" | jq -r '.date'` )
  set jpm = `echo "$image" | sed "s/\(.*\)-.*-.*/\1/"` # get the image date for matching
  set time = `echo "$image" | sed "s/\(....\)\(..\)\(..\)\(..\)\(..\).*-.*/\1\/\2\/\3 \4:\5/"` # breakdown image identifier into time components for image label

  # how to access the image (and sample)
  set img = "http://$HTTP_HOST/CGI/$APP-images.cgi?db=$db&id=$image&ext=full"
  set jpeg = "http://$HTTP_HOST/CGI/$APP-images.cgi?db=$db&id=$image&ext=crop"

  # note change in limit to one (1) as we are inspecting single image (see width specification below)
  if ($?slave) then
    set cgi = "http://$HTTP_HOST/CGI/$APP-$API.cgi?db=$db&class=$class&match=$jpm&limit=1&slave=true"
  else
    set cgi = "http://$HTTP_HOST/CGI/$APP-$API.cgi?db=$db&class=$class&match=$jpm&limit=1"
  endif

  # start a new row every $ncolumns
  if ($k % $ncolumns == 0) echo '</tr><tr>' >> "$HTML"

  # build the figure entry in the table
  echo '<td><figure>' >> "$HTML"
  echo '<table><tr><td>' >> "$HTML"
  # FORM 1
  echo '<form action="'"$act"'" method="get">' >> "$HTML"
  echo '<input type="hidden" name="db" value="'"$db"'">' >> "$HTML"
  echo '<input type="hidden" name="class" value="'"$class"'">' >> "$HTML"
  echo '<input type="hidden" name="image" value="'"$image"'">' >> "$HTML"
  echo '<input type="hidden" name="old" value="'"$dir"'">' >> "$HTML"
  echo '<input type="hidden" name="match" value="'"$match"'">' >> "$HTML"
  echo '<input type="hidden" name="limit" value="'"$limit"'">' >> "$HTML"
  if ($?slave) echo '<input type="hidden" name="slave" value="true">' >> "$HTML"
  echo '<button style="background-color:#999999" type="submit" name="skip" value="'"$image"'">SKIP</button>' >> "$HTML"
  echo '</form>' >> "$HTML"
  echo '</td><td>' >> "$HTML"
  # FORM 2
  echo '<form action="'"$act"'" method="get">' >> "$HTML"
  echo '<input type="hidden" name="db" value="'"$db"'">' >> "$HTML"
  echo '<input type="hidden" name="class" value="'"$class"'">' >> "$HTML"
  echo '<input type="hidden" name="image" value="'"$image"'">' >> "$HTML"
  echo '<input type="hidden" name="old" value="'"$dir"'">' >> "$HTML"
  echo '<input type="hidden" name="match" value="'"$match"'">' >> "$HTML"
  echo '<input type="hidden" name="limit" value="'"$limit"'">' >> "$HTML"
  if ($?slave) echo '<input type="hidden" name="slave" value="true">' >> "$HTML"
  echo '<select name="new" onchange="this.form.submit()">' >> "$HTML"
  echo '<option selected value="'"$dir"'">'"$dir"'</option>' >> "$HTML"
  echo '<option value="'"$location"'">'"$location"'</option>' >> "$HTML"
  if ($?label_classes) then
    foreach i ( $label_classes )
      set j = "$i:t"
      if (($j != $dir) && ($j != $location)) echo '<option value="'"$i"'">'"$i"'</option>' >> "$HTML"
    end
  endif
  echo '</select>' >> "$HTML"
  echo '</form>' >> "$HTML"

  # NEW COLUMN
  echo '</td><td>' >> "$HTML"
  # FORM 3
  echo '<form action="'"$act"'" method="get">' >> "$HTML"
  echo '<input type="hidden" name="db" value="'"$db"'">' >> "$HTML"
  echo '<input type="hidden" name="class" value="'"$class"'">' >> "$HTML"
  echo '<input type="hidden" name="image" value="'"$image"'">' >> "$HTML"
  echo '<input type="hidden" name="old" value="'"$dir"'">' >> "$HTML"
  echo '<input type="hidden" name="match" value="'"$match"'">' >> "$HTML"
  echo '<input type="hidden" name="limit" value="'"$limit"'">' >> "$HTML"
  if ($?slave) echo '<input type="hidden" name="slave" value="true">' >> "$HTML"
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

  # jump over single image stuff
  if ($limit > 1) goto bottom

  #
  # ENTIRE SECTION IS FOR SINGLE IMAGE DETAIL
  #
  set record = ( `curl -s -q -f -L "$CU/$db/$image" | jq -r '.'` )
  set imagebox = `echo "$record" | jq -r '.imagebox'`
  set scores = ( `echo "$record" | jq -r '.visual.scores|sort_by(.score)'` )
  set top1 = ( `echo "$record" | jq -r '.visual.scores|sort_by(.score)[-1]'` )

  # # get the scores
  echo "$scores" | jq -c '.[]' >! /tmp/$0:t.$$
  # count them
  set nscore = ( `cat /tmp/$0:t.$$ | /usr/bin/wc -l` )
  if ($nscore == 0) goto bottom
  #
  # report on scores
  #
  echo '<td><table style="font-size:75%;"><tr><th>CLASS</th><th>SCORE</th><th>MODEL</th></tr>' >> "$HTML"
  @ z = 0
  while ($z < $nscore)
    echo '<tr>' >> "$HTML"
    @ y = $nscore - $z
    set class_id = `cat /tmp/$0:t.$$ | /usr/bin/head -$y | /usr/bin/tail -1 | jq -r '.classifier_id'`
    set name = `cat /tmp/$0:t.$$ | /usr/bin/head -$y | /usr/bin/tail -1 | jq -r '.name'`
    set score = `cat /tmp/$0:t.$$ | /usr/bin/head -$y | /usr/bin/tail -1 | jq -r '.score'`
    # if a model was specified (name)
    if ($?name) then
      if ($?DEBUG) echo `date` "$0 $$ -- CHECKING MODEL $name" >>&! $LOGTO

      # find out type
      unset type
      # test if model name matches DIGITS convention of date
      set tf = ( `echo "$name" | sed 's/[0-9]*-[0-9]*-.*/DIGITS/'` )
      if ("$tf" == "DIGITS") then
        set type = "DIGITS"
      else 
	# Watson VR removes hyphens from db name (rough-fog becomes roughfog) 
	set device = ( `echo "$db" | sed "s/-//g"` )
	set tf = ( `echo "$name" | sed 's/'"$device"'_.*/CUSTOM/'` )
	if ("$tf" == "CUSTOM") set type = "CUSTOM"
      endif
      # default type if not DIGITS and not CUSTOM
      if ($?type == 0) set type = "default"
      switch ($type)
	case "CUSTOM":
	      echo '<td>' >> "$HTML"
	      echo '<a target="'"$name"-"$class_id"'" href="http://www.dcmartin.com/CGI/aah-index.cgi?db='"$db"'&class='"$class_id"'&display=icon">'"$class_id"'</a>' >> "$HTML"
	      echo '</td><td>'"$score"'</td><td>' >> "$HTML"
	      # http://www.dcmartin.com/AAH/cfmatrix.html?model=roughfog_292216250
	      echo '<a target="cfmatrix" href="http://age-at-home.mybluemix.net/cfmatrix.html?model='"$name"'">'"$name"'</a>' >> "$HTML"
	      echo '</td>' >> "$HTML"
	      breaksw
	case "DIGITS":
	      set ds_id = ( `curl -s -q "http://age-at-home.dcmartin.com:5001/models/$name.json" | jq -r '.dataset_id'` )
	      echo '<td>' >> "$HTML"
	      if ($#ds_id) then
		echo -n '<a target="'"$name"-"$class_id"'" href="' >> "$HTML"
		echo -n 'http://age-at-home.dcmartin.com:5001/datasets/'"$ds_id" >> "$HTML"
		echo '">'"$class_id"'</a>' >> "$HTML"
	      else
		echo "$class_id" >> "$HTML"
	      endif
	      echo '</td><td>'"$score"'</td><td>' >> "$HTML"
	      # http://192.168.1.30:5001/models/20170506-235510-f689
	      echo '<a target="digits" href="http://age-at-home.dcmartin.com:5001/models/'"$name"'">'"$name"'</a>' >> "$HTML"
	      echo '</td>' >> "$HTML"
	      breaksw
	default:
	      echo '<td>'"$class_id"'</td><td>'"$score"'</td><td>'"$name"'</td>' >> "$HTML"
	      breaksw
      endsw
      # end row
      echo '</tr>' >> "$HTML"
      @ z++
  end # while ($z < $nscore)
  # cleanup
  echo '</table>' >> "$HTML"
  echo '</td>' >> "$HTML"
bottom:
  rm -f /tmp/$0:t.$$
  # increment to next image
  @ k++
end # foreach 

# end row & table
echo "</tr></table>" >> "$HTML"

echo '</BODY>' >> "$HTML"
echo '</HTML>' >> "$HTML"

output:

#
# prepare for output
#

if (-s "$HTML") then
  echo "Content-Type: text/html; charset=utf-8"
  echo "Cache-Control: no-cache"
  @ age = $SECONDS - $DATE
  @ refresh = $TTL - $age
  echo "Age: $age"
  echo "Refresh: $refresh"
  echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
  echo ""
  cat "$HTML"
else
  echo "Content-Type: text/html; charset=utf-8"
  echo "Cache-Control: no-cache"
  echo ""
  echo "<HTML><HEAD><TITLE>$APP-$API"
  echo '{ "device":"'$db'","class":"'$class'","match":"'$match'","limit":"'$limit'" }'
  echo "</TITLE></HEAD>"
  echo '<script type="text/javascript" src="'$MIXPANELJS'"></script><script>mixpanel.track('"'"$APP-$API"');</script>"
  echo '<BODY>'
  echo '<P><A HREF="HTTP://'"$HTTP_HOST/CGI/$APP-$API.cgi?$QUERY_STRING"'">RETRY '"$QUERY_STRING"'</A></P>'
  echo '</BODY>'
  echo '</HTML>'
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

echo `date` "$0 $$ -- FINISH ($QUERY_STRING)" >>&! $LOGTO

