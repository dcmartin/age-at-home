#!/bin/tcsh -b
setenv APP "aah"
setenv API "devices"

# setenv DEBUG true
# setenv VERBOSE true

# environment
if ($?LAN == 0) setenv LAN "192.168.1"
if ($?DIGITS == 0) setenv DIGITS "$LAN".30
if ($?TMP == 0) setenv TMP "/tmp"
if ($?AAHDIR == 0) setenv AAHDIR "/var/lib/age-at-home"
if ($?CREDENTIALS == 0) setenv CREDENTIALS /usr/local/etc
if ($?LOGTO == 0) setenv LOGTO /dev/stderr

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

# don't update statistics more than once per (in seconds)
setenv TTL 30
setenv SECONDS `date "+%s"`
setenv DATE `echo $SECONDS \/ $TTL \* $TTL | bc`

if ($?QUERY_STRING) then
    set db = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
endif

if ($?db == 0) set db = all

# standardize QUERY_STRING (rendezvous w/ APP-make-API.csh script)
setenv QUERY_STRING "db=$db"

if ($?VERBOSE) echo `date` "$0:t $$ -- START ($QUERY_STRING)" >>&! $LOGTO

##
## ACCESS CLOUDANT
##
if ($?CLOUDANT_URL) then
  set CU = $CLOUDANT_URL
else if (-s $CREDENTIALS/.cloudant_url) then
  set cc = ( `cat $CREDENTIALS/.cloudant_url` )
  if ($#cc > 0) set CU = $cc[1]
  if ($#cc > 1) set CN = $cc[2]
  if ($#cc > 2) set CP = $cc[3]
  if ($?CP && $?CN && $?CU) then
    set CU = 'https://'"$CN"':'"$CP"'@'"$CU"
  else if ($?CU) then
    set CU = "https://$CU"
  endif
else
  /bin/echo `date` "$0:t $$ -- FAILURE: no Cloudant credentials" >>&! $LOGTO
  goto done
endif

# output target
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
# test if been-there-done-that
if (-e "$OUTPUT") goto output
rm -f "$OUTPUT:r:r".*

# find devices
if ($db == "all") then
  set devices = ( `curl -s -q -L "$CU/$API/_all_docs" | jq -r '.rows[]?.id'` )
  if ($#devices == 0) then
    if ($?VERBOSE) echo `date` "$0:t $$ ++ Could not retrieve list of devices from ($url)" >>&! $LOGTO
    goto done
  endif
else
  set devices = ($db)
endif

if ($?VERBOSE) echo `date` "$0:t $$ ++ Devices in DB ($devices)" >>&! $LOGTO

@ k = 0
set all = '{"date":'"$DATE"',"devices":['

foreach d ( $devices )
  # get device entry
  set url = "$CU/$API/$d"
  set out = "$TMP/$APP-$API-$$.json"
  curl -s -q -L "$url" -o "$out"
  if (! -e "$out") then
    if ($?VERBOSE) echo `date` "$0:t $$ ++ FAILURE ($d)" `ls -al $out` >>&! $LOGTO
    rm -f "$out"
    continue
  endif
  if ($db != "all" && $d == "$db") then
    jq '{"name":.name,"date":.date,"ip_address":.ip_address,"location":.location}' "$out" >! "$OUTPUT"
    rm -f "$out"
    goto output
  else if ($db == "all") then
    set json = `jq '{"name":.name,"date":.date}' "$out"`
    rm -f "$out"
  else
    unset json
  endif
  if ($k) set all = "$all"','
  @ k++
  if ($?json) then
    set all = "$all""$json"
  endif
end
set all = "$all"']}'

echo "$all" | jq -c '.' >! "$OUTPUT"

#
# output
#

output:

echo "Content-Type: application/json; charset=utf-8"
echo "Access-Control-Allow-Origin: *"

# echo "Content-Location: $HTTP_HOST/CGI/$APP-$API.cgi?$QUERY_STRING"

if ($?output == 0 && -e "$OUTPUT") then
  @ age = $SECONDS - $DATE
  echo "Age: $age"
  @ refresh = $TTL - $age
  # check back if using old
  if ($refresh < 0) @ refresh = $TTL
  echo "Refresh: $refresh"
  echo "Cache-Control: max-age=$TTL"
  echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
  echo ""
  jq -c '.' "$OUTPUT"
  if ($?VERBOSE) echo `date` "$0:t $$ -- output ($OUTPUT) Age: $age Refresh: $refresh" >>&! $LOGTO
else
  echo "Cache-Control: no-cache"
  echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
  echo ""
  if ($?output) then
    echo "$output"
  else
    echo '{ "error": "not found" }'
  endif
endif

# done

done:

if ($?VERBOSE) echo `date` "$0:t $$ -- FINISH ($QUERY_STRING)" >>&! $LOGTO
