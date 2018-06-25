#!/bin/tcsh -b
setenv APP "aah"
setenv API "classify"

setenv DEBUG true
unsetenv VERBOSE true

# environment
if ($?DIGITS_HOST == 0) setenv DIGITS_HOST "192.168.1.40:32769"
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
echo `date` "$0:t $$ -- START ($QUERY_STRING)" >>&! $LOGTO

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

# get list of image identifiers
set url = "localhost/CGI/aah-images.cgi?db=$db"
set out = /tmp/$0:t.$$.json
curl -s -q -f -L "$url" -o "$out"
if (! -s "$out") then
  if ($?DEBUG) echo "$0:t $$ -- $db -- failed $url" >>&! $LOGTO
  rm -f "$out"
  goto output 
else
  set nimage = ( `jq '.ids?|length' "$out"` )
  if ($?VERBOSE) echo "$0:t $$ -- $db -- found total of $nimage images" >>&! $LOGTO
  # select a limited numbers of images matching the search expression
  set images = ( `jq -r 'limit('$limit';.ids[]|match("'$match'.*")|.string)' "$out"` )
  if ($#images == 0 || "$images" == "null") then
    if ($?DEBUG) echo "$0:t $$ -- $db -- failed to find images ($images) matching: $match" >>&! $LOGTO
    set images = ()
  endif
  rm -f "$out"
endif

if ($?images) then
  if ($?VERBOSE) echo "$0:t $$ -- $db -- found $#images images" >>&! $LOGTO
else
  if ($?DEBUG) echo "$0:t $$ -- $db -- no images defined" >>&! $LOGTO
  set images = ()
endif

###
### get labels and location 
###

# get location
set location = ( `curl -s -q -f -L "localhost/CGI/$APP-devices.cgi?db=$db" | jq -r '.location'` )
if ($#location == 0 || "$location" == "null") then
  if ($?DEBUG) echo "$0:t $$ -- $db -- no such device ($location)" >>&! $LOGTO
  goto output
endif

# get labels
set labels = ( `curl -s -q "localhost/CGI/$APP-labels.cgi?db=$db" | jq -r '.classes|sort_by(.name)[].name'` )
if ($#labels == 0 || "$labels" == "null") then
  if ($?DEBUG) echo "$0:t $$ -- $db -- no labels for db $db" >>&! $LOGTO
  set labels = ()
endif

# choices by end-user on which images to curate
set image_classes = ( "recent" "confusing" "unknown" $labels )

set date = "DATE"
set seqid = "SEQID"

# header
set MIXPANELJS = "http://$HTTP_HOST/script/mixpanel-aah.js"
set HTML = "$TMP/$APP-$API.$$.html"
echo "<HTML><HEAD><TITLE>$APP-$API" >! "$HTML"
echo '{ "device":"'$db'","class":"'$class'","match":"'$match'","limit":"'$limit'" }' >> "$HTML"
echo "</TITLE></HEAD>" >> "$HTML"
echo '<script type="text/javascript" src="'$MIXPANELJS'"></script><script>mixpanel.track('"'"$APP-$API"');</script>" >> "$HTML"

# body
echo '<BODY>' >> "$HTML"

if ($?slave == 0) echo '<p>'"$db"' : match date by <i>regexp</i>; slide image count (max = '$IMAGE_LIMIT'); select all or <i>class</i>; then press <b>CHANGE</b>' >> "$HTML"

## change selection criteria
echo '<form action="'"http://$HTTP_HOST/CGI/$APP-$API"'.cgi">' >> "$HTML"
if ($?slave) echo '<input type="hidden" name="slave" value="true">' >> "$HTML"
echo '<input type="hidden" name="db" value="'"$db"'">' >> "$HTML"
echo '<input type="text" name="match" value="'"$match"'">' >> "$HTML"
echo '<input type="range" name="limit" value="'"$limit"'" max="'$IMAGE_LIMIT'" min="1">' >> "$HTML"
echo '<select name="class">' >> "$HTML"
echo '<option value="'"$class"'">'"$class"'</option>' >> "$HTML" # current class (dir) is first option
if ($class != "all") echo '<option value="all">all</option>' >> "$HTML" # all classes is second option
foreach c ( $image_classes )
    if ($c != $class) echo '<option value="'"$c"'">'"$c"'</option>' >> "$HTML" # don't include current class
end
echo '</select>' >> "$HTML"
echo '<input type="submit" style="background-color:#ff9933" value="CHANGE"></form>' >> "$HTML"

@ ncolumns = 4
if ($#images < $ncolumns) @ ncolumns = $#images
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

  if ($?DEBUG) echo `date` "$0:t $$ -- PROCESSING IMAGE ($k/$limit) ($image)" >>&! $LOGTO

  # get image details
  set jpm = `echo "$image" | sed "s/\(.*\)-.*-.*/\1/"` # get the image date for matching
  set time = `echo "$image" | sed "s/\(....\)\(..\)\(..\)\(..\)\(..\).*-.*/\1\/\2\/\3 \4:\5/"` # breakdown image identifier into time components for image label

  # how to access the image (and sample)
  set img = "http://$HTTP_HOST/CGI/$APP-images.cgi?db=$db&id=$image&ext=full"
  set jpeg = "http://$HTTP_HOST/CGI/$APP-images.cgi?db=$db&id=$image&ext=crop"

  # note change in limit to one (1) as we are inspecting single image (see width specification below)
  if ($?slave) then
    set cgi = "http://$HTTP_HOST/CGI/$APP-$API.cgi?db=$db&class=$class&match=$image&limit=1&slave=true"
  else
    set cgi = "http://$HTTP_HOST/CGI/$APP-$API.cgi?db=$db&class=$class&match=$image&limit=1"
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
  echo '<input type="hidden" name="match" value="'"$match"'">' >> "$HTML"
  echo '<input type="hidden" name="limit" value="'"$limit"'">' >> "$HTML"
  if ($?slave) echo '<input type="hidden" name="slave" value="true">' >> "$HTML"
  echo '<select name="new" onchange="this.form.submit()">' >> "$HTML"
  echo '<option selected value="'"$class"'">'"$class"'</option>' >> "$HTML"
  echo '<option value="'"$location"'">'"$location"'</option>' >> "$HTML"
  if ($?labels) then
    foreach i ( $labels)
      set j = "$i:t"
      if (($j != $class) && ($j != $location)) echo '<option value="'"$i"'">'"$i"'</option>' >> "$HTML"
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
  echo '<input type="hidden" name="match" value="'"$match"'">' >> "$HTML"
  echo '<input type="hidden" name="limit" value="'"$limit"'">' >> "$HTML"
  if ($?slave) echo '<input type="hidden" name="slave" value="true">' >> "$HTML"
  echo '<input type="text" size="5" name="add" value="'"$add"'">' >> "$HTML"
  echo '<input type="submit" style="background-color:#ff9933" value="OK">' >> "$HTML"
  echo '</form>' >> "$HTML"

  echo '</td>' >> "$HTML"
  echo '</tr>' >> "$HTML"
  echo '</table>' >> "$HTML"

  # this conditional is based on inspection in single image mode
  if ($#images > 1) then
    echo '<a href="'"$cgi"'"><img width="'$MODEL_IMAGE_WIDTH'" height="'$MODEL_IMAGE_HEIGHT'" alt="'"$image:t:r"'" src="'"$img"'" onmouseover="this.src='"'""$jpeg""'"'" onmouseout="this.src='"'""$img""'"'"></a>' >> "$HTML"
  else
    echo '<a href="'"$cgi"'"><img width="'$CAMERA_IMAGE_WIDTH'" height="'$CAMERA_IMAGE_HEIGHT'" alt="'"$image:t:r"'" src="'"$img"'" onmouseover="this.src='"'""$jpeg""'"'" onmouseout="this.src='"'""$img""'"'"></a>' >> "$HTML"
  endif
  echo '<figcaption style="font-size:50%;">'"$time"'</figcaption>' >> "$HTML" 
  echo '</figure>' >> "$HTML"
  echo '</td>' >> "$HTML"

  # jump over single image stuff
  if ($#images >  1) goto bottom

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
  set nscore = ( `cat /tmp/$0:t.$$ | wc -l` )
  if ($nscore == 0) goto bottom
  #
  # report on scores
  #
  echo '<td><table style="font-size:75%;"><tr><th>CLASS</th><th>SCORE</th><th>MODEL</th></tr>' >> "$HTML"
  @ z = 0
  while ($z < $nscore)
    echo '<tr>' >> "$HTML"
    @ y = $nscore - $z
    set class_id = `cat /tmp/$0:t.$$ | head -$y | tail -1 | jq -r '.classifier_id'`
    set name = `cat /tmp/$0:t.$$ | head -$y | tail -1 | jq -r '.name'`
    set score = `cat /tmp/$0:t.$$ | head -$y | tail -1 | jq -r '.score'`
    # if a model was specified (name)
    if ($?name) then
      if ($?DEBUG) echo `date` "$0:t $$ -- CHECKING MODEL $name" >>&! $LOGTO
      # find out type
      unset type
      # test if model name matches DIGITS convention of date
      set tf = ( `echo "$name" | sed 's/[0-9]*-[0-9]*-.*/DIGITS/'` )
      if ("$tf" == "DIGITS") then
        set type = "DIGITS"
      else if ("$name" != "default" && "$name:h" == "$name:t") then 
	set type = "CUSTOM"
      endif
      # default type if not DIGITS and not CUSTOM
      if ($?type == 0) set type = "default"
      switch ($type)
	case "CUSTOM":
	      echo '<td>' >> "$HTML"
	      echo '<a target="'"$name"-"$class_id"'" href="http://'"$HTTP_HOST"'/CGI/aah-index.cgi?db='"$db"'&class='"$class_id"'&display=icon">'"$class_id"'</a>' >> "$HTML"
	      echo '</td><td>'"$score"'</td><td>' >> "$HTML"
	      echo '<a target="cfmatrix" href="http://'"$HTTP_HOST"'/cfmatrix.html?model='"$name"'">'"$name"'</a>' >> "$HTML"
	      echo '</td>' >> "$HTML"
	      breaksw
	case "DIGITS":
	      set ds_id = ( `curl -s -q "http://$DIGITS_HOST/models/$name.json" | jq -r '.dataset_id'` )
	      echo '<td>' >> "$HTML"
	      if ($#ds_id) then
		echo -n '<a target="'"$name"-"$class_id"'" href="' >> "$HTML"
		echo -n 'http://'"$DIGITS_HOST"'/datasets/'"$ds_id" >> "$HTML"
		echo '">'"$class_id"'</a>' >> "$HTML"
	      else
		echo "$class_id" >> "$HTML"
	      endif
	      echo '</td><td>'"$score"'</td><td>' >> "$HTML"
	      echo '<a target="digits" href="http://'"$DIGITS_HOST"'/models/'"$name"'">'"$name"'</a>' >> "$HTML"
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
  echo '<P><A HREF="http://'"$HTTP_HOST/CGI/$APP-$API.cgi?$QUERY_STRING"'">RETRY '"$QUERY_STRING"'</A></P>'
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

echo `date` "$0:t $$ -- FINISH ($QUERY_STRING)" >>&! $LOGTO

