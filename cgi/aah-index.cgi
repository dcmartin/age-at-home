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

echo `date` "$0 $$ -- START ($DATE)" >>! $TMP/LOG

if ($?QUERY_STRING) then
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
endif

if ($?DB) then
  set db = "$DB:h"
else
  set DB = rough-fog
  set db = "$DB"
endif

if ($?ext) then
    set ext = $ext:h
    if ($ext == "frame") set type = "jpg"
    if ($ext == "sample") set type = "jpeg"
else
    set ext = "frame"
    set type = "jpg"
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
  set class = "$class:h"
endif
if ($?id) then
  set id = "$id:r"
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

#
# handle images (files)
#
if ($?id) then

    set base = "$TMP/label/$db/$class"
    set images = ( `find "$base" -name "$id""*.$type" -type f -print` )

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
    if ($#images == 1) then
	echo "Content-Type: image/jpeg"
	echo ""
	if ($?DEBUG) echo `date` "$0 $$ -- DD ($id) ($#images) " >>! $TMP/LOG
	dd if="$images"
    else if ($#images > 1) then
	#  trick is to use id to pass regexp base
	echo "Content-Type: application/zip"
	echo ""
	if ($?DEBUG) echo `date` "$0 $$ -- ZIP ($#images) DD ($id) count ($images) " >>! $TMP/LOG
	zip - $images | dd of=/dev/stdout
    endif

    goto done
endif

#
# build HTML
#
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.html"
set INPROGRESS = ( `echo "$OUTPUT".*` )
if ($#INPROGRESS) then
    set INPROGRESS = $INPROGRESS[$#INPROGRESS]
    set pid = "$INPROGRESS:e"
    set pid = `ps axw | egrep "pid" | egrep "$API" | awk '{ print $1 }'`
    if ($#pid) then
      if ($?DEBUG) echo `date` "$0 $$ -- IN-PROGRESS $INPROGRESS" >>! $TMP/LOG
      goto done
    endif
    rm -f "$INPROGRESS:r".*
else
  # start work
  touch "$OUTPUT.$$"
endif

#
# test hierarchy level (label/device/class); class could be a UNIX directory hierarchy, e.g. "/vehicle/car/sedan" (AFAIK :-)
#

if ($?class) then
    set base = "$TMP/label/$db/$class"
    # find all images in the $class directory
    set images = ( `find "$base" -name "*.$type" -type f -print | sed "s@$base/\(.*\)\.$type@\1@"` )
else 
    set base = "$TMP/label/$db"
    # find all directories in the $db directory (not includes those beginning with ".", e.g. ".skipped")
    set classes = ( `find "$base" -name "[^\.]*" -type d -print | sed "s@$base@@" | sed "s@/@@"` )
endif

if ($?DEBUG) echo `date` "$0 $$ -- $db $?id ($?images) $?class ($?classes)" >>! $TMP/LOG

set MIXPANELJS = "http://$WWW/CGI/script/mixpanel-aah.js"

if ($?class) then
    # should be a directory listing of images
    set dir = "$db/$class"
    echo '<html><head><title>Index of '"$dir"'</title></head>' >! "$OUTPUT.$$"
    echo '<script type="text/javascript" src="'$MIXPANELJS'"></script><script>mixpanel.track('"'"$APP-$API"'"',{"db":"'$db'","class":"'$class'"});</script>' >> "$OUTPUT.$$"
    echo '<body bgcolor="white"><h1>Index of '"$dir"'</h1><hr><pre><a href="http://'"$WWW/CGI/$APP-$API.cgi?db=$db&ext=$ext"'/">../</a>' >>! "$OUTPUT.$$"
    if ($?display) echo '</pre>' >>! "$OUTPUT.$$"
    foreach i ( $images )
      if ($?display) then
	echo '<a href="http://'"$WWW/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&class='"$class"'&id='"$i"'.'"$type"'">' >>! "$OUTPUT.$$"
	echo '<img width="16%" alt="'"$i.$type"'" src="http://'"$WWW/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&class='"$class"'&id='"$i"'.'"$type"'">' >>! "$OUTPUT.$$"
	echo '</a>' >>! "$OUTPUT.$$"
      else
	set file = '<a href="http://'"$WWW/CGI/$APP-$API"'.cgi?db='"$db"'&ext='"$ext"'&class='"$class"'&id='"$i"'.'"$type"'">'"$i.$type"'</a>' 
	set ctime = `date '+%d-%h-%Y %H:%M'`
	set fsize = `ls -l "$TMP/label/$db/$class/$i.$type" | awk '{ print $5 }'`
	echo "$file		$ctime		$fsize" >>! "$OUTPUT.$$"
      endif
    end
    if ($?display) echo '<pre>' >>! "$OUTPUT.$$"
    echo '</pre><hr></body></html>' >>! "$OUTPUT.$$"
else if ($?classes) then
    # should be a directory listing of directories
    set dir = "$db"
    echo '<html><head><title>Index of '"$dir"'/</title></head>' >! "$OUTPUT.$$"
    echo '<script type="text/javascript" src="'$MIXPANELJS'"></script><script>mixpanel.track('"'"$APP-$API"'"',{"db":"'$db'"});</script>' >> "$OUTPUT.$$"
    echo '<body bgcolor="white"><h1>Index of '"$dir"'/</h1><hr><pre><a href="http://'"$WWW/CGI/$APP-$API.cgi?db=$db&ext=$ext"'/">../</a>' >>! "$OUTPUT.$$"
    foreach i ( $classes )
      set class = '<a href="http://www.dcmartin.com/CGI/aah-index.cgi?db='"$db"'&ext='"$ext"'&class='"$i"'/">'"$i"'/</a>' >>! "$OUTPUT.$$"
      set ctime = `date '+%d-%h-%Y %H:%M'`
      set fsize = `du -sk "$TMP/label/$db/$i" | awk '{ print $1 }'`
      echo "$class		$ctime		$fsize" >>! "$OUTPUT.$$"
    end
    echo '</pre><hr></body></html>' >>! "$OUTPUT.$$"
endif

mv "$OUTPUT.$$" "$OUTPUT"

output:

echo "Access-Control-Allow-Origin: *"
echo "Age: $AGE"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo "Content-Type: text/html"
echo ""

cat "$OUTPUT"

done:

rm -f "$TMP/$APP-$API-"*.$$
echo `date` "$0 $$ -- FINISH" >>! $TMP/LOG
