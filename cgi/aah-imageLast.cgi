#!/bin/csh -fb
setenv APP "aah"
setenv API "imageLast"
setenv LAN "192.168.1"
setenv WWW "$LAN".32
setenv DIGITS "$LAN".30
setenv WAN "www.dcmartin.com"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

setenv DEBUG true

# don't update statistics more than once per (in seconds)
setenv TTL 15
setenv SECONDS `/bin/date "+%s"`
setenv DATE `/bin/echo $SECONDS \/ $TTL \* $TTL | bc`

if ($?QUERY_STRING) then
    set db = `/bin/echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
    set ext = `/bin/echo "$QUERY_STRING" | sed 's/.*ext=\([^&]*\).*/\1/'`
    if ($ext == "$QUERY_STRING") unset ext
endif

if ($?db == 0) then
  /bin/echo `/bin/date` "$0 $$ -- no db" >>! $TMP/LOGk
  goto done
endif
if ($?ext == 0) then
  set ext = "full"
else if ($ext != "full" && $ext != "crop") then
  set ext = "full"
endif

if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- START ($db-$ext)" >>! $TMP/LOG

# find image
set out = "/tmp/$0:t.$db-$ext.$DATE.jpg"

if (! -s "$out") then
  /bin/rm -f "$out:r:r".*.jpg

  set url = "$WWW/CGI/$APP-images.cgi?db=$db&limit=1&ext=full"
  set time = 4

  /usr/bin/curl -s -q -f -k -m $time -L0 "$url" -o "$out.$$"
  set code = $status
  if ($code == 22 || $code == 28 || ! -s "$out.$$") then
    if ($?VERBOSE) /bin/echo `date` "$0 $$ ++ FAILURE ($url)" >>&! $TMP/LOG
    set output = '{"error":"no image","url":"'"$url"'"}'
    goto output
  else
    /bin/mv "$out.$$" "$out"
  endif
  /bin/rm -f "$out.$$"
endif

if (-s "$out") then
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- SINGLETON ($out)" >>! $TMP/LOG
  /bin/echo "Last-Modified:" `/bin/date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
  /bin/echo "Access-Control-Allow-Origin: *"
  /bin/echo "Content-Type: image/jpeg"
  /bin/echo "Last-Modified:" `/bin/date -r $SECONDS '+%a, %d %b %Y %H:%M:%S %Z'`
  /bin/echo ""
  /bin/dd if="$out"
  goto done
endif
  set output = '{"error":"not found","db":"'"$db"'"}'
  goto output
endif

#
# output
#

output:

/bin/echo "Content-Type: application/json; charset=utf-8"
/bin/echo "Access-Control-Allow-Origin: *"
/bin/echo "Cache-Control: no-cache"
/bin/echo ""
if ($?output) then
   /bin/echo "$output"
else
   /bin/echo '{ "error": "not found" }'
endif

# done

done:

if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- FINISH ($db-$ext)" >>! $TMP/LOG
