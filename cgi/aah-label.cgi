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

# output set
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

# check OUTPUT exists
if (-e "$OUTPUT") then
    echo `date` "$0 $$ -- returning existing ($OUTPUT)" >>! $TMP/LOG
    goto output
else
    set old = ( `find "$TMP/" -name "$APP-$API-$QUERY_STRING.*.json" -print | sort -t . -k 2,2 -n -r` )
    if ($#old > 0) then
        rm -f $old
    endif
    echo "<HTML><HEAD></HEAD><BODY>$0 $QUERY_STRING ($$)</BODY></HTML>" >>! "$OUTPUT"
endif

output:

#
# prepare for output
#
echo "Content-Type: text/html; charset=utf-8"
set age = `echo "$SECONDS - $DATE" | bc`
set refresh = `echo "$TTL - $age" | bc`
echo "Age: $age"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo "Location: $HTTP_REFERER"
echo ""
cat "$OUTPUT"

done:

echo `date` "$0 $$ -- FINISH ($QUERY_STRING)" >>! $TMP/LOG
