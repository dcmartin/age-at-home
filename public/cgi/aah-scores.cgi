#!/bin/csh -fb
setenv APP "aah"
setenv API "scores"
setenv WWW "http://www.dcmartin.com/CGI/"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/tmp"
# don't update statistics more than once per 12 hours
set TTL = `echo "12 * 60 * 60" | bc`
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo ">>> $APP-$API ($0 $$)" `date` >>! $TMP/LOG

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed "s/.*db=\([^&]*\).*/\1/"` 
    set class = `echo "$QUERY_STRING" | sed "s/.*id=\([^&]*\)/\1/"`
endif
if ($#DB == 0) set DB = rough-fog
if ($#class == 0) set class = all
setenv QUERY_STRING "db=$DB&id=$class"

set JSON = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

if (-e "$JSON") then
    echo "$APP-$API ($0 $$) == CURRENT $JSON $DATE" >>! $TMP/LOG
else
    echo "$APP-$API ($0 $$) ++ CALLING ./$APP-make-$API.bash QUERY_STRING=$QUERY_STRING" >>! $TMP/LOG
    ./$APP-make-$API.bash
    # find old results
    set OLD_JSON = ( `ls -1t "$TMP/$APP-$API-$QUERY_STRING".*.json` )
    if ($#OLD_JSON > 0) then
        echo "$APP-$API ($0 $$) == OLD $JSON ($OLD_JSON)" >>! $TMP/LOG
        set JSON = "$OLD_JSON[1]"
        if ($#OLD_JSON > 1) then
            echo "$APP-$API ($0 $$) -- DELETING $OLD_JSON[2-]" >>! $TMP/LOG
            /bin/rm -f "$OLD_JSON[2-]"
        endif
    else
        set JSON = ()
    endif
endif

if ($#JSON == 0) then
    echo "$APP-$API ($0 $$) ** NONE" >>! $TMP/LOG
endif

#
# prepare for output
#
echo "Content-Type: application/json; charset=utf-8"
echo "Access-Control-Allow-Origin: *"
set AGE = `echo "$SECONDS - $DATE" | bc`
echo "Age: $AGE"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo ""

cat "$JSON"
