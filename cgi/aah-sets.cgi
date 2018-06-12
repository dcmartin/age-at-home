#!/bin/tcsh -b
setenv APP "aah"
setenv API "sets"

# setenv DEBUG true
# setenv VERBOSE true

# environment
if ($?LAN == 0) setenv LAN "192.168.1"
if ($?DIGITS == 0) setenv DIGITS "$LAN".30
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
set TTL = 360
set SECONDS = `date "+%s"`
set DATE = `/bin/echo $SECONDS \/ $TTL \* $TTL | bc`

setenv DEBUG true

if ($?QUERY_STRING) then
    set DB = `/bin/echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($DB == "$QUERY_STRING") unset DB
endif
if ($?DB == 0) set DB = rough-fog
setenv QUERY_STRING "db=$DB"

/bin/echo `date` "$0 $$ -- START ($QUERY_STRING)" >>&! $LOGTO

#
# get OUTPUT
#

set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
set INPROGRESS = ( `/bin/echo "$OUTPUT".*` )
if ($#INPROGRESS && ! -s "$OUTPUT") then
  set pid = "$INPROGRESS:e"
  set pid = `ps axw | egrep "$pid" | egrep "$API" | awk '{ print $1 }'` )
  if ($#pid) then
    set old = "$TMP/$APP-$API-$QUERY_STRING".*.json"
    if ($#old) then
      set OUTPUT = "$old[$#old]"
      @ nold = $#old - 1
      if ($nold) then
        rm -f "$old[1-$nold]"
      endif
      goto output
  endif
else if (-s "$OUTPUT) then
   goto output
endif

# indicate were running
touch "$OUTPUT".$$

set output = '{"source":"'"$DB"'","date":'"$DATE"',"classes":'
if (! -d "$AAHDIR/label/$DB") then
  set output = "$output"'null}'
  goto output
endif
set classes = ( `find "$AAHDIR/label/$DB" -name "[^\.]*" -type d -print | sed "s@$AAHDIR/label/$DB@@" | sed "s@/@@"` )
if ($#classes) then
  set output = "$output"'['
  foreach class ( $classes )
    if ($?comma) set output = "$output"','
    set output = "$output"'{"class":"'"$class"'"'
    set images = ( `find "$AAHDIR/label/$DB/$class" -name "[^\.]*.jpg" -type f -print | sed "s@$AAHDIR/label/$DB/$class/\(.*\)\.jpg@"'"\1"@'` )
    set output = "$output"',"count":'$#images',"images":['
    set images = `/bin/echo "$images" | sed 's/ /,/g'`
    set output = "$output""$images"']}'
    set comma= true
 end
endif
/bin/echo "$output"']}' >! "$OUTPUT".$$
jq -c '.' "$OUTPUT".$$ >! "$OUTPUT"
rm "$OUTPUT".$$

output:

if (-s "$OUTPUT") then
  /bin/echo "Content-Type: application/json; charset=utf-8"
  /bin/echo "Access-Control-Allow-Origin: *"
  set AGE = `/bin/echo "$SECONDS - $DATE" | bc`
  /bin/echo "Age: $AGE"
  /bin/echo "Cache-Control: max-age=$TTL"
  /bin/echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
  /bin/echo ""
  jq '.' "$OUTPUT"
else
  /bin/echo '{ "error":"not found" }'
endif

done:

/bin/echo `date` "$0 $$ -- FINISH" >>&! $LOGTO
