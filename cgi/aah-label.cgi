#!/bin/csh -fb
setenv APP "aah"
setenv API "label"
setenv WWW "www.dcmartin.com"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

# don't update statistics more than once per (in seconds)
set TTL = 15
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo `date` "$0 $$ -- START ($QUERY_STRING) from $HTTP_REFERER" >>! $TMP/LOG

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($DB == "$QUERY_STRING") unset DB
    set id = `echo "$QUERY_STRING" | sed 's/.*id=\([^&]*\).*/\1/'`
    if ($id == "$QUERY_STRING") unset id
    set image = `echo "$QUERY_STRING" | sed 's/.*image=\([^&]*\).*/\1/'`
    if ($image == "$QUERY_STRING") unset image
    set class = `echo "$QUERY_STRING" | sed 's/.*class=\([^&]*\).*/\1/'`
    if ($class == "$QUERY_STRING") unset class
endif

if ($?DB && $?id && $?class && $?image) then
    set jpg = "$TMP/$DB/$id/$image"
    set link = "$TMP/$DB/$class/$image"

    if (-s "$jpg") then
	if (-e "$link") then
	    echo `date` "$0 $$ -- link exists ($link)" `ls -al "$link"` >>! $TMP/LOG
	    set OUTPUT = '{"result":"fail-exists","image":"'"$id/$image"'","link":"'"$class/$image"'"}'
	else
	    echo `date` "$0 $$ -- linking $jpg -> $link" >>! $TMP/LOG
	    ln -s $jpg $link >>&! $TMP/LOG
	    if (-e "$link") then
		echo `date` "$0 $$ -- link succeeded ($link)" `ls -al "$link"` >>! $TMP/LOG
		set OUTPUT = '{"result":"success","image":"'"$id/$image"'","link":"'"$class/$image"'"}'
	    else
		echo `date` "$0 $$ -- link failed ($link)" >>! $TMP/LOG
		set OUTPUT = '{"result":"fail-link","image":"'"$id/$image"'","link":"'"$class/$image"'"}'
	    endif
	endif
    else
	echo `date` "$0 $$ -- image file invalid ($jpg)" >>! $TMP/LOG
	set OUTPUT = '{"result":"fail-invalid","image":"'"$id/$image"'","link":"'"$class/$image"'"}'
    endif
else
    echo `date` "$0 $$ -- insufficient arguments" >>! $TMP/LOG
    set OUTPUT = '{"result":"badargs"}'
endif

output:

#
# prepare for output
#
echo "Content-Type: application/json; charset=utf-8"
set age = `echo "$SECONDS - $DATE" | bc`
set refresh = `echo "$TTL - $age" | bc`
echo "Age: $age"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo "Location: $HTTP_REFERER"
echo ""
echo "$OUTPUT"

done:

echo `date` "$0 $$ -- FINISH" >>! $TMP/LOG
