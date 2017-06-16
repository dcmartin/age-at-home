#!/bin/csh -fb
setenv APP "aah"
setenv API "review"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

setenv DEBUG true

# don't update statistics more than once per (in seconds)
setenv TTL 1800
setenv SECONDS `date "+%s"`
setenv DATE `echo $SECONDS \/ $TTL \* $TTL | bc`

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($DB == "$QUERY_STRING") unset DB
endif

if ($?DB == 0) set DB = rough-fog

setenv QUERY_STRING "db=$DB"

echo `date` "$0 $$ -- START ($QUERY_STRING)" >>! $TMP/LOG

# initiate new output
if ($?DEBUG) echo `date` "$0 $$ ++ REQUESTING ./$APP-make-$API.bash" >>! $TMP/LOG
./$APP-make-$API.bash

if (-e ~$USER/.cloudant_url) then
    set cc = ( `cat ~$USER/.cloudant_url` )
    if ($#cc > 0) set CU = $cc[1]
endif
if ($?CU == 0) then
    if ($?DEBUG) echo `date` "$0 $$ -- no Cloudant URL" >>! $TMP/LOG
    goto done
endif

#
# find output
#
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
# check OUTPUT exists
if (-s "$OUTPUT") then
    set seqid = `/usr/local/bin/jq -f ".seqid' "$OUTPUT"`
    if ($seqid == "null" || $seqid == 0) then
      if ($?DEBUG) echo `date` "$0 $$ ++ bad $OUTPUT" >>! $TMP/LOG
      rm -f "$OUTPUT"
    endif
endif

if (! -s "$OUTPUT") then
    # look for old output
    set old = ( `echo "$TMP/$APP-$API-$QUERY_STRING".*.json` )
    if ($?old) then
      @ nold = $#old
      if ($nold) then
	set oldest = $old[$nold]
	@ nold--
	if ($nold) rm -f $old[1-$nold]
      endif
    endif
    if ($?oldest) then
	if ($?DEBUG) echo `date` "$0 $$ -- using old output ($oldest)" >>! $TMP/LOG
	set OUTPUT = "$oldest"
	set DATE = "$oldest:r:e"
    endif
endif

if (-s "$OUTPUT") then
    echo "Content-Type: application/json; charset=utf-8"
    echo "Access-Control-Allow-Origin: *"
    @ age = $SECONDS - $DATE
    echo "Age: $age"
    @ refresh = $TTL - $age
    # check back if using old
    if ($refresh < 0) @ refresh = $TTL
    echo "Refresh: $refresh"
    echo "Cache-Control: max-age=$TTL"
    echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
    echo ""
    /usr/local/bin/jq -c '.' "$OUTPUT"
    if ($?DEBUG) echo `date` "$0 $$ -- output ($OUTPUT) Age: $age Refresh: $refresh" >>! $TMP/LOG
else
    set URL = "https://$CU/$DB-$API/all"
    if ($?DEBUG) echo `date` "$0 $$ -- returning redirect ($URL)" >>! $TMP/LOG
    set age = `echo "$SECONDS - $DATE" | bc`
    echo "Age: $age"
    set refresh = `echo "$TTL - $age" | bc`
    if ($refresh < 0) set refresh = 0
    echo "Refresh: $refresh"
    echo "Cache-Control: max-age=$TTL"
    echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
    echo "Status: 302 Found"
    echo "Location: $URL"
    echo ""
endif

# done

done:

echo `date` "$0 $$ -- FINISH ($QUERY_STRING)" >>! $TMP/LOG
