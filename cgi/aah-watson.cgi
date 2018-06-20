#!/bin/tcsh -b
setenv APP "aah"
setenv API "watson"

# setenv DEBUG true
# setenv VERBOSE true

# environment
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

# don't update statistics more than once per (in seconds)
set TTL = 1800
set SECONDS = `date "+%s"`
set DATE = `/bin/echo $SECONDS \/ $TTL \* $TTL | bc`
set AGE = `/bin/echo "$SECONDS - $DATE" | bc`

set DEBUG = true

setenv COMPOSITE "__COMPOSITE__"


if ($?QUERY_STRING) then
    /bin/echo `date` "$0:t $$ -- START ($QUERY_STRING)" >>&! $LOGTO
    set noglob
    set DB = `/bin/echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ("$DB" == "$QUERY_STRING") set DB = rough-fog
    set class = `/bin/echo "$QUERY_STRING" | sed 's/.*class=\([^&]*\).*/\1/'`
    if ("$class" == "$QUERY_STRING") unset class
    set id = `/bin/echo "$QUERY_STRING" | sed 's/.*id=\([^&]*\).*/\1/'`
    if ("$id" == "$QUERY_STRING") unset id
    set ext = `/bin/echo "$QUERY_STRING" | sed 's/.*ext=\([^&]*\).*/\1/'`
    if ("$ext" == "$QUERY_STRING") unset ext
    set display = `/bin/echo "$QUERY_STRING" | sed 's/.*display=\([^&]*\).*/\1/'`
    if ("$display" == "$QUERY_STRING") unset display
    set level = `/bin/echo "$QUERY_STRING" | sed 's/.*level=\([^&]*\).*/\1/'`
    if ("$level" == "$QUERY_STRING") unset level
    unset noglob
else
    /bin/echo `date` "$0:t $$ -- EXIT !! NO QUERY_STRING !!" >>&! $LOGTO
    exit
endif

if ($?DB) then
  set db = "$DB:h"
else
  set DB = rough-fog
  set db = "$DB"
endif

set DBt = ( "$DB:t" )
set dbt = ( "$db:t" ) 
if ($#dbt && $dbt != $db && $?class == 0) then
  set class = "$db:t"
  set db = "$db:h"
endif
if ($#DBt && $#dbt && $?id == 0) then
  set id = "$DB:t"
  set ide = ( $id:e )
  if ($#ide == 0) unset id
endif
if ($?class) then
  set class = ( `/bin/echo "$class" | sed 's@//@/@g' | sed 's@/$@@'` )
endif

if ($?db) then
    setenv QUERY_STRING "db=$db"
endif
if ($?ext) then
    setenv QUERY_STRING "$QUERY_STRING&ext=$ext"
endif
if ($?display) then
    setenv QUERY_STRING "$QUERY_STRING&display=$display"
endif
if ($?level) then
    setenv QUERY_STRING "$QUERY_STRING&level=$level"
endif
if ($?class) then
    setenv QUERY_STRING "$QUERY_STRING&class=$class"
endif
if ($?id) then
    setenv QUERY_STRING "$QUERY_STRING&id=$id"
endif

if ($?DEBUG) /bin/echo `date` "$0:t $$ -- query string ($QUERY_STRING)" >>&! $LOGTO

# check which image (ext = { full, crop } -> type = { jpg, jpeg } )
if ($?ext) then
    set ext = $ext:h
    if ($ext == "full") set type = "jpg"
    if ($ext == "crop") set type = "jpeg"
else
    set ext = "full"
    set type = "jpg"
endif

#
# handle images (files)
#
if ($?id) then
  if (-d "$AAHDIR/$db/.models/$class/$id") then
    if ($?VERBOSE) /bin/echo `date` "$0:t $$ -- got directory $id ($class)" >>&! $LOGTO
    set ext = "dir"
  endif

    # do the normal thing to find the file with this ID (SLOOOOOOW)
    if ($ext != "dir") then
      set base = "$AAHDIR/$db/.models/$class"
      set images = ( `find "$base" -name "$id" -print | egrep -v "$COMPOSITE"` )
    else
      set base = "$AAHDIR/$db/.models/$class/$id"
      set images = ( `find "$base" -type l -print | egrep -v "$COMPOSITE"` )
    endif

    if ($?VERBOSE) /bin/echo `date` "$0:t $$ -- BASE ($base) ID ($id) images ($#images)" >>&! $LOGTO

    if ($#images == 0) then
      /bin/echo "Status: 404 Not Found"
      goto done
    endif

    /bin/echo "Access-Control-Allow-Origin: *"
    /bin/echo "Age: $AGE"
    /bin/echo "Cache-Control: max-age=$TTL"
    /bin/echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`

    /bin/echo "Content-Location: $HTTP_HOST/CGI/$APP-$API.cgi?$QUERY_STRING"

    #  singleton image
    if ($#images == 1 && $ext != "dir") then
	/bin/echo "Content-Type: image/jpeg"
	/bin/echo ""
	if ($?VERBOSE) /bin/echo `date` "$0:t $$ -- SINGLETON ($id)" >>&! $LOGTO
	dd if="$images"
    else if ($#images && $ext == "dir") then
	if ($?VERBOSE) /bin/echo `date` "$0:t $$ -- COMPOSITE IMAGES ($#images) " >>&! $LOGTO
	set blend = "$base/$COMPOSITE.$type"
	if (-s "$blend") then
	  set last = ( `stat -r "$blend" | awk '{ print $10 }'` )

	  foreach i ( $images )
	    set ilast = ( `stat -r "$i" | awk '{ print $10 }'` )
	    if ($ilast > $last) then
	    rm -f "$blend"
	    break
	  endif
       endif
       if (! -e "$blend") then
	if ($#images > 1) then
	    composite -blend 50 $images "$blend:r.$$.$blend:e"
	else
	    cp "$images" "$blend:r.$$.$blend:e"
	endif
	switch ($type)
 	  case "jpg": # 640x480 image
	    set csize = "600x40"
	    set psize = "48"
	    breaksw
	  case "jpeg": # 224x224 image
	    set csize = "200x20"
	    set psize = "18"
	    breaksw
	endsw
	# montage -label "$id" "$blend:r.$$.$blend:e" -pointsize 48 -frame 0 -geometry +10+10 "$blend"
        convert \
	  -pointsize "$psize" -size "$csize" \
	  xc:none -gravity center -stroke black -strokewidth 2 -annotate 0 \
	  "$id" \
	  -background none -shadow "100x3+0+0" +repage -stroke none -fill white -annotate 0 \
	  "$id" \
	  "$blend:r.$$.$blend:e" \
	  +swap -gravity south -geometry +0-3 -composite \
	  "$blend"
	/bin/rm -f "$blend:r.$$.$blend:e"
	if (! -s "$blend") then
	  if ($?VERBOSE) /bin/echo `date` "$0:t $$ -- creation of composite image failed ($images)" >>&! $LOGTO
	  set failure = "composite failure"
          goto done
	endif
      endif
      /bin/echo "Content-Type: image/jpeg"
      /bin/echo ""
      if ($?VERBOSE) /bin/echo `date` "$0:t $$ -- SINGLETON ($id)" >>&! $LOGTO
      dd if="$blend"
    else
	#  trick is to use id to pass regexp base
	/bin/echo "Content-Type: application/zip"
	/bin/echo ""
	if ($?VERBOSE) /bin/echo `date` "$0:t $$ -- MULTIPLE IMAGES ZIP ($#images)" >>&! $LOGTO
	zip - $images | dd of=/dev/stdout
    endif

    goto done
endif

#
# build HTML
#
set OUTPUT = "$TMP/$APP-$API-$$.html"

#
# test hierarchy level (label/device/class); class could be a UNIX directory hierarchy, e.g. "/vehicle/car/sedan" (AFAIK :-)
#

if ($?class) then
  set base = "$AAHDIR/$db/.models/$class"
  # find all images in the $class directory
  set images = ( `find "$base" -type l -print | egrep -v "$COMPOSITE" | sed "s@$base"".*/\(.*\)@\1@"` )
  # get subclasses
  set allsubdirs = ( `find "$base" -name "[^\.]*" -type d -print | sed "s|$base||" | sed "s|^/||"` )
  foreach c ( $allsubdirs )
    if ("$c" == "$c:t") then
      if ($?classes) then
	set classes = ( $classes "$c" )
      else
	set classes = ( "$c" )
      endif
    endif
  end 
else 
  set base = "$AAHDIR/$db/.models"
  # find all directories in the $db directory (not includes those beginning with ".", e.g. ".skipped")
  set allsubdirs = ( `find "$base" -name "[^\.]*" -type d -print | sed "s|$base||" | sed "s|^/||"` )
  foreach c ( $allsubdirs )
    if ("$c" == "$c:t") then
      if ($?classes) then
	set classes = ( $classes "$c" )
      else
	set classes = ( "$c" )
      endif
    endif
  end 
endif

set MIXPANELJS = "http://$HTTP_HOST/script/mixpanel-aah.js"

if ($?class) then
    if ($?VERBOSE) /bin/echo `date` "$0:t $$ -- CLASS ($class)" >>&! $LOGTO
    # should make a path name
    set dir = "$db/$class"
    if ($?VERBOSE) /bin/echo `date` "$0:t $$ -- DIR ($dir)" >>&! $LOGTO
    /bin/echo '<html><head><title>Index of '"$dir"'</title></head>' >! "$OUTPUT"
    /bin/echo '<script type="text/javascript" src="'$MIXPANELJS'"></script><script>mixpanel.track('"'"$APP-$API"'"',{"db":"'$db'","dir":"'$dir'"});</script>' >> "$OUTPUT"
    /bin/echo '<body bgcolor="white"><h1>Index of '"$dir"'</h1><hr>' >>! "$OUTPUT"
    if ($?display == 0) then
      /bin/echo '<pre>' >>! "$OUTPUT"
      set parent = "$class:h:h"
      if ($parent != "$class") then
	/bin/echo '<a href="http://'"$HTTP_HOST/CGI/$APP-$API.cgi?db=$db&ext=$ext&class=$parent"'">../</a>' >>! "$OUTPUT"
      else
	/bin/echo '<a href="http://'"$HTTP_HOST/CGI/$APP-$API.cgi?db=$db&ext=$ext"'">../</a>' >>! "$OUTPUT"
      endif
    else # display icons for directories
      /bin/echo '<pre>' >>! "$OUTPUT"
      set parent = "$class:h:h"
      if ($parent != "$class") then
	/bin/echo '<a href="http://'"$HTTP_HOST/CGI/$APP-$API.cgi?db=$db&ext=$ext&display=icon&class=$parent"'">../</a>' >>! "$OUTPUT"
      else
	/bin/echo '<a href="http://'"$HTTP_HOST/CGI/$APP-$API.cgi?db=$db&ext=$ext&display=icon"'">../</a>' >>! "$OUTPUT"
      endif
      /bin/echo '</pre>' >>! "$OUTPUT"
    endif
    if ($?classes) then
      if ($?VERBOSE) /bin/echo `date` "$0:t $$ -- SUBCLASSES ($classes)" >>&! $LOGTO
      foreach i ( $classes )
	if ($?display) then
	  /bin/echo '<a href="http://'"$HTTP_HOST/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&display=icon&class='"$class/$i"'">' >>! "$OUTPUT"
	  /bin/echo '<img width="24%" alt="'"$i"'" src="http://'"$HTTP_HOST/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&class='"$class"'&id='"$i"'">' >>! "$OUTPUT"
	  /bin/echo '</a>' >>! "$OUTPUT"
	else 
	  set name = '<a href="http://www.dcmartin.com/CGI/aah-watson.cgi?db='"$db"'&ext='"$ext"'&class='"$class/$i"'">'"$i"'/</a>'
	  set ctime = `date '+%d-%h-%Y %H:%M'`
	  set fsize = `du -sk "$AAHDIR/label/$db/$class/$i" | awk '{ print $1 }'`
	  /bin/echo "$name		$ctime		$fsize" >>! "$OUTPUT"
	endif
      end
    endif

    if ($?display) /bin/echo '<br>' >>! "$OUTPUT"

    if ($?VERBOSE) /bin/echo `date` "$0:t $$ -- HANDLING IMAGES ($images)" >>&! $LOGTO
    foreach i ( $images )
      if ($?display) then
        if (! $?classes) then
	  /bin/echo '<a href="http://'"$HTTP_HOST/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&class='"$class"'&id='"$i"'">' >>! "$OUTPUT"
	  /bin/echo '<img width="16%" alt="'"$i.$type"'" src="http://'"$HTTP_HOST/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&class='"$class"'&id='"$i"'">' >>! "$OUTPUT"
	  /bin/echo '</a>' >>! "$OUTPUT"
	endif
      else
	set file = '<a href="http://'"$HTTP_HOST/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&class='"$class"'&id='"$i"'">'"$i"'</a>' 
	set ctime = `date '+%d-%h-%Y %H:%M'`
	set fsize = `find "$AAHDIR/$db/.model/$class" -name "$i" -print | xargs ls -l | awk '{ print $5 }'`
	/bin/echo "$file		$ctime		$fsize" >>! "$OUTPUT"
      endif
    end
    if ($?display == 0) then
      /bin/echo '</pre>' >>! "$OUTPUT"
    endif
    /bin/echo '<hr></body></html>' >>! "$OUTPUT"
    if ($?VERBOSE) /bin/echo `date` "$0:t $$ -- DONE" >>&! $LOGTO
else if ($?classes) then
  if ($?VERBOSE) /bin/echo `date` "$0:t $$ -- TOP-LEVEL ($classes)" >>&! $LOGTO
    # should be a directory listing of directories
    set dir = "$db"
    /bin/echo '<html><head><title>Index of '"$dir"'/</title></head>' >! "$OUTPUT"
    /bin/echo '<script type="text/javascript" src="'$MIXPANELJS'"></script><script>mixpanel.track('"'"$APP-$API"'"',{"db":"'$db'"});</script>' >> "$OUTPUT"
    /bin/echo '<body bgcolor="white"><h1>Index of '"$dir"'</h1><hr>' >>! "$OUTPUT"
    /bin/echo '<pre>' >>! "$OUTPUT"
    if ($?display) then
      /bin/echo '<a href="http://'"$HTTP_HOST/CGI/$APP-$API.cgi?db=$db&ext=$ext"'/">../</a>' >>! "$OUTPUT"
      /bin/echo '</pre>' >>! "$OUTPUT"
    else
      /bin/echo '<a href="http://'"$HTTP_HOST/CGI/$APP-$API.cgi?db=$db&ext=$ext&display=icon"'/">../</a>' >>! "$OUTPUT"
    endif
    foreach i ( $classes )
      if ($?display == 0) then
	set name = '<a href="http://www.dcmartin.com/CGI/aah-watson.cgi?db='"$db"'&ext='"$ext"'&class='"$i"'/">'"$i"'/</a>' >>! "$OUTPUT"
	set ctime = `date '+%d-%h-%Y %H:%M'`
	set fsize = `du -sk "$AAHDIR/label/$db/$i" | awk '{ print $1 }'`
	/bin/echo "$name		$ctime		$fsize" >>! "$OUTPUT"
      else
	/bin/echo '<a href="http://'"$HTTP_HOST/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&display=icon&class='"$i"'">' >>! "$OUTPUT"
	/bin/echo '<img width="24%" alt="'"$i"'" src="http://'"$HTTP_HOST/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&class=&id='"$i"'">' >>! "$OUTPUT"
	/bin/echo '</a>' >>! "$OUTPUT"
      endif
    end
    if ($?display == 0) then
      /bin/echo '</pre>' >>! "$OUTPUT"
    endif
    /bin/echo '<hr></body></html>' >>! "$OUTPUT"
endif

output:

/bin/echo "Access-Control-Allow-Origin: *"
/bin/echo "Age: $AGE"
/bin/echo "Cache-Control: max-age=$TTL"
/bin/echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
/bin/echo "Content-Type: text/html"
/bin/echo "Content-Location: $HTTP_HOST/CGI/$APP-$API.cgi?$QUERY_STRING"
/bin/echo ""

cat "$OUTPUT"

done:

rm -f "$OUTPUT"

/bin/echo `date` "$0:t $$ -- FINISH" >>&! $LOGTO
