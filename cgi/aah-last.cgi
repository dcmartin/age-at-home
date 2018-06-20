#!/bin/tcsh -b
setenv APP "aah"
setenv API "last"

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

# don't update statistics more than once per 15 minutes
set TTL = `/bin/echo "30 * 60" | bc`
set SECONDS = `date "+%s"`
set DATE = `/bin/echo $SECONDS \/ $TTL \* $TTL | bc`

if ($?QUERY_STRING) then
    set DB = `/bin/echo "$QUERY_STRING" | sed "s/.*db=\([^&]*\).*/\1/"`
    if ($#DB == 0) set DB = rough-fog
else
    set DB = rough-fog
endif
setenv QUERY_STRING "db=$DB"

/bin/echo `date` "$0:t $$ -- START ($QUERY_STRING)" >>! $LOGTO

set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
if (! -e "$OUTPUT") then
    rm -f "$TMP/$APP-$API-$QUERY_STRING".*.json
    if ($DB == "damp-cloud") then
	curl -L -s -q -o "$OUTPUT" "https://ibmcds.looker.com/looks/QYMvmW69kbcPxf3MkN43jSrgJ2NvBg9D.json"
    else
	curl -L -s -q -o "$OUTPUT" "https://ibmcds.looker.com/looks/P7QkTrRjNVpGfj4Vgz8m8Qzb7cFw8Z4X.json"
    endif
endif
if ($DB == "damp-cloud") then
    set DATETIME = `jq '.[]."dampcloud.alchemy_time"' $OUTPUT`
else
    set DATETIME = `jq '.[]."roughfog.alchemy_time"' $OUTPUT`
endif

output:

/bin/echo "Content-Type: application/json; charset=utf-8"
/bin/echo "Access-Control-Allow-Origin: *"
set AGE = `/bin/echo "$SECONDS - $DATE" | bc`
/bin/echo "Age: $AGE"
/bin/echo "Cache-Control: max-age=$TTL"
/bin/echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
/bin/echo ""
/bin/echo '{"device":"'$DB'", "datetime":'$DATETIME' }'

done:

/bin/echo `date` "$0:t $$ -- FINISH ($QUERY_STRING)" >>! $LOGTO
