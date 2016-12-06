#!/bin/csh -fb
setenv DEBUG true
setenv APP "aah"
setenv API "example"
setenv WWW "www.dcmartin.com"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

# don't update statistics more than once per (in seconds)
set TTL = 360
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($DB == "$QUERY_STRING") unset DB
    set class = `echo "$QUERY_STRING" | sed 's/.*class=\([^&]*\).*/\1/'`
    if ($class == "$QUERY_STRING") unset class
    set id = `echo "$QUERY_STRING" | sed 's/.*id=\([^&]*\).*/\1/'`
    if ($id == "$QUERY_STRING") unset id
	     
endif
if ($?DB == 0) set DB = rough-fog
if ($?class == 0) set class = ""
if ($?id == 0) set id = "*"
setenv QUERY_STRING "db=$DB"

echo `date` "$0 $$ -- START ($QUERY_STRING)" >>! $TMP/LOG

#
# get OUTPUT
#

set image = ( `find "$TMP/label/$DB/$class" -name "$id.jpg" -type f -print` )

output:

echo "Access-Control-Allow-Origin: *"
set AGE = `echo "$SECONDS - $DATE" | bc`
echo "Age: $AGE"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`

if ($#image == 1) then
    echo "Content-Type: image/jpeg"
    echo ""
    dd if="$image[1]"
else if ($#image > 1) then
    echo "Content-Type: application/zip"
    echo ""
    zip - $image | dd of=/dev/stdout
endif

done:

echo `date` "$0 $$ -- FINISH" >>! $TMP/LOG
