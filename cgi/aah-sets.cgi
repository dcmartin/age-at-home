#!/bin/csh -fb
setenv APP "aah"
setenv API "sets"
setenv LAN "192.168.1"
setenv WWW "$LAN".32
setenv DIGITS "$LAN".30
setenv WAN "www.dcmartin.com"
setenv TMP "/var/lib/age-at-home"

# don't update statistics more than once per (in seconds)
set TTL = 360
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

setenv DEBUG true

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($DB == "$QUERY_STRING") unset DB
endif
if ($?DB == 0) set DB = rough-fog
setenv QUERY_STRING "db=$DB"

echo `date` "$0 $$ -- START ($QUERY_STRING)" >>! $TMP/LOG

#
# get OUTPUT
#

set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
set INPROGRESS = ( `echo "$OUTPUT".*` )
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
if (! -d "$TMP/label/$DB") then
  set output = "$output"'null}'
  goto output
endif
set classes = ( `find "$TMP/label/$DB" -name "[^\.]*" -type d -print | sed "s@$TMP/label/$DB@@" | sed "s@/@@"` )
if ($#classes) then
  set output = "$output"'['
  foreach class ( $classes )
    if ($?comma) set output = "$output"','
    set output = "$output"'{"class":"'"$class"'"'
    set images = ( `find "$TMP/label/$DB/$class" -name "[^\.]*.jpg" -type f -print | sed "s@$TMP/label/$DB/$class/\(.*\)\.jpg@"'"\1"@'` )
    set output = "$output"',"count":'$#images',"images":['
    set images = `echo "$images" | sed 's/ /,/g'`
    set output = "$output""$images"']}'
    set comma= true
 end
endif
echo "$output"']}' >! "$OUTPUT".$$
/usr/local/bin/jq -c '.' "$OUTPUT".$$ >! "$OUTPUT"
rm "$OUTPUT".$$

output:

if (-s "$OUTPUT") then
  echo "Content-Type: application/json; charset=utf-8"
  echo "Access-Control-Allow-Origin: *"
  set AGE = `echo "$SECONDS - $DATE" | bc`
  echo "Age: $AGE"
  echo "Cache-Control: max-age=$TTL"
  echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
  echo ""
  /usr/local/bin/jq '.' "$OUTPUT"
else
  echo '{ "error":"not found" }'
endif

done:

echo `date` "$0 $$ -- FINISH" >>! $TMP/LOG
