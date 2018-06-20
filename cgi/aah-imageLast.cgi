#!/bin/tcsh -b
setenv APP "aah"
setenv API "imageLast"

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

# don't update statistics more than once per (in seconds)
setenv TTL 60
setenv SECONDS `/bin/date "+%s"`
setenv DATE `/bin/echo $SECONDS \/ $TTL \* $TTL | bc`

if ($?QUERY_STRING) then
    set db = `/bin/echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
    set ext = `/bin/echo "$QUERY_STRING" | sed 's/.*ext=\([^&]*\).*/\1/'`
    if ($ext == "$QUERY_STRING") unset ext
endif

if ($?db == 0) then
  /bin/echo `/bin/date` "$0:t $$ -- no db" >>! $LOGTOk
  goto done
endif
if ($?ext == 0) then
  set ext = "full"
else if ($ext != "full" && $ext != "crop") then
  set ext = "full"
endif

if ($?VERBOSE) /bin/echo `/bin/date` "$0:t $$ -- START ($db $ext)" >>! $LOGTO

# find image
set out = "/tmp/$0:t.$db-$ext.$DATE.jpg"

if (! -s "$out") then
  set old = ( `/bin/echo "$out:r:r".*.jpg` )

  if ($?DEBUG) /bin/echo `/bin/date` "$0:t $$ -- ASYNC REQUEST ($db $ext)" >>! $LOGTO

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
  if ($?DEBUG) /bin/echo `/bin/date` "$0:t $$ -- CACHE HIT ($out)" >>! $LOGTO
  /bin/echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
  /bin/echo "Access-Control-Allow-Origin: *"
  /bin/echo "Content-Type: image/jpeg"
  /bin/echo ""
  /bin/dd if="$out"
  goto done
endif
  if ($?DEBUG) /bin/echo `/bin/date` "$0:t $$ -- FAIL ($db $ext)" >>! $LOGTO
  set output = '{"error":"not found","db":"'"$db"'","ext":"'"$ext"'"}'
  goto output
endif

#
# output
#

output:

if ($?DEBUG) /bin/echo `/bin/date` "$0:t $$ -- FAIL ($output)" >>! $LOGTO

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

if ($?VERBOSE) /bin/echo `/bin/date` "$0:t $$ -- FINISH ($DATE)" >>! $LOGTO
