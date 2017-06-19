#!/bin/csh -fb
setenv APP "aah"
setenv API "updates"
setenv LAN "192.168.1"
setenv WWW "$LAN".32
setenv DIGITS "$LAN".30
setenv WAN "www.dcmartin.com"
setenv TMP "/var/lib/age-at-home"

setenv DEBUG true
# setenv VERBOSE true

# don't update statistics more than once per (in seconds)
setenv TTL 60
setenv SECONDS `date "+%s"`
setenv DATE `echo $SECONDS \/ $TTL \* $TTL | bc`

#
# PROCESS ARGUMENTS
#
if ($?QUERY_STRING) then
    set db = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
endif
if ($?db == 0) set db = all # do all devices by default
setenv QUERY_STRING "db=$db"

# START
if ($?VERBOSE) echo `date` "$0 $$ -- START ($QUERY_STRING)" >>! $TMP/LOG

# get read-only access to cloudant
if (-e ~$USER/.cloudant_url) then
    set cc = ( `cat ~$USER/.cloudant_url` )
    if ($#cc > 0) set CU = $cc[1]
    if ($#cc > 1) set CN = $cc[2]
    if ($#cc > 2) set CP = $cc[3]
    set CU = "$CN":"$CP"@"$CU"
endif
if ($?CU == 0) then
    echo `date` "$0 $$ -- no Cloudant URL" >>! $TMP/LOG
    goto done
endif

# find output
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
if (-s "$OUTPUT") then
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- CACHED OUTPUT ($OUTPUT)" >>&! $TMP/LOG
  goto output
else
  rm -f "$OUTPUT:r:r".*.json
endif

# MAKE updates for each device
set devices = ( `/usr/bin/curl -s -q -s -f -L "$WWW/CGI/aah-devices.cgi" | /usr/local/bin/jq -r '.name'` )
if ($#devices == 0 || "$devices" == "null") then
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- NO DEVICES" >>&! $TMP/LOG
  set failure = '{ "error": "not found", "detail":"'"$WWW/CGI/aah-devices.cgi"'"}'
  goto done
endif
  
foreach d ( $devices )
    if ($d == "$db") set device = $d
    if ($db == "all" || $d == "$db") then
      setenv QUERY_STRING "device=$d"
      if ($?VERBOSE) echo `date` "$0 $$ ++ REQUESTING ./$APP-make-$API.bash ($QUERY_STRING)" >>! $TMP/LOG
      ./$APP-make-$API.bash # forks and runs asynchronously
    endif
end
if ($?device == 0 && $db != "all") then
  if ($?VERBOSE) echo `date` "$0 $$ -- no such device ($db)" >>! $TMP/LOG
  set failure = '{ "error": "not found", "detail":"'"$db"'"}'
  goto done
endif

# HANDLE DEVICES
@ k = 0
set all = "/tmp/$0:t.all.$$.json"
echo '{"date":'"$DATE"',"count":'$#devices',"devices":[' >! "$all"
foreach d ( $devices )
  set url = "device-$API/$d"
  set out = "/tmp/$0:t.$$.json"
  @ timer = 5
  @ try = 0
  /usr/bin/curl -m $timer -s -q -f -L "$CU/$url" -o "$out"
  if ($status == 22 || $status == 28 || ! -s "$out") then
    rm -f "$out"
    if ($status == 28) then
      if ($try < 3) then
        @ try++
        @ timer = $timer + $timer
        goto again
      else
        if ($?DEBUG) echo `date` "$0 $$ ++ DEVICE ($d) TIMEOUT" >>&! $TMP/LOG
        continue
      endif
    endif
    if ($?DEBUG) echo `date` "$0 $$ ++ DEVICE ($d) NOT FOUND" >>&! $TMP/LOG
    if ($d == $db) then
      # singleton
      echo '{"name":"'"$d"'","seqid":"","date":0,"count":0,"ids":[]}' >! "$OUTPUT"
      goto output
    else
      if ($k) echo ',' >> "$all"
      echo '{"name":"'"$d"'","date":0,"count":0}' >> "$all"
    endif
  else if ($d == $db) then
    # singleton 
    /usr/local/bin/jq -c '{"name":.name,"seqid":.seqid,"date":.date,"count":.count,"ids":.ids}' "$out" >! "$OUTPUT"
    rm -f "$out"
    goto output
  else 
    if ($k) echo ',' >> "$all"
    /usr/local/bin/jq -c '{"name":"'"$d"'","date":.date,"count":.count}' "$out" >> "$all"
    rm -f "$out"
  endif
  @ k++
end

# FINISH ALL
echo ']}' >> "$all"
/usr/local/bin/jq -c '.' "$all" >! "$OUTPUT"
rm -f "$all"

#
# output
#

output:

echo "Content-Type: application/json; charset=utf-8"
echo "Access-Control-Allow-Origin: *"

if (-s "$OUTPUT") then
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
else
    echo "Cache-Control: no-cache"
    echo "Last-Modified:" `date -r $SECONDS '+%a, %d %b %Y %H:%M:%S %Z'`
    echo ""
    if ($?failure) then
      if ($?VERBOSE) echo `date` "$0 $$ -- FAILURE ($failure)" >>! $TMP/LOG
      echo "$failure"
    else
      if ($?VERBOSE) echo `date` "$0 $$ -- FAILURE (NOT FOUND)" >>! $TMP/LOG
      echo '{ "error": "NOT FOUND" }'
    endif
endif

cleanup:
  rm -f "$OUTPUT".*

done:
  if ($?VERBOSE) echo `date` "$0 $$ -- FINISH (db=$db)" >>! $TMP/LOG
