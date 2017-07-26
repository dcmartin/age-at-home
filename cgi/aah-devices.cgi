#!/bin/csh -fb
setenv APP "aah"
setenv API "devices"
setenv LAN "192.168.1"
setenv WWW "$LAN".32
setenv DIGITS "$LAN".30
setenv WAN "www.dcmartin.com"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

setenv DEBUG true

# don't update statistics more than once per (in seconds)
setenv TTL 30
setenv SECONDS `date "+%s"`
setenv DATE `/bin/echo $SECONDS \/ $TTL \* $TTL | bc`

if ($?QUERY_STRING) then
    set db = `/bin/echo "$QUERY_STRING" | /usr/bin/sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
endif

if ($?db == 0) set db = all

# standardize QUERY_STRING (rendezvous w/ APP-make-API.csh script)
setenv QUERY_STRING "db=$db"

if ($?VERBOSE) /bin/echo `date` "$0 $$ -- START ($QUERY_STRING)" >>! $TMP/LOG

#
# get read-only access to cloudant
#
if (-e ~$USER/.cloudant_url) then
    set cc = ( `cat ~$USER/.cloudant_url` )
    if ($#cc > 0) set CU = $cc[1]
    if ($#cc > 1) set CN = $cc[2]
    if ($#cc > 2) set CP = $cc[3]
    set CU = "$CN":"$CP"@"$CU"
endif
if ($?CU == 0) then
    /bin/echo `date` "$0 $$ -- no Cloudant URL" >>! $TMP/LOG
    goto done
endif

# output target
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
# test if been-there-done-that
if (-s "$OUTPUT") goto output
rm -f "$OUTPUT:r:r".*

# find devices
if ($db == "all") then
  set devices = ( `curl "$CU/$API/_all_docs" | /usr/local/bin/jq -r '.rows[]?.id'` )
  if ($#devices == 0) then
    if ($?VERBOSE) /bin/echo `date` "$0 $$ ++ FAILURE ($url)" >>&! $TMP/LOG
    goto done
  endif
else
  set devices = ($db)
endif

if ($?VERBOSE) /bin/echo `date` "$0 $$ ++ SUCCESS -- devices ($devices)" >>&! $TMP/LOG

@ k = 0
set all = '{"date":'"$DATE"',"devices":['
foreach d ( $devices )

  # get device entry
  set url = "$API/$d"
  set out = "/tmp/$0:t.$$.json"
  curl -s -q -f -L "$CU/$url" -o "$out"
  if ($status == 22 || $status == 28 || ! -s "$out") then
    if ($?VERBOSE) /bin/echo `date` "$0 $$ ++ FAILURE ($url) ($status)" >>&! $TMP/LOG
    rm -f "$out"
    continue
  endif
  if ($db != "all" && $d == "$db") then
    /usr/local/bin/jq '{"name":.name,"date":.date,"ip_address":.ip_address,"location":.location}' "$out" >! "$OUTPUT"
    rm -f "$out"
    goto output
  else if ($db == "all") then
    set json = `/usr/local/bin/jq '{"name":.name,"date":.date}' "$out"`
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

/bin/echo "$all" | /usr/local/bin/jq -c '.' >! "$OUTPUT"

#
# output
#

output:

/bin/echo "Content-Type: application/json; charset=utf-8"
/bin/echo "Access-Control-Allow-Origin: *"

# /bin/echo "Content-Location: $WWW/CGI/$APP-$API.cgi?$QUERY_STRING"

if ($?output == 0 && -s "$OUTPUT") then
  @ age = $SECONDS - $DATE
  /bin/echo "Age: $age"
  @ refresh = $TTL - $age
  # check back if using old
  if ($refresh < 0) @ refresh = $TTL
  /bin/echo "Refresh: $refresh"
  /bin/echo "Cache-Control: max-age=$TTL"
  /bin/echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
  /bin/echo ""
  /usr/local/bin/jq -c '.' "$OUTPUT"
  if ($?VERBOSE) /bin/echo `date` "$0 $$ -- output ($OUTPUT) Age: $age Refresh: $refresh" >>! $TMP/LOG
else
  /bin/echo "Cache-Control: no-cache"
  /bin/echo "Last-Modified:" `date -r $SECONDS '+%a, %d %b %Y %H:%M:%S %Z'`
  /bin/echo ""
  if ($?output) then
    /bin/echo "$output"
  else
    /bin/echo '{ "error": "not found" }'
  endif
endif

# done

done:

if ($?VERBOSE) /bin/echo `date` "$0 $$ -- FINISH ($QUERY_STRING)" >>! $TMP/LOG
