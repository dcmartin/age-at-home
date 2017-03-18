#!/bin/csh -fb
setenv APP "aah"
setenv API "resinDevice"
setenv WWW "www.dcmartin.com"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

# don't update more than once per (in seconds)
set TTL = 60
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo `date` "$0 $$ -- START ($DATE)" >>! "$TMP/LOG"

if ($?QUERY_STRING) then
  if ($#QUERY_STRING) then
    set JSON = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
  else
    set JSON = "$TMP/$APP-$API.$DATE.json"
  endif
endif

setenv RESIN_AUTH_TOKEN `cat ~$USER/.resin_auth`

if (! -e "$JSON") then
    rm -f "$JSON*"

    /usr/bin/curl -s -q -f -L \
      "https://api.resin.io/v1/device" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $RESIN_AUTH_TOKEN" > "$JSON.$$"

    /usr/local/bin/jq '.d[]|{"app_id":.application.__id,"id":.id,"name":.name,"is_online":.is_online,"ip_address":.ip_address,"lastseen":.last_seen_time}' "$JSON.$$" >! "$JSON"
    rm -f "$JSON.$$"
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

/usr/local/bin/jq -c '.' "$JSON"

echo `date` "$0 $$ -- FINISH ($DATE)" >>! "$TMP/LOG"
