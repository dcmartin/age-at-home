#!/bin/csh -fb
setenv APP "aah"
setenv API "stats"
setenv LAN "192.168.1"
setenv WWW "www.dcmartin.com"
setenv TMP "/var/lib/age-at-home"

if ($?TTL == 0) set TTL = 3600
if ($?SECONDS == 0) set SECONDS = `/bin/date "+%s"`
if ($?DATE == 0) set DATE = `/bin/echo $SECONDS \/ $TTL \* $TTL | /usr/bin/bc`

setenv DEBUG true
setenv NOFORCE true

if ($?QUERY_STRING) then
    set db = `/bin/echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
    set class = `/bin/echo "$QUERY_STRING" | sed 's/.*class=\([^&]*\).*/\1/'`
    if ($class == "$QUERY_STRING") unset class
endif

# DEFAULTS to rough-fog (kitchen) and "person" class (should change to handle "all")
if ($?db == 0) set db = rough-fog
if ($?class == 0) set class = person

# standardize QUERY_STRING
setenv QUERY_STRING "db=$db&class=$class"

echo `date` "$0 $$ - START ($QUERY_STRING)" # # >>&! $TMP/LOG

#
# output set
#
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

#
# check output
#

if (-s "$OUTPUT") then
  goto done
endif

#
# SINGLE THREADED (by QUERY_STRING)
#
set INPROGRESS = ( `/bin/echo "$OUTPUT".*` )
if ($#INPROGRESS) then
    set pid = $INPROGRESS[$#INPROGRESS]:e
    set pid = `ps axw | egrep "$pid" | egrep "$API" | awk '{ print $1 }'`
    if ($#pid) then
      if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- in-progress $INPROGRESS:e ($pid)" # >>&! $TMP/LOG
      goto done
    endif
    rm -f $INPROGRESS
endif
onintr cleanup
touch "$OUTPUT.$$"

#
# GET CLOUDANT CREDENTIALS
#
if (-e ~$USER/.cloudant_url) then
  set cc = ( `cat ~$USER/.cloudant_url` )
  if ($#cc > 0) set CU = $cc[1]
  if ($#cc > 1) set CN = $cc[2]
  if ($#cc > 2) set CP = $cc[3]
  if ($?CN && $?CP) then
    set CU = "$CN":"$CP"@"$CU"
  else
else
  if($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- NO ~$USER/.cloudant_url" # >>&! $TMP/LOG
  goto done
endif

#
# CREATE DATABASE 
#
if ($?CU && $?db) then
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- test if db exists ($CU/$db-$API)" # >>&! $TMP/LOG
  set DEVICE_db = `/usr/bin/curl -s -q -L -X GET "$CU/$db-$API" | /usr/local/bin/jq '.db_name'`
  if ( $DEVICE_db == "" || "$DEVICE_db" == "null" ) then
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- creating db $CU/$db-$API" # >>&! $TMP/LOG
    # create db
    set DEVICE_db = `/usr/bin/curl -s -q -L -X PUT "$CU/$db-$API" | /usr/local/bin/jq '.ok'`
    # test for success
    if ( "$DEVICE_db" != "true" ) then
      # failure
      if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- failure creating Cloudant database ($db-$API)" # >>&! $TMP/LOG
      goto done
    else
      if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- success creating db $CU/$db-$API" # >>&! $TMP/LOG
    endif
  endif
endif

#
# ATTEMPT TO REAL "all" record with summary information
#
set ALL = "$OUTPUT:r:r"-all.$$.json
set last = 0
set known = ()
/usr/bin/curl -s -q -f -L "$CU/$db-$API/all" -o "$ALL"
if ($status != 22 && -s "$ALL") then
  set last = ( `/usr/local/bin/jq -r '.date' "$ALL"` )
  if ($#last == 0 || $last == "null") then
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- NO MODIFIED DATE ($i)" # >>&! $TMP/LOG
    set last = 0
  else
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- ALL MODIFIED LAST ($last)" # >>&! $TMP/LOG
  endif
endif
if ($last && -s "$ALL") then
  # get known from "all" record
  set known = ( `/usr/local/bin/jq -r '.classes[]?.name' "$ALL"` )
endif
if ($#known == 0) then
  # get known through inspection of all rows
  set known = ( `curl -s -q -f -L "$CU/$db-$API/_all_docs" | /usr/local/bin/jq -r '.rows[]?.id'` )
endif
if ($#known == 0 || "$known" == '[]' || "$known" == "null") then
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- NO EXISTING CLASSES (all)" # >>&! $TMP/LOG
    set known = ()
  endif
else
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- CANNOT RETRIEVE $db-$API/all ($ALL)" # >>&! $TMP/LOG
  set last = 0
endif

#
# GET OLD
#
set OLD_STATS = "$OUTPUT:r"-old.json
set prev_seqid = 0
echo `date` "$0 $$ -- getting OLD_STATS ($db-$API/$class)" # # >>&! $TMP/LOG
curl -s -q -o "$OLD_STATS" -X GET "$CU/$db-$API/$class"
# check iff successful
set CLASS_db = `/usr/local/bin/jq -r '._id' "$OLD_STATS"`
if ($CLASS_db != $class) then
  echo `date` "$0 $$ -- no old statistics ($db-$API/$class)" # # >>&! $TMP/LOG
else
  # get last sequence # for class specified
  set prev_seqid = `/usr/local/bin/jq -r '.seqid' "$OLD_STATS"`
  if ("$prev_seqid" == "null") set prev_seqid = 0
endif

#
# get changes in events stored to db for device
#
set ALLCHANGES = "$TMP/$APP-$API-$db-changes.$DATE.json"
set seqid = 0
if ( ! -s "$ALLCHANGES" ) then
    rm -f "$ALLCHANGES:r:r".*
    echo `date` "$0 $$ -- creating $ALLCHANGES" # # >>&! $TMP/LOG
    set url = "$db/_changes?include_docs=true&since=$prev_seqid"
    curl -s -q -f -L "$CU/$url" -o "$ALLCHANGES.$$" >>&! "$TMP/LOG"
    if ($status != 22 && -s "$ALLCHANGES.$$") then
      if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- SUCCESS ALLCHANGES ($ALLCHANGES)" # >>&! $TMP/LOG
      mv "$ALLCHANGES.$$" "$ALLCHANGES"
    else
      if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- CANNOT RETRIEVE ALLCHANGES ($url)" # >>&! $TMP/LOG
    endif    
    rm -f "$ALLCHANGES.$$"
    set seqid = ( `/usr/local/bin/jq .last_seq "$ALLCHANGES"` )
    if ($seqid == "null") then
         echo `date` "$0 $$ -- FATAL ERROR :: BAD ALLCHANGES ($ALLCHANGES)" # # >>&! $TMP/LOG
	 exit
    endif
else
    set seqid = ( `/usr/local/bin/jq .last_seq "$ALLCHANGES"` )
    if ($seqid == "null") then
         echo `date` "$0 $$ -- FATAL ERROR :: BAD ALLCHANGES ($ALLCHANGES)" # # >>&! $TMP/LOG
	 exit
    endif
    set ttyl = `echo "$SECONDS - $DATE" | bc`
    echo `date` "$0 $$ -- OUTPUT ($ALLCHANGES) is current with TTL of $TTL; next update in $ttyl seconds" # # >>&! $TMP/LOG
endif

#
# convert OUTPUT to CSV
#
set ALLRECORDS = "$ALLCHANGES:r".csv
if ((! -s "$ALLRECORDS") || ((-M "$ALLCHANGES") > (-M "$ALLRECORDS"))) then
    echo `date` "$0 $$ -- creating $ALLRECORDS" # # >>&! $TMP/LOG
    /usr/local/bin/in2csv --no-inference -k "results" "$ALLCHANGES" >! "$ALLRECORDS"
else
    echo `date` "$0 $$ -- $ALLRECORDS is current with $ALLCHANGES" # # >>&! $TMP/LOG
endif

#
# subselect class records
#

set RECORDS = "$ALLCHANGES:r"-"$class".csv
if ((! -s "$RECORDS") || ((-M "$ALLRECORDS") > (-M "$RECORDS"))) then
  # extract only rows with specified classifier
  echo `date` "$0 $$ -- extracting all $class records" # # >>&! $TMP/LOG
  head -1 "$ALLRECORDS" >! "$RECORDS.$$"
  tail +2 "$ALLRECORDS" | egrep ",$class," >> "$RECORDS.$$"
  mv -f "$RECORDS.$$" "$RECORDS"
else
    echo `date` "$0 $$ -- $RECORDS is current with $ALLRECORDS" # # >>&! $TMP/LOG
endif

#
# Build intervals for all records
#
set datetime = ( doc/year doc/month doc/day doc/hour doc/minute doc/second )
set dtcolumns = `echo "$datetime" | sed "s/ /,/g"`
set colset = `/usr/local/bin/csvstat -n "$RECORDS" | /usr/local/bin/gawk '{ print $2 }'`

set CLASS_INTERVALS = "$TMP/$APP-$API-$db-$class-intervals.$$.csv"
if ((! -e "$CLASS_INTERVALS") || ((-M "$RECORDS") > (-M "$CLASS_INTERVALS"))) then
    # get all columns as set and convert to CSV header
    set colnam = `echo $colset | sed "s/ /,/g"`

    echo `date` "$0 $$ -- creating $CLASS_INTERVALS" # # >>&! $TMP/LOG
    echo "interval,ampm,week,day,id" >! "$TMP/$APP-$API-$db-$class-intervals.$$.csv"

    # cut out data/time columns and produce interval calculations using GAWK
    set datetime = ( doc/year doc/month doc/day doc/hour doc/minute doc/second )
    set dtcolumns = `echo "$datetime" | sed "s/ /,/g"`
    /usr/local/bin/csvcut -c "id","$dtcolumns" "$RECORDS" | \
	tail +2 | \
	/usr/local/bin/gawk -F, '{ m=$5*60+$6; m = m / 15; t=mktime(sprintf("%4d %2d %2d %2d %2d %2d", $2, $3, $4, $5, $6, $7)); printf "%d,%s,%s,%s,%s\n", m, strftime("%p",t),strftime("%U",t),strftime("%A",t), $1 }' >> "$CLASS_INTERVALS"
else
    echo `date` "$0 $$ -- $CLASS_INTERVALS is current with $RECORDS" # # >>&! $TMP/LOG
endif

#
# get all values for class (THIS IS WRONG; distinguishing on source by classifier; need to include "name")
#
set CLASS_VALUES = "$TMP/$APP-$API-$db-$class-values.$$.csv"
if ((! -e "$CLASS_VALUES") || ((-M "$RECORDS") > (-M "$CLASS_VALUES"))) then
    echo `date` "$0 $$ -- creating $CLASS_VALUES " # # >>&! $TMP/LOG
    echo "classifier,score,$dtcolumns,id" >! "$CLASS_VALUES"

    /usr/local/bin/csvstat -n "$RECORDS" | /usr/local/bin/gawk '{ print $2 }'

    # check Alchemy when classifier is lowercase
    set vi = `echo $class | sed "s/\([a-z]\)*.*/\1/"`
    if ($vi != "") then
	set acolset = `/usr/local/bin/csvstat -n "$RECORDS" | /usr/local/bin/gawk '{ print $2 }' | egrep "alchemy/text"`
	foreach j ( $acolset )
	    /usr/local/bin/csvcut -c "$j","$j:h/score","$dtcolumns","id" "$RECORDS" | egrep "^$class," >> "$CLASS_VALUES"
	end
    endif

    # check VisualInsights when classifier is uppercase
    set vi = `echo $class | sed "s/\([A-Z]\)*.*/\1/"`
    if ($vi != "") then
	set vcolset = `/usr/local/bin/csvstat -n "$RECORDS" | /usr/local/bin/gawk '{ print $2 }' | egrep "classifier_id"`
	foreach j ( $vcolset )
	    /usr/local/bin/csvcut -c "$j","$j:h/score","$dtcolumns","id" "$RECORDS" | egrep "^$class," >> "$CLASS_VALUES"
	end
    endif
else
    echo `date` "$0 $$ -- $CLASS_VALUES is current with $RECORDS" # # >>&! $TMP/LOG
endif

#
# extract only events by classifier specified
#
set CLASS_INTERVAL_VALUES = "$TMP/$APP-$API-$db-$class-interval-values.$$.csv" 
echo `date` "$0 $$ -- creating $CLASS_INTERVAL_VALUES " # # >>&! $TMP/LOG
cat "$CLASS_VALUES" | /usr/local/bin/csvjoin -c "id,id" - "$CLASS_INTERVALS" | /usr/local/bin/csvcut -c "interval,day,week,classifier,score" >! "$CLASS_INTERVAL_VALUES"

#
# setup analysis intervals
#
set intervals = ()
set intvalues = ()
@ i = 0
# there are 96 15 minute intervals per day
while ($i < 96)
    set intervals = ( $intervals $i )
    set intvalues = ( $intvalues "c$i,s$i,m$i,d$i" )
    @ i++
end
set intnames = `echo $intvalues | sed "s/ /,/g"`

# set dowindex = `date +%w`

#
# update OUTPUT statistics 
#
set NEW_STATS = "$OLD_STATS.$$"
# get current day-of-week
echo `date` "$0 $$ -- creating NEW_STATS ($NEW_STATS)" # # >>&! $TMP/LOG
echo -n '{ "seqid":'$seqid',"days":[' >! "$NEW_STATS"
set days = ( Sunday Monday Tuesday Wednesday Thursday Friday Saturday )
@ k = 0
foreach d ( $days )
    if ($k > 0) echo "," >> "$NEW_STATS"

    # get new weeks
    /usr/local/bin/csvgrep -c day -m "$d" $CLASS_INTERVAL_VALUES | /usr/local/bin/csvcut -c week | tail +2 | sort -nr | uniq >! "$TMP/$APP-$API-$QUERY_STRING-weeks.$$"
    # get old weeks
    /usr/local/bin/jq '.days['$k'].weeks[]' "$OLD_STATS" | sed 's/"//g' >> "$TMP/$APP-$API-$QUERY_STRING-weeks.$$"

    # get uniq set
    set weeks = `cat "$TMP/$APP-$API-$QUERY_STRING-weeks.$$" | sort -nr | uniq | awk 'BEGIN { c=0 } { if (c > 0) printf ", "; printf "\"%d\"", $1; c++ }'`
    # remove temporary file
    rm -f "$TMP/$APP-$API-$QUERY_STRING-weeks.$$"

    echo -n '{"weekday":"'$d'","nweek":'$#weeks',"weeks":['$weeks'],"intervals":[' >> "$NEW_STATS"

    @ j = 1
    foreach i ( $intervals )
      if ($j > 1) echo "," >> "$NEW_STATS"

      if (-s "$OLD_STATS") then
	set count = `/usr/local/bin/jq -r '.days['$k'].intervals['$i'].count' "$OLD_STATS"` ; if ($count == "null") set count = 0
	set max = `/usr/local/bin/jq -r '.days['$k'].intervals['$i'].max' "$OLD_STATS"` ; if ($max == "null") set max = 0
	set sum = `/usr/local/bin/jq -r '.days['$k'].intervals['$i'].sum' "$OLD_STATS"` ; if ($sum == "null") set sum = 0
	set mean = `/usr/local/bin/jq -r '.days['$k'].intervals['$i'].mean' "$OLD_STATS"` ; if ($mean == "null") set mean = 0
	set stdev = `/usr/local/bin/jq -r '.days['$k'].intervals['$i'].stdev' "$OLD_STATS"` ; if ($stdev == "null") set stdev = 0
      else
        set count = 0; set max = 0; set sum = 0; set mean = 0; set stdev = 0;
      endif

	# calculate existing variance
	set var = `echo "$stdev * $stdev * $count" | bc -l`

	egrep "^$i,$d," $CLASS_INTERVAL_VALUES | \
	    awk -F, \
	        -v "c=$count" \
		-v "mx=$max" \
		-v "s=$sum" \
		-v "m=$mean" \
		-v "vs=$var" \
		'{ c++; if ($5 > mx) mx=$5; s+=$5; m=s/c; vs+=(($5-m)^2) } END { sd=0; if (c > 0) sd=sqrt(vs/c); printf "{\"count\":%d,\"max\":%f,\"sum\":%f,\"mean\":%f,\"stdev\":%f}", c, mx, s, m, sd }' >> "$NEW_STATS"
	# next!
	@ j++
    end

    echo -n "] }" >> "$NEW_STATS"
    @ k++
end
echo "] }" >> "$NEW_STATS"

# update statistics
mv -f "$NEW_STATS" "$OUTPUT"

#
# update Cloudant
#
set rev = ( `/usr/bin/curl -s -q -L "$CU/$db-$API/$class" | /usr/local/bin/jq -r '._rev'` )
if ($#rev && $rev != "null") then
  /usr/bin/curl -s -q -L -X DELETE "$CU/$db-$API/$class?rev=$rev"
endif
/usr/bin/curl -s -q -L -H "Content-type: application/json" -X PUT "$CU/$db-$API/$class" -d "@$OUTPUT" # >>&! $TMP/LOG
if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- $db-$API/$class returned $status" # >>&! $TMP/LOG

cleanup:
  rm -f "$OUTPUT".*

done:

echo `date` "$0 $$ - FINISH ($QUERY_STRING)" # # >>&! $TMP/LOG
