#!/bin/tcsh -b
setenv APP "aah"
setenv API "samples"

# debug on/off
setenv DEBUG true
setenv VERBOSE true

# environment
if ($?LAN == 0) setenv LAN "192.168.1"
if ($?DIGITS == 0) setenv DIGITS "$LAN".30
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"
if ($?CREDENTIALS == 0) setenv CREDENTIALS /usr/local/etc
if ($?LOGTO == 0) setenv LOGTO /dev/stderr

if ($?TTL == 0) set TTL = 1800
if ($?SECONDS == 0) set SECONDS = `/bin/date "+%s"`
if ($?DATE == 0) set DATE = `/bin/echo $SECONDS \/ $TTL \* $TTL | /usr/bin/bc`

setenv NOFORCE true

if ($?QUERY_STRING) then
    set db = `/bin/echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
endif

# DEFAULTS to rough-fog (kitchen) and all classes
if ($?db == 0) set db = rough-fog

# standardize QUERY_STRING
setenv QUERY_STRING "db=$db"

/bin/echo `/bin/date` "$0 $$ -- START ($QUERY_STRING)"  >>&! $LOGTO

#
# OUTPUT target
#
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

#
# check output
#

if (-s "$OUTPUT") then
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- $OUTPUT exists" >>&! $LOGTO
  goto done
endif

#
# SINGLE THREADED (by QUERY_STRING)
#
set INPROGRESS = ( `/bin/echo "$OUTPUT:r:r".*` )
if ($#INPROGRESS) then
  foreach ip ( $INPROGRESS )
    set pid = $ip:e
    set eid = `ps axw | awk '{ print $1 }' | egrep "$pid"`
    if ($pid == $eid) then
      if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- in-progress ($pid)" >>&! $LOGTO
      goto done
    endif
    rm -f $ip
  end
endif

# cleanup if interrupted
onintr cleanup
touch "$OUTPUT".$$

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
  /bin/echo `date` "$0:t $$ -- FAILURE: no Cloudant credentials" >>& $LOGTO
  goto done
endif

#
# CREATE DATABASE 
#
if ($?CU && $?db) then
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- test if db exists ($CU/$db-$API)" >>&! $LOGTO
  set DEVICE_db = `curl -s -q -f -L -X GET "$CU/$db-$API" | jq '.db_name'`
  if ( $DEVICE_db == "" || "$DEVICE_db" == "null" ) then
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- creating db $CU/$db-$API" >>&! $LOGTO
    # create db
    set DEVICE_db = `curl -s -q -f -L -X PUT "$CU/$db-$API" | jq '.ok'`
    # test for success
    if ( "$DEVICE_db" != "true" ) then
      # failure
      if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- failure creating Cloudant database ($db-$API)" >>&! $LOGTO
    else
      if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- success creating db $CU/$db-$API" >>&! $LOGTO
    endif
  endif
endif

#
# GET OLD (ALL)
#
set ALL = "$OUTPUT:r:r"-all.$$.json
set last = 0
set known = ()
curl -s -q -f -L "$CU/$db-$API/all" -o "$ALL"
if ($status != 22 && -s "$ALL") then
  set last = ( `jq -r '.date' "$ALL"` )
  if ($#last == 0 || $last == "null") then
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- NO MODIFIED DATE ($i)" >>&! $LOGTO
    set last = 0
  else
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- ALL MODIFIED LAST ($last)" >>&! $LOGTO
  endif
endif
if ($last && -s "$ALL") then
  # get known from "all" record
  set known = ( `jq -r '.classes[]?.name' "$ALL"` )
endif
if ($#known == 0) then
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- NO EXISTING CLASSES (all)" >>&! $LOGTO
  # get known through inspection of all rows
  set known = ( `curl -s -q -f -L "$CU/$db-$API/_all_docs" | jq -r '.rows[]?|select(.id!="all").id'` )
endif
if ($#known == 0 || "$known" == '[]' || "$known" == "null") then
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- DB: $db -- CANNOT FIND ANY KNOWN CLASSES OF $API" >>&! $LOGTO
    set known = ()
  endif
else
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- CANNOT RETRIEVE $db-$API/all ($ALL)" >>&! $LOGTO
  set last = 0
endif

#
# FIND CURRENT HIERARCHY
#
set dir = "$TMP/$db" 
if (! -d "$dir") then
  if ($?DEBUG) /bin/echo `date` "$0 $$ -- create directory ($dir)" >>&! $LOGTO
  mkdir -p "$dir"
  if (! -d "$dir") then
    if ($?DEBUG) /bin/echo `date` "$0 $$ -- FAILURE -- no directory ($dir)" >>&! $LOGTO
    goto done
  endif
endif

# stat directory
set stat = ( `stat -r "$dir" | awk '{ print $10 }'` )
if ($?NOFORCE == 0 || $stat > $last) then
  # search for any changes
  set classes = ( `find "$dir" -type d -print | egrep -v "/\." | sed "s@$dir@@g" | sed "s@^/@@" | sed "s@ /@ @g"` )
  if ($#classes == 0) then
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- found NO classes in $dir" >>&! $LOGTO
    goto done
  endif
else if ($?known) then
  set classes = ( $known )
else
  set classes = ( )
endif

if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- PROCESSING ($DATE, $db, $#classes ( $classes ))" >>&! $LOGTO

/bin/echo '{"date":'"$DATE"',"device":"'"$db"'","classes":[' >! "$ALL.$$"

@ k = 0
set unknown = ()
foreach i ( $classes )
  set CDIR = "$dir/$i"
  set CID = ( `/bin/echo "$i" | sed 's|/|%2F|g'` ) # URL encode "/"

  # SANITY
  if (! -d "$CDIR") then
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- NO DIRECTORY ($CDIR)" >>&! $LOGTO
    continue
  endif

  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- PROCESSING DIR: $CDIR CID: $CID ($k of $#classes)" >>&! $LOGTO

  set last = 0
  unset json
  # get json for this class
  if (-s "$ALL") then
    set json = `jq '.classes[]?|select(.name=="'"$i"'")' "$ALL"`
    if ($#json && "$json" != "null") then
      # get last date
      set last = ( `/bin/echo "$json" | jq -r '.date'` )
      if ($#last == 0 || "$last" == "null") set last = 0
    else
      if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- UNKNOWN CLASS $i ($CID)" >>&! $LOGTO
      set unknown = ( $unknown "$i" )
    endif
  endif

  # get last modified time (10th field) in seconds since epoch
  set stat = ( `/usr/bin/stat -r "$CDIR" | /usr/bin/awk '{ print $10 }'` )
  if ($#stat == 0) then
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- NO STATS ($CDIR)" >>&! $LOGTO
    continue
  endif

  # record separator
  if ($k) /bin/echo ',' >>! "$ALL.$$"
  @ k++

  # check if directory is updated
  if ($stat <= $last) then
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- $CDIR UNCHANGED ($stat <= $last)" >>&! $LOGTO
    if ($?json && $?NOFORCE) then
      if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- using prior record: $db/$i == $json" >>&! $LOGTO
      /bin/echo "$json" >>! "$ALL.$$"
      continue
    else
      if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- making new record :: prior JSON ($?json) :: no-force ($?NOFORCE)" >>&! $LOGTO
    endif
  else
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- $CDIR CHANGED ($stat > $last)" >>&! $LOGTO
  endif

  #
  # NOW CHECK INVENTORY OF IMAGES
  #
  set FILES = "$OUTPUT:r:r"-files.$$.json
  set images = ( `/bin/echo "$CDIR"/*.jpg` )
  if ($#images) then
    /bin/echo "$images" | xargs stat -r | awk '{ print $10, $16 }' | sort -k 1,1 -n | sed 's@\([0-9]*\).*/\([^/]*\).jpg@\1,\2@' >! "$FILES"
  else
    set subdirs = ( "$CDIR"/* )
    rm -f "$FILES"
    foreach s ( $subdirs )
      find "$s" -name "*.jpg" -type f -print | xargs -I % stat -r % | awk '{ print $10, $16 }' | sort -k 1,1 -n | sed 's@\([0-9]*\).*/\([^/]*\).jpg@\1,\2@' >>! "$FILES"
    end
  endif

  set nfiles = ( `/usr/bin/wc -l "$FILES" | awk '{ print $1 }'` )

  #
  # MAKE NEW ENTRY FOR ALL CLASSES RECORD - "all"
  set json = '{"name":"'"$i"'","date":'"$stat"',"count":'"$nfiles"'}'
  # concatenante
  /bin/echo "$json" >> "$ALL.$$"

  #
  # CREATE CLASS RECORD
  #
  set CLASS = "$OUTPUT:r:r"-class.$$.json
  /bin/echo '{"name":"'"$i"'","date":'"$stat"',"count":'"$nfiles"',"ids":[' >! "$CLASS"
  if ($nfiles > 0 && -s "$FILES") then
    @ j = 0
    foreach file ( `/bin/cat "$FILES"` )
      set file = ( `/bin/echo "$file" | sed "s/,/ /"` )
      set date = $file[1]
      set imgid = $file[2]

      if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- IMAGE $j of $nfiles in CLASS $i; ID: $imgid DATE: ($date)" >>&! $LOGTO
      
      if ($j) /bin/echo -n ',' >>! "$CLASS"
      set file = '{ "id":"'"$file[2]"'","date":'"$file[1]"' }'
      /bin/echo "$file" >>! "$CLASS"
      # increment count of files
      @ j++
    end
  endif
  # complete array of image records
  /bin/echo ']}' >>! "$CLASS"

  jq -c '.' "$CLASS" >&! /dev/null
  if ($status != 0) then
    echo "FAIL : $CLASS"
    cat "$CLASS"
    exit
  endif

  set url = "$CU/$db-$API/$CID"
  set rev = ( `curl -s -q -L "$url" | jq -r '._rev?'` )
  if ($#rev && "$rev" != "null") then
    set url = "$url?rev=$rev"
  endif
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- PUT NEW RECORD CLASS $i $nfiles ($CID)" >>&! $LOGTO
  set put = ( `curl -s -q -L -H "Content-type: application/json" -X PUT "$url" -d "@$CLASS" | jq '.ok'`)
  if ("$put" != "true") then
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- $url FAILED" >>&! $LOGTO
  else
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- PUT NEW RECORD $url" >>&! $LOGTO
  endif
  /bin/rm -f "$CLASS"

end

rm -f "$ALL"
cat "$ALL.$$" >! "$OUTPUT.$$"
rm -f "$ALL.$$"

/bin/echo '],"count":'$k'}' >> "$OUTPUT.$$"

jq -c '.' "$OUTPUT.$$" >! "$OUTPUT"

#
# update all record
#
set url = "$CU/$db-$API/all" 
set rev = ( `curl -s -q -L "$url" | jq -r '._rev?'` )
if ($#rev && $rev != "null") then
  set url = "$url?rev=$rev"
endif
set put = ( `curl -s -q -L -H "Content-type: application/json" -X PUT "$url" -d "@$OUTPUT" | jq '.ok'` )
if ("$put" != "true") then
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- $url FAILED" >>&! $LOGTO
else
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- PUT NEW RECORD $url" >>&! $LOGTO
endif

done:
/bin/echo `/bin/date` "$0 $$ -- FINISH ($QUERY_STRING)" >>&! $LOGTO

cleanup:
rm -f "$OUTPUT.$$"
