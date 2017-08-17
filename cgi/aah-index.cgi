#!/bin/csh -fb
setenv APP "aah"
setenv API "index"
setenv LAN "192.168.1"
setenv WWW "$LAN".32
setenv DIGITS "$LAN".30
setenv WAN "www.dcmartin.com"
setenv TMP "/var/lib/age-at-home"

# don't update statistics more than once per (in seconds)
set TTL = 1800
set SECONDS = `date "+%s"`
set DATE = `/bin/echo $SECONDS \/ $TTL \* $TTL | bc`
set AGE = `/bin/echo "$SECONDS - $DATE" | bc`

set DEBUG = true

setenv COMPOSITE "__COMPOSITE__"


if ($?QUERY_STRING) then
    /bin/echo `date` "$0 $$ -- START ($QUERY_STRING)" >>! $TMP/LOG
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
    /bin/echo `date` "$0 $$ -- PLEASE SPECIFY QUERY_STRING" >>! $TMP/LOG
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

if ($?DEBUG) /bin/echo `date` "$0 $$ -- query string ($QUERY_STRING)" >>! $TMP/LOG

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
  set fid = "$id:r"
  if ("$fid" == "$id") then
    if ($?DEBUG) /bin/echo `date` "$0 $$ -- got directory $id ($class)" >>! $TMP/LOG
    set ext = "dir"
  else
    set id = "$fid"
  endif

    # do the normal thing to find the file with this ID (SLOOOOOOW)
    if ($ext != "dir") then
      set base = "$TMP/label/$db/$class"
      set images = ( `find "$base" -name "$id""*.$type" -type f -print | egrep -v "$COMPOSITE"` )
    else
      set base = "$TMP/label/$db/$class/$id"
      set images = ( `find "$base" -name "*.$type" -type f -print | egrep -v "$COMPOSITE"` )
    endif

    if ($?DEBUG) /bin/echo `date` "$0 $$ -- BASE ($base) ID ($id) images ($#images)" >>! $TMP/LOG

    if ($#images == 0) then
      /bin/echo "Status: 404 Not Found"
      goto done
    endif

    /bin/echo "Access-Control-Allow-Origin: *"
    /bin/echo "Age: $AGE"
    /bin/echo "Cache-Control: max-age=$TTL"
    /bin/echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`

    /bin/echo "Content-Location: $WAN/CGI/$APP-$API.cgi?$QUERY_STRING"

    #  singleton image
    if ($#images == 1 && $ext != "dir") then
	/bin/echo "Content-Type: image/jpeg"
	/bin/echo ""
	if ($?DEBUG) /bin/echo `date` "$0 $$ -- SINGLETON ($id)" >>! $TMP/LOG
	dd if="$images"
    else if ($#images && $ext == "dir") then
	if ($?DEBUG) /bin/echo `date` "$0 $$ -- COMPOSITE IMAGES ($#images) " >>! $TMP/LOG
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
	    /usr/local/bin/composite -blend 50 $images "$blend:r.$$.$blend:e"
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
	# /usr/local/bin/montage -label "$id" "$blend:r.$$.$blend:e" -pointsize 48 -frame 0 -geometry +10+10 "$blend"
        /usr/local/bin/convert \
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
	  if ($?DEBUG) /bin/echo `date` "$0 $$ -- creation of composite image failed ($images)" >>! $TMP/LOG
	  set failure = "composite failure"
          goto done
	endif
      endif
      /bin/echo "Content-Type: image/jpeg"
      /bin/echo ""
      if ($?DEBUG) /bin/echo `date` "$0 $$ -- SINGLETON ($id)" >>! $TMP/LOG
      dd if="$blend"
    else
	#  trick is to use id to pass regexp base
	/bin/echo "Content-Type: application/zip"
	/bin/echo ""
	if ($?DEBUG) /bin/echo `date` "$0 $$ -- MULTIPLE IMAGES ZIP ($#images)" >>! $TMP/LOG
	zip - $images | dd of=/dev/stdout
    endif

    goto done
endif

#
# test hierarchy level (label/device/class); class could be a UNIX directory hierarchy, e.g. "/vehicle/car/sedan" (AFAIK :-)
#

if ($?class == 0) then
  # top-level
  set base = "$TMP/label/$db"
else 
  set base = "$TMP/label/$db/$class"
  if (-e "$base/.images.json") then
    if ((-M "$base/.images.json") < (-M "$base")) then
      rm -f "$base/.images.json"
    endif
  endif
  if (! -e "$base/.images.json") then
    # find all images in the $class directory
    if ($?DEBUG) /bin/echo `date` "$0 $$ -- FINDING IMAGES" >>! $TMP/LOG
    find "$base" -name "*.$type" -type f -print | egrep -v "$COMPOSITE" | sed "s@$base"".*/\(.*\)\.$type@\1@" >! "$base/.images.json"
  endif
  set images = ( `cat "$base/.images.json"` )
endif

# get subclasses
if (-e "$base/.classes.json") then
  if ((-M "$base/.classes.json") < (-M "$base")) then
    rm -f "$base/.classes.json"
  endif
endif
if (! -e "$base/.classes.json") then
  if ($?DEBUG) /bin/echo `date` "$0 $$ -- FINDING CLASSES" >>! $TMP/LOG
  find "$base" -name "[^\.]*" -type d -print | sed "s|$base||" | sed "s|^/||" >! "$base/.classes.json"
endif
set allsubdirs = ( `cat "$base/.classes.json"` )
foreach c ( $allsubdirs )
  if ("$c" == "$c:t") then
    if ($?classes) then
      set classes = ( $classes "$c" )
    else
      set classes = ( "$c" )
    endif
  endif
end 

#
# build HTML
#
if ($?display) then
  set OUTPUT = "$base/.index.$ext.icon.html"
else
  set OUTPUT = "$base/.index.$ext.html"
endif

if (-s "$OUTPUT" && ((-M "$base") <= (-M "$OUTPUT"))) then
  if ($?DEBUG) /bin/echo `date` "$0 $$ -- CACHED ($OUTPUT)" >>! $TMP/LOG
  goto output
else
  rm -f "$OUTPUT"
endif

set MIXPANELJS = "http://$WAN/CGI/script/mixpanel-aah.js"

if ($?class) then
  if ($?DEBUG) /bin/echo `date` "$0 $$ -- BUILD ($class)" >>! $TMP/LOG
  # should make a path name
  set dir = "$db/$class"
  if ($?DEBUG) /bin/echo `date` "$0 $$ -- DIR ($dir)" >>! $TMP/LOG
  /bin/echo '<html><head><title>Index of '"$dir"'</title></head>' >! "$OUTPUT"
  /bin/echo '<script type="text/javascript" src="'$MIXPANELJS'"></script><script>mixpanel.track('"'"$APP-$API"'"',{"db":"'$db'","dir":"'$dir'"});</script>' >> "$OUTPUT"
  /bin/echo '<body bgcolor="white"><h1>Index of '"$dir"'</h1><hr>' >>! "$OUTPUT"
  if ($?display == 0) then
    /bin/echo '<pre>' >>! "$OUTPUT"
    set parent = "$class:h:h"
    if ($parent != "$class") then
      /bin/echo '<a href="http://'"$WAN/CGI/$APP-$API.cgi?db=$db&ext=$ext&class=$parent"'">../</a>' >>! "$OUTPUT"
    else
      /bin/echo '<a href="http://'"$WAN/CGI/$APP-$API.cgi?db=$db&ext=$ext"'">../</a>' >>! "$OUTPUT"
    endif
  else # display icons for directories
    /bin/echo '<pre>' >>! "$OUTPUT"
    set parent = "$class:h:h"
    if ($parent != "$class") then
      /bin/echo '<a href="http://'"$WAN/CGI/$APP-$API.cgi?db=$db&ext=$ext&display=icon&class=$parent"'">../</a>' >>! "$OUTPUT"
    else
      /bin/echo '<a href="http://'"$WAN/CGI/$APP-$API.cgi?db=$db&ext=$ext&display=icon"'">../</a>' >>! "$OUTPUT"
    endif
    /bin/echo '</pre>' >>! "$OUTPUT"
  endif
  if ($?classes) then
    if ($?DEBUG) /bin/echo `date` "$0 $$ -- SUBCLASSES ($classes)" >>! $TMP/LOG
    foreach i ( $classes )
      if ($?display) then
	/bin/echo '<a href="http://'"$WAN/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&display=icon&class='"$class/$i"'">' >>! "$OUTPUT"
	/bin/echo '<img width="24%" alt="'"$i"'" src="http://'"$WAN/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&class='"$class"'&id='"$i"'">' >>! "$OUTPUT"
	/bin/echo '</a>' >>! "$OUTPUT"
      else 
	set name = '<a href="http://www.dcmartin.com/CGI/aah-index.cgi?db='"$db"'&ext='"$ext"'&class='"$class/$i"'">'"$i"'/</a>'
	set ctime = `date '+%d-%h-%Y %H:%M'`
	set fsize = `du -sk "$TMP/label/$db/$class/$i" | awk '{ print $1 }'`
	/bin/echo "$name		$ctime		$fsize" >>! "$OUTPUT"
      endif
    end
  endif

  if ($?display) /bin/echo '<br>' >>! "$OUTPUT"

  if ($?DEBUG) /bin/echo `date` "$0 $$ -- HANDLING IMAGES ($#images)" >>! $TMP/LOG
  foreach i ( $images )
    if ($?display) then
      if (! $?classes) then
	/bin/echo '<a href="http://'"$WAN/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&class='"$class"'&id='"$i"'.'"$type"'">' >>! "$OUTPUT"
	/bin/echo '<img width="16%" alt="'"$i.$type"'" src="http://'"$WAN/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&class='"$class"'&id='"$i"'.'"$type"'">' >>! "$OUTPUT"
	/bin/echo '</a>' >>! "$OUTPUT"
      endif
    else
      set file = '<a href="http://'"$WAN/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&class='"$class"'&id='"$i"'.'"$type"'">'"$i.$type"'</a>' 
      set ctime = `date '+%d-%h-%Y %H:%M'`
      set fsize = `find "$TMP/label/$db/$class" -name "$i.$type" -print | xargs ls -l | awk '{ print $5 }'`
      /bin/echo "$file		$ctime		$fsize" >>! "$OUTPUT"
    endif
  end
  if ($?display == 0) then
    /bin/echo '</pre>' >>! "$OUTPUT"
  endif
  /bin/echo '<hr></body></html>' >>! "$OUTPUT"
  if ($?DEBUG) /bin/echo `date` "$0 $$ -- DONE" >>! $TMP/LOG
else if ($?classes) then
  if ($?DEBUG) /bin/echo `date` "$0 $$ -- BUILD ($classes)" >>! $TMP/LOG
    # should be a directory listing of directories
    set dir = "$db"
    /bin/echo '<html><head><title>Index of '"$dir"'/</title></head>' >! "$OUTPUT"
    /bin/echo '<script type="text/javascript" src="'$MIXPANELJS'"></script><script>mixpanel.track('"'"$APP-$API"'"',{"db":"'$db'"});</script>' >> "$OUTPUT"
    /bin/echo '<body bgcolor="white"><h1>Index of '"$dir"'</h1><hr>' >>! "$OUTPUT"
    /bin/echo '<pre>' >>! "$OUTPUT"
    if ($?display) then
      /bin/echo '<a href="http://'"$WAN/CGI/$APP-$API.cgi?db=$db&ext=$ext"'/">../</a>' >>! "$OUTPUT"
      /bin/echo '</pre>' >>! "$OUTPUT"
    else
      /bin/echo '<a href="http://'"$WAN/CGI/$APP-$API.cgi?db=$db&ext=$ext&display=icon"'/">../</a>' >>! "$OUTPUT"
    endif
    foreach i ( $classes )
      if ($?display == 0) then
	set name = '<a href="http://www.dcmartin.com/CGI/aah-index.cgi?db='"$db"'&ext='"$ext"'&class='"$i"'/">'"$i"'/</a>' >>! "$OUTPUT"
	set ctime = `date '+%d-%h-%Y %H:%M'`
	set fsize = `du -sk "$TMP/label/$db/$i" | awk '{ print $1 }'`
	/bin/echo "$name		$ctime		$fsize" >>! "$OUTPUT"
      else
	/bin/echo '<a href="http://'"$WAN/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&display=icon&class='"$i"'">' >>! "$OUTPUT"
	/bin/echo '<img width="24%" alt="'"$i"'" src="http://'"$WAN/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&class=&id='"$i"'">' >>! "$OUTPUT"
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
/bin/echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
/bin/echo "Content-Type: text/html"
# /bin/echo "Content-Location: $WAN/CGI/$APP-$API.cgi?$QUERY_STRING"
/bin/echo ""

cat "$OUTPUT"

done:

/bin/echo `date` "$0 $$ -- FINISH" >>! $TMP/LOG
