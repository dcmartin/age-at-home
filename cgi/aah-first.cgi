#!/bin/tcsh -b
setenv APP "aah"
setenv API "first"

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

/bin/echo `date` "$0 $$ -- START" >>! $LOGTO

if ($?QUERY_STRING) then
    set DB = `/bin/echo "$QUERY_STRING" | sed "s/.*db=\([^&]*\).*/\1/"`
    if ($#DB == 0) set DB = rough-fog
else
    set DB = rough-fog
endif
setenv QUERY_STRING "db=$DB"

set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
if (! -e "$OUTPUT") then
    rm -f "$TMP/$APP-$API-$QUERY_STRING".*.json
    if ($DB == "damp-cloud") then
	# new URL for "person" or "people" from Alchemy text
	curl -L -s -q -o "$OUTPUT" "https://ibmcds.looker.com/looks/y4dP4n52YGGcjpKHGjFQVXtCR56xT7kX.json?apply_formatting=true"
    else
	# NEED new URL for "person" or "people" from Alchemy text
	curl -L -s -q -o "$OUTPUT" "https://ibmcds.looker.com/looks/vNhq2H5mWFwPB5pgT3j5Rs4wGbRKHpH7.json?apply_formatting=true"
    endif
endif
if ($DB == "damp-cloud") then
    set DATETIME = `jq '.[0]."dampcloud.alchemy_time"' $OUTPUT`
else
    set DATETIME = `jq '.[0]."roughfog.alchemy_time"' $OUTPUT`
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

/bin/echo `date` "$0 $$ -- FINISH" >>! $LOGTO
