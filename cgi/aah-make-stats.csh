#!/bin/tcsh
setenv APP "aah"
setenv API "stats"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"
setenv LAN "192.168.1"
# don't update statistics more than once per 15 minutes
set TTL = 3600
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo `date` "$0 $$ - START" >>! $TMP/LOG

if (-e ~$USER/.cloudant_url) then
    echo `date` "$0 $$ -- ~$USER/.cloudant_url" >>! $TMP/LOG
    set cc = ( `cat ~$USER/.cloudant_url` )
    if ($#cc > 0) set CU = $cc[1]
    if ($#cc > 1) set CN = $cc[2]
    if ($#cc > 2) set CP = $cc[3]
endif

if ($?CLOUDANT_URL) then
    set CU = $CLOUDANT_URL
else if ($?CN && $?CP) then
    set CU = "$CN":"$CP"@"$CN.cloudant.com"
else
    echo `date` "$0 $$ -- No Cloudant URL" >>! $TMP/LOG
    exit
endif

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed "s/.*db=\([^&]*\).*/\1/"` 
    set class = `echo "$QUERY_STRING" | sed "s/.*id=\([^&]*\)/\1/"`
else
    set DB = rough-fog
    set class = person
endif
setenv QUERY_STRING "db=$DB&id=$class"

# output set
set JSON = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
set INPROGRESS = ( `echo "$JSON".*` )

# check JSON in-progress for current interval
if ($#INPROGRESS) then
    echo `date` "$0 $$ -- in-progress" >>! $TMP/LOG
    goto done
else
    # download stats
    set OLD_STATS = "$JSON.$$"
    echo `date` "$0 $$ -- getting OLD_STATS ($OLD_STATS)" >>! $TMP/LOG
    curl -s -q -o "$OLD_STATS" -X GET "$CU/$DB-stats/$class"
    # check iff successful
    set CLASS_DB = `/usr/local/bin/jq '._id' "$OLD_STATS" | sed 's/"//g'`
    if ($CLASS_DB != $class) then
	echo `date` "$0 $$ -- no existing statistics ($CU/$DB-stats/$class)" >>! $TMP/LOG
	exit
    else
	# get last sequence # for class specified
	set prev_seqid = `/usr/local/bin/jq '.seqid' "$OLD_STATS"`
	if ($prev_seqid[1] == "null") set prev_seqid = 0
    endif
endif

#
# get JSON changes
#
set NEW_JSON = "$TMP/$APP-$API-$DB-$class-changes.$$.json"
set seqid = 0
if ( ! -e "$NEW_JSON" ) then
    echo `date` "$0 $$ -- creating $NEW_JSON" >>! $TMP/LOG
    curl -s -q -o "$NEW_JSON" "$CU/$DB/_changes?include_docs=true&since=$prev_seqid"
    set seqid = ( `/usr/local/bin/jq .last_seq "$NEW_JSON"` )
    if ($seqid == "null") then
         echo `date` "$0 $$ -- FAILURE RETRIEVING NEW_JSON" >>! $TMP/LOG
	 exit
    endif
else
    set seqid = ( `/usr/local/bin/jq .last_seq "$NEW_JSON"` )
    if ($seqid == "null") then
         echo `date` "$0 $$ -- BAD JSON $NEW_JSON" >>! $TMP/LOG
	 exit
    endif
    set ttyl = `echo "$SECONDS - $DATE" | bc`
    echo `date` "$0 $$ -- JSON ($NEW_JSON) is current with TTL of $TTL; next update in $ttyl seconds" >>! $TMP/LOG
endif

#
# convert JSON to CSV
#
set NEW_ROWS = "$TMP/$APP-$API-$DB-$class-changes.$$.csv"
if ((! -e "$NEW_ROWS") || ((-M "$NEW_JSON") > (-M "$NEW_ROWS"))) then
    echo `date` "$0 $$ -- creating $NEW_ROWS" >>! $TMP/LOG
    /usr/local/bin/in2csv --no-inference -k "results" "$NEW_JSON" >! "$NEW_ROWS"
    # extract only rows with specified classifier
    head -1 "$NEW_ROWS" >! "$NEW_ROWS.$$"
    tail +2 "$NEW_ROWS" | egrep ",$class," >> "$NEW_ROWS.$$"
    mv -f "$NEW_ROWS.$$" "$NEW_ROWS"
else
    echo `date` "$0 $$ -- $NEW_ROWS is current with $NEW_JSON" >>! $TMP/LOG
endif

#
# Build intervals for all records
#
set datetime = ( doc/year doc/month doc/day doc/hour doc/minute doc/second )
set dtcolumns = `echo "$datetime" | sed "s/ /,/g"`
set colset = `/usr/local/bin/csvstat -n "$NEW_ROWS" | /usr/local/bin/gawk '{ print $2 }'`

set CLASS_INTERVALS = "$TMP/$APP-$API-$DB-$class-intervals.$$.csv"
if ((! -e "$CLASS_INTERVALS") || ((-M "$NEW_ROWS") > (-M "$CLASS_INTERVALS"))) then
    # get all columns as set and convert to CSV header
    set colnam = `echo $colset | sed "s/ /,/g"`

    echo `date` "$0 $$ -- creating $CLASS_INTERVALS" >>! $TMP/LOG
    echo "interval,ampm,week,day,id" >! "$TMP/$APP-$API-$DB-$class-intervals.$$.csv"

    # cut out data/time columns and produce interval calculations using GAWK
    set datetime = ( doc/year doc/month doc/day doc/hour doc/minute doc/second )
    set dtcolumns = `echo "$datetime" | sed "s/ /,/g"`
    /usr/local/bin/csvcut -c "id","$dtcolumns" "$NEW_ROWS" | \
	tail +2 | \
	/usr/local/bin/gawk -F, '{ m=$5*60+$6; m = m / 15; t=mktime(sprintf("%4d %2d %2d %2d %2d %2d", $2, $3, $4, $5, $6, $7)); printf "%d,%s,%s,%s,%s\n", m, strftime("%p",t),strftime("%U",t),strftime("%A",t), $1 }' >> "$CLASS_INTERVALS"
else
    echo `date` "$0 $$ -- $CLASS_INTERVALS is current with $NEW_ROWS" >>! $TMP/LOG
endif

#
# get all values for class
#
set CLASS_VALUES = "$TMP/$APP-$API-$DB-$class-values.$$.csv"
if ((! -e "$CLASS_VALUES") || ((-M "$NEW_ROWS") > (-M "$CLASS_VALUES"))) then
    echo "+++ $APP-$API ($0 $$) -- creating $CLASS_VALUES " >>! $TMP/LOG
    echo "classifier,score,$dtcolumns,id" >! "$CLASS_VALUES"

    # check Alchemy when classifier is lowercase
    set vi = `echo $class | sed "s/\([a-z]\)*.*/\1/"`
    if ($vi != "") then
	set acolset = `/usr/local/bin/csvstat -n "$NEW_ROWS" | /usr/local/bin/gawk '{ print $2 }' | egrep "alchemy/text"`
	foreach j ( $acolset )
	    /usr/local/bin/csvcut -c "$j","$j:h/score","$dtcolumns","id" "$NEW_ROWS" | egrep "^$class," >> "$CLASS_VALUES"
	end
    endif

    # check VisualInsights when classifier is uppercase
    set vi = `echo $class | sed "s/\([A-Z]\)*.*/\1/"`
    if ($vi != "") then
	set vcolset = `/usr/local/bin/csvstat -n "$NEW_ROWS" | /usr/local/bin/gawk '{ print $2 }' | egrep "classifier_id"`
	foreach j ( $vcolset )
	    /usr/local/bin/csvcut -c "$j","$j:h/score","$dtcolumns","id" "$NEW_ROWS" | egrep "^$class," >> "$CLASS_VALUES"
	end
    endif
else
    echo `date` "$0 $$ -- $CLASS_VALUES is current with $NEW_ROWS" >>! $TMP/LOG
endif

#
# extract only events by classifier specified
#
set CLASS_INTERVAL_VALUES = "$TMP/$APP-$API-$DB-$class-interval-values.$$.csv" 
echo `date` "$0 $$ -- creating $CLASS_INTERVAL_VALUES " >>! $TMP/LOG
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
# update JSON statistics 
#
set NEW_STATS = "$OLD_STATS.$$"
# get current day-of-week
echo `date` "$0 $$ -- creating NEW_STATS ($NEW_STATS)" >>! $TMP/LOG
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

	set count = `/usr/local/bin/jq '.days['$k'].intervals['$i'].count' "$OLD_STATS" | sed 's/"//g'`
	set max = `/usr/local/bin/jq '.days['$k'].intervals['$i'].max' "$OLD_STATS" | sed 's/"//g'`
	set sum = `/usr/local/bin/jq '.days['$k'].intervals['$i'].sum' "$OLD_STATS" | sed 's/"//g'`
	set mean = `/usr/local/bin/jq '.days['$k'].intervals['$i'].mean' "$OLD_STATS" | sed 's/"//g'`
	set stdev = `/usr/local/bin/jq '.days['$k'].intervals['$i'].stdev' "$OLD_STATS" | sed 's/"//g'`

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

#
# update Cloudant
#
if ($?CLOUDANT_OFF == 0 && $?CU && $?DB) then
    set DEVICE_DB = `curl -s -q -X GET "$CU/$DB-stats" | /usr/local/bin/jq '.db_name'`
    if ( "$DEVICE_DB" == "null" ) then
	# create DB
	set DEVICE_DB = `curl -s -q -X PUT "$CU/$DB-stats" | /usr/local/bin/jq '.ok'`
	# test for success
	if ( "$DEVICE_DB" != "true" ) then
	    # failure
	    setenv CLOUDANT_OFF TRUE
	endif
    endif
    if ( $?CLOUDANT_OFF == 0 ) then
	set doc = ( `cat "$OLD_STATS" | /usr/local/bin/jq ._id,._rev | sed 's/"//g'` )
	if ($#doc == 2 && $doc[1] == $class && $doc[2] != "") then
	    set rev = $doc[2]
	    echo `date` "$0 $$ -- DELETE $rev" >>! $TMP/LOG
	    curl -s -q -X DELETE "$CU/$DB-stats/$class?rev=$rev" >>! $TMP/LOG
	endif
	echo `date` "$0 $$ -- STORE $NEW_STATS" >>! $TMP/LOG
	curl -s -q -H "Content-type: application/json" -X PUT "$CU/$DB-stats/$class" -d "@$NEW_STATS" >>! $TMP/LOG
    endif
    echo `date` "$0 $$ -- SUCCESS : $JSON" >>! $TMP/LOG
    # update statistics
    mv -f "$NEW_STATS" "$JSON"
    # remove temporary files
    rm -f $OLD_STATS $NEW_JSON $NEW_ROWS $CLASS_INTERVALS $CLASS_VALUES $CLASS_INTERVAL_VALUES
else
    echo `date` "$0 $$ -- no CLOUDANT update" >>! $TMP/LOG
endif

done:

echo `date` "$0 $$ - START" >>! $TMP/LOG
