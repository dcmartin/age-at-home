#!/bin/csh -fb
setenv APP "aah"
setenv API "resinDevice"
setenv WWW "www.dcmartin.com"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

# don't update more than once per (in seconds)
set TTL = `echo  "12 * 60 * 60" | bc`
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo `date` "$0 $$ -- START ($DATE)" >>! "$TMP/LOG"

set JSON = "$TMP/$APP-$API.$DATE.json"

if (! -e "$JSON") then
  set url = ~$USER/.resin_auth
  if (-e "$url") then
    setenv RESIN_AUTH_TOKEN `cat "$url"`
  else
    echo `date` "$0 $$ -- NO RESIN_AUTH_TOKEN ($url)" >>! "$TMP/LOG"
    set failure = "RESIN_AUTH_TOKEN undefined"
    goto output
  endif

  if ($?RESIN_AUTH_TOKEN) then
    set old = ( `echo "$JSON:r:r".*` )
    if ($?old) then
       rm -f $old
    endif
    set url = "https://api.resin.io/v1/device" 
    # get RESIN device information
    /usr/bin/curl -s -q -f -L \
      "$url" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $RESIN_AUTH_TOKEN" -o "$JSON.$$"
    if ($status == 22 || ! -s "$JSON.$$") then
      echo `date` "$0 $$ -- RESIN API FAILURE ($url)" >>! "$TMP/LOG"
      rm -f "$JSON.$$"
      goto done
    else
      set dids = ( `/usr/local/bin/jq '.d[].id' "$JSON.$$"` )

      rm -f "$JSON"
      foreach did ( $dids )
	set url = 'https://api.resin.io/v1/device_environment_variable?$filter=device%20eq%20'"$did"

	/usr/bin/curl -s -q -f -L "$url" \
	  -H "Content-Type: application/json" \
	  -H "Authorization: Bearer $RESIN_AUTH_TOKEN" \
	  -o "$JSON.$$.$did.json"
	if ($status != 22 && -s "$JSON.$$.$did.json") then
	  set location = `/usr/local/bin/jq -r '.d[]|select(."env_var_name" == "AAH_LOCATION").value' "$JSON.$$.$did.json"`
	  if ($location == "") set location = "UNKNOWN"
	else
          set location = "UNKNOWN"
	endif
	rm -f "$JSON.$$.$did.json"
	/usr/local/bin/jq -c '.d[]|select(.id=='"$did"')|{"app_id":.application.__id,"id":.id,"name":.name,"is_online":.is_online,"ip_address":.ip_address,"lastseen":.last_seen_time,"location":"'"$location"'"}' "$JSON.$$" >>! "$JSON"
      end
    endif
    rm -f "$JSON.$$"
    unset url
  else
    echo `date` "$0 $$ -- NO DEFINED RESIN_AUTH_TOKEN" >>! "$TMP/LOG"
    set failure = "RESIN_AUTH_TOKEN undefined"
  endif
endif

output:

#
# prepare for output
#
echo "Content-Type: application/json; charset=utf-8"
echo "Access-Control-Allow-Origin: *"
if (-s "$JSON") then
    set AGE = `echo "$SECONDS - $DATE" | bc`
    echo "Age: $AGE"
    echo "Cache-Control: max-age=$TTL"
    echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
    echo ""
    /usr/local/bin/jq -c '.' "$JSON"
else
    echo "Age: 0"
    echo "Cache-Control: max-age=0"
    echo "Last-Modified:" `date -r $SECONDS '+%a, %d %b %Y %H:%M:%S %Z'`
    echo ""
    if ($?failure == 0) set failure = "UNKNOWN"
    echo '{ "error": "'"$failure"'" }'
endif

done:

echo `date` "$0 $$ -- FINISH ($DATE) - status = $?failure" >>! "$TMP/LOG"
