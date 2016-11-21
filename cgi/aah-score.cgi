#!/bin/csh -fb
setenv APP "aah"
setenv API "score"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"
# don't update statistics more than once per seconds
set TTL = 30
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

if ($?QUERY_STRING) then
    set device = `echo "$QUERY_STRING" | sed "s/.*db=\([^&]*\).*/\1/"`
    if ($device == "$QUERY_STRING") unset device
    set model = `echo "$QUERY_STRING" | sed 's/.*cid=\([^&]*\).*/\1/'`
    if ($model == "$QUERY_STRING") unset model
    set image = `echo "$QUERY_STRING" | sed 's/.*jpg=\([^&]*\).*/\1/'`
    if ($image == "$QUERY_STRING") unset image
endif
if ($?device == 0) set device = rough-fog
if ($?model == 0) set model = any
if ($?image == 0) set image = any

if ($?device && $?model && $?image) then
    setenv QUERY_STRING "db=$DB&cid=$model&jpg=$image"
else
    echo `date` "$0 $$ ** FAIL: invalid arguments ($?device $?model $?image)" >>! $TMP/LOG
    exit
endif

echo `date` "$0 $$ -- START ($QUERY_STRING)" >>! $TMP/LOG

set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
if (! -e "$OUTPUT") then
    rm -f "$TMP/$APP-$API-$QUERY_STRING".*.json
    set models = ( `curl -s -q -L "538e7925-b7f5-478b-bf75-2f292dcf642a-bluemix.cloudant.com/rough-fog-train/_all_docs" | jq '.rows[].id' | sed 's/"//g'` )
    if ($#models > 0) then
      foreach m ( $models )
	if ($m == "$model" || $model == "any") then
	  set model = $m
	endif
      end
    else
      set model = "default"
    endif
    echo '{"device":"'$DB'", "model":"'"$model"'","jpg":"'"$image"'","classes":[' >! "$OUTPUT".$$

    echo ']}' >> "$OUTPUT.$$
    mv -f "$OUTPUT".$$ "$OUTPUT"
endif

echo "Content-Type: application/json; charset=utf-8"
echo "Access-Control-Allow-Origin: *"
set AGE = `echo "$SECONDS - $DATE" | bc`
echo "Age: $AGE"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo ""
cat "$OUTPUT"

done:

echo `date` "$0 $$ -- FINISH" >>! $TMP/LOG
