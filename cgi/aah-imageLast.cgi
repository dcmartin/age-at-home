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
setenv TTL 5
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

if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- START ($db $ext)" >>! $TMP/LOG

# find image
set out = "/tmp/$0:t.$db-$ext.$DATE.jpg"

if (! -s "$out") then
  set old = ( `/bin/echo "$out:r:r".*.jpg` )

  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- ASYNC REQUEST ($db $ext)" >>! $TMP/LOG

  ./aah-fetch-imageLast.bash "$db" "$ext" "$out"

  if ($?old) then
    if ($#old) then
      @ nold = $#old
      set out = "$old[$nold]"
      @ nold--
      if ($nold) then
        /bin/rm -f "$old[1-$nold]"
      endif
    endif
  endif
endif

if (-s "$out") then
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- CACHE HIT ($out)" >>! $TMP/LOG
  /bin/echo "Last-Modified:" `/bin/date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
  /bin/echo "Access-Control-Allow-Origin: *"
  /bin/echo "Content-Type: image/jpeg"
  /bin/echo "Last-Modified:" `/bin/date -r $SECONDS '+%a, %d %b %Y %H:%M:%S %Z'`
  /bin/echo ""
  /bin/dd if="$out"
  goto done
endif
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- FAIL ($db $ext)" >>! $TMP/LOG
  set output = '{"error":"not found","db":"'"$db"'","ext":"'"$ext"'"}'
  goto output
endif

#
# output
#

output:

if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- FAIL ($output)" >>! $TMP/LOG

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

if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- FINISH ($DATE)" >>! $TMP/LOG
