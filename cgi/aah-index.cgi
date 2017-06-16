#!/bin/csh -fb
setenv APP "aah"
setenv API "index"
setenv WWW "www.dcmartin.com"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

# don't update statistics more than once per (in seconds)
set TTL = 1800
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`
set AGE = `echo "$SECONDS - $DATE" | bc`

#set DEBUG = true

setenv COMPOSITE "__COMPOSITE__"


if ($?QUERY_STRING) then
    echo `date` "$0 $$ -- START ($QUERY_STRING)" >>! $TMP/LOG
    set noglob
    set DB = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ("$DB" == "$QUERY_STRING") set DB = rough-fog
    set class = `echo "$QUERY_STRING" | sed 's/.*class=\([^&]*\).*/\1/'`
    if ("$class" == "$QUERY_STRING") unset class
    set id = `echo "$QUERY_STRING" | sed 's/.*id=\([^&]*\).*/\1/'`
    if ("$id" == "$QUERY_STRING") unset id
    set ext = `echo "$QUERY_STRING" | sed 's/.*ext=\([^&]*\).*/\1/'`
    if ("$ext" == "$QUERY_STRING") unset ext
    set display = `echo "$QUERY_STRING" | sed 's/.*display=\([^&]*\).*/\1/'`
    if ("$display" == "$QUERY_STRING") unset display
    unset noglob
else
    echo `date` "$0 $$ -- EXIT !! NO QUERY_STRING !!" >>! $TMP/LOG
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
  set class = ( `echo "$class" | sed 's@//@/@g'` )
endif

if ($?db) then
    setenv QUERY_STRING "db=$db"
endif
if ($?ext) then
    setenv QUERY_STRING "$QUERY_STRING&ext=$ext"
endif
if ($?class) then
    setenv QUERY_STRING "$QUERY_STRING&class=$class"
endif
if ($?display) then
    setenv QUERY_STRING "$QUERY_STRING&display=$display"
endif
if ($?id) then
    setenv QUERY_STRING "$QUERY_STRING&id=$id"
endif

if ($?DEBUG) echo `date` "$0 $$ -- query string ($QUERY_STRING)" >>! $TMP/LOG

# check which image (ext = { frame, sample } -> type = { jpg, jpeg } )
if ($?ext) then
    set ext = $ext:h
    if ($ext == "frame") set type = "jpg"
    if ($ext == "sample") set type = "jpeg"
else
    set ext = "frame"
    set type = "jpg"
endif

#
# handle images (files)
#
if ($?id) then
  set fid = "$id:r"
  if ("$fid" == "$id") then
    if ($?DEBUG) echo `date` "$0 $$ -- got directory $id ($class)" >>! $TMP/LOG
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

    if ($?DEBUG) echo `date` "$0 $$ -- BASE ($base) ID ($id) images ($#images)" >>! $TMP/LOG

    if ($#images == 0) then
      echo "Status: 404 Not Found"
      goto done
    endif

    echo "Access-Control-Allow-Origin: *"
    echo "Age: $AGE"
    echo "Cache-Control: max-age=$TTL"
    echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
    echo "Content-Location: $WWW/CGI/$APP-$API.cgi?$QUERY_STRING"

    #  singleton image
    if ($#images == 1 && $ext != "dir") then
	echo "Content-Type: image/jpeg"
	echo ""
	if ($?DEBUG) echo `date` "$0 $$ -- SINGLETON ($id)" >>! $TMP/LOG
	dd if="$images"
    else if ($#images && $ext == "dir") then
	if ($?DEBUG) echo `date` "$0 $$ -- COMPOSITE IMAGES ($#images) " >>! $TMP/LOG
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
	  xc:none -gravity center -stroke black -strokewidth 2 -annotate 0 "$id" -background none -shadow "100x3+0+0" +repage -stroke none -fill white -annotate 0 \
	  "$id" \
	  "$blend:r.$$.$blend:e" \
	  +swap -gravity south -geometry +0-3 -composite \
	  "$blend"
	/bin/rm -f "$blend:r.$$.$blend:e"
	if (! -s "$blend") then
	  if ($?DEBUG) echo `date` "$0 $$ -- creation of composite image failed ($images)" >>! $TMP/LOG
	  set failure = "composite failure"
          goto done
	endif
      endif
      echo "Content-Type: image/jpeg"
      echo ""
      if ($?DEBUG) echo `date` "$0 $$ -- SINGLETON ($id)" >>! $TMP/LOG
      dd if="$blend"
    else
	#  trick is to use id to pass regexp base
	echo "Content-Type: application/zip"
	echo ""
	if ($?DEBUG) echo `date` "$0 $$ -- MULTIPLE IMAGES ZIP ($#images)" >>! $TMP/LOG
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
  set base = "$TMP/label/$db/$class"
  # find all images in the $class directory
  set images = ( `find "$base" -name "*.$type" -type f -print | egrep -v "$COMPOSITE" | sed "s@$base"".*/\(.*\)\.$type@\1@"` )
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
  set base = "$TMP/label/$db"
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


set MIXPANELJS = "http://$WWW/CGI/script/mixpanel-aah.js"

if ($?class) then
    if ($?DEBUG) echo `date` "$0 $$ -- CLASS ($class)" >>! $TMP/LOG
    # should make a path name
    set dir = "$db/$class"
    if ($?DEBUG) echo `date` "$0 $$ -- DIR ($dir)" >>! $TMP/LOG
    echo '<html><head><title>Index of '"$dir"'</title></head>' >! "$OUTPUT"
    echo '<script type="text/javascript" src="'$MIXPANELJS'"></script><script>mixpanel.track('"'"$APP-$API"'"',{"db":"'$db'","dir":"'$dir'"});</script>' >> "$OUTPUT"
    echo '<body bgcolor="white"><h1>Index of '"$dir"'</h1><hr>' >>! "$OUTPUT"
    if ($?display == 0) then
      echo '<pre>' >>! "$OUTPUT"
      set parent = "$class:h:h"
      if ($parent != "$class") then
	echo '<a href="http://'"$WWW/CGI/$APP-$API.cgi?db=$db&ext=$ext&class=$parent"'">../</a>' >>! "$OUTPUT"
      else
	echo '<a href="http://'"$WWW/CGI/$APP-$API.cgi?db=$db&ext=$ext"'">../</a>' >>! "$OUTPUT"
      endif
    else
      echo '<pre>' >>! "$OUTPUT"
      set parent = "$class:h:h"
      if ($parent != "$class") then
	echo '<a href="http://'"$WWW/CGI/$APP-$API.cgi?db=$db&ext=$ext&display=icon&class=$parent"'">../</a>' >>! "$OUTPUT"
      else
	echo '<a href="http://'"$WWW/CGI/$APP-$API.cgi?db=$db&ext=$ext&display=icon"'">../</a>' >>! "$OUTPUT"
      endif
      echo '</pre>' >>! "$OUTPUT"
    endif
    if ($?classes) then
      if ($?DEBUG) echo `date` "$0 $$ -- SUBCLASSES ($classes)" >>! $TMP/LOG
      foreach i ( $classes )
	if ($?display) then
	  echo '<a href="http://'"$WWW/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&display=icon&class='"$class/$i"'">' >>! "$OUTPUT"
	  echo '<img width="24%" alt="'"$i"'" src="http://'"$WWW/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&class='"$class"'&id='"$i"'">' >>! "$OUTPUT"
	  echo '</a>' >>! "$OUTPUT"
	else 
	  set name = '<a href="http://www.dcmartin.com/CGI/aah-index.cgi?db='"$db"'&ext='"$ext"'&class='"$class/$i"'">'"$i"'/</a>'
	  set ctime = `date '+%d-%h-%Y %H:%M'`
	  set fsize = `du -sk "$TMP/label/$db/$class/$i" | awk '{ print $1 }'`
	  echo "$name		$ctime		$fsize" >>! "$OUTPUT"
	endif
      end
    endif

    if ($?display) echo '<br>' >>! "$OUTPUT"

    if ($?DEBUG) echo `date` "$0 $$ -- HANDLING IMAGES ($images)" >>! $TMP/LOG
    foreach i ( $images )
      if ($?display) then
        if (! $?classes) then
	  echo '<a href="http://'"$WWW/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&class='"$class"'&id='"$i"'.'"$type"'">' >>! "$OUTPUT"
	  echo '<img width="16%" alt="'"$i.$type"'" src="http://'"$WWW/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&class='"$class"'&id='"$i"'.'"$type"'">' >>! "$OUTPUT"
	  echo '</a>' >>! "$OUTPUT"
	endif
      else
	set file = '<a href="http://'"$WWW/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&class='"$class"'&id='"$i"'.'"$type"'">'"$i.$type"'</a>' 
	set ctime = `date '+%d-%h-%Y %H:%M'`
	set fsize = `find "$TMP/label/$db/$class" -name "$i.$type" -print | xargs ls -l | awk '{ print $5 }'`
	echo "$file		$ctime		$fsize" >>! "$OUTPUT"
      endif
    end
    if ($?display == 0) then
      echo '</pre>' >>! "$OUTPUT"
    endif
    echo '<hr></body></html>' >>! "$OUTPUT"
    if ($?DEBUG) echo `date` "$0 $$ -- DONE" >>! $TMP/LOG
else if ($?classes) then
  if ($?DEBUG) echo `date` "$0 $$ -- TOP-LEVEL ($classes)" >>! $TMP/LOG
    # should be a directory listing of directories
    set dir = "$db"
    echo '<html><head><title>Index of '"$dir"'/</title></head>' >! "$OUTPUT"
    echo '<script type="text/javascript" src="'$MIXPANELJS'"></script><script>mixpanel.track('"'"$APP-$API"'"',{"db":"'$db'"});</script>' >> "$OUTPUT"
    echo '<body bgcolor="white"><h1>Index of '"$dir"'/</h1><hr>' >>! "$OUTPUT"
    echo '<pre>' >>! "$OUTPUT"
    echo '<a href="http://'"$WWW/CGI/$APP-$API.cgi?db=$db&ext=$ext"'/">../</a>' >>! "$OUTPUT"
    if ($?display) then
      echo '</pre>' >>! "$OUTPUT"
      # echo '<br>' >>! "$OUTPUT"
    endif
    foreach i ( $classes )
      if ($?display == 0) then
	set name = '<a href="http://www.dcmartin.com/CGI/aah-index.cgi?db='"$db"'&ext='"$ext"'&class='"$i"'/">'"$i"'/</a>' >>! "$OUTPUT"
	set ctime = `date '+%d-%h-%Y %H:%M'`
	set fsize = `du -sk "$TMP/label/$db/$i" | awk '{ print $1 }'`
	echo "$name		$ctime		$fsize" >>! "$OUTPUT"
      else
	echo '<a href="http://'"$WWW/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&display=icon&class='"$i"'">' >>! "$OUTPUT"
	echo '<img width="24%" alt="'"$i"'" src="http://'"$WWW/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&class=&id='"$i"'">' >>! "$OUTPUT"
	echo '</a>' >>! "$OUTPUT"
      endif
    end
    if ($?display == 0) then
      echo '</pre>' >>! "$OUTPUT"
    endif
    echo '<hr></body></html>' >>! "$OUTPUT"
endif

output:

echo "Access-Control-Allow-Origin: *"
echo "Age: $AGE"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo "Content-Type: text/html"
echo ""

cat "$OUTPUT"

done:

rm -f "$OUTPUT"

echo `date` "$0 $$ -- FINISH" >>! $TMP/LOG
