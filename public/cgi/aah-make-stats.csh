#!/bin/tcsh
setenv APP "aah"
setenv API "stats"
if ($?TMP == 0) setenv TMP "/tmp"
setenv WWW "http://www.dcmartin.com/CGI/"
setenv LAN "192.168.1"
# don't update statistics more than once per 15 minutes
set TTL = `echo "30 * 60" | bc`
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

if ($?CLOUDANT_URL) then
    setenv CU $CLOUDANT_URL
else
    if (-e ~$USER/.cloudant_url) then
        set cc = ( `cat ~$USER/.cloudant_url` )
	if ($#cc > 0) set CU = $cc[1]
	if ($#cc > 1) set CN = $cc[2]
	if ($#cc > 2) set CP = $cc[3]
	unset cc
    endif
    if ($?CN && $?CP) then
        setenv CU "https://$CN":"$CP"@"$CN.cloudant.com"
    else
        echo "$APP-$API ($0 $$) -- No Cloudant URL" >>! $TMP/LOG
	exit
    endif
endif

if ($?QUERY_STRING != 0 && $QUERY_STRING != "") then
    set DB = `echo $QUERY_STRING | sed "s/.*db=\([^&]*\).*/\1/"`
    set class = `echo $QUERY_STRING | sed "s/.*id=\(.*\)/\1/"`
else
    set DB = rough-fog
    set class = person
    setenv QUERY_STRING `echo "db=$DB&id=$class"`
endif

# output set
set JSON = ( `echo "$TMP/$APP-$API-$QUERY_STRING.$DATE.json."*` )

# check JSON complete or in-progress for current interval
if ($#JSON < 1) then
    set JSON = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
    set OLD_STATS = "$JSON.$$"
    echo "$APP-$API ($0 $$) -- Making $JSON" >>! $TMP/LOG
    # download stats
    curl -o "$OLD_STATS" -s -q -X GET "$CU/$DB-stats/$class"
    set CLASS_DB = `/usr/local/bin/jq '._id' "$OLD_STATS" | sed 's/"//g'`
    if ($CLASS_DB != $class) then
	echo "$APP-$API ($0 $$) -- No existing statistics ($CU/$DB-stats/$class)" >>! $TMP/LOG
	set prev_seqid = 0
    else
	# get last sequence # for class specified
	set prev_seqid = `/usr/local/bin/jq '.seqid' "$OLD_STATS"`
	if ($prev_seqid[1] == "null") set prev_seqid = 0
    endif
else
    echo "$APP-$API ($0 $$) - In-progress $JSON" >>! $TMP/LOG
    exit
endif

#
# get JSON changes
#
set CHANGE_JSON = "$TMP/$DB-$class-changes.$$.json"
set seqid = 0
if ( ! -e "$CHANGE_JSON" ) then
    echo "$APP-$API ($0 $$) -- creating $CHANGE_JSON (since = $prev_seqid) " >>! $TMP/LOG
    # remove old
    /bin/rm -f "$TMP/$DB-$class-changes.*.json" >&! /dev/null
    curl -s -o "$CHANGE_JSON" "$CU/$DB/_changes?include_docs=true&since=$prev_seqid"
    set seqid = ( `/usr/local/bin/jq .last_seq "$CHANGE_JSON"` )
    if ($seqid == "null") then
         echo "$APP-$API ($0 $$) -- FAILURE RETRIEVING CHANGE_JSON" >>! $TMP/LOG
	 exit
    endif
else
    set seqid = ( `/usr/local/bin/jq .last_seq "$CHANGE_JSON"` )
    if ($seqid == "null") then
         echo "$APP-$API ($0 $$) -- BAD JSON $CHANGE_JSON" >>! $TMP/LOG
	 exit
    endif
    set ttyl = `echo "$SECONDS - $DATE" | bc`
    echo "$APP-$API ($0 $$) -- JSON ($CHANGE_JSON) is current with TTL of $TTL; next update in $ttyl seconds" >>! $TMP/LOG
endif

#
# convert JSON to CSV
#
set CHANGE_ROWS = "$TMP/$DB-$class-changes.$$.csv"
if ((! -e "$CHANGE_ROWS") || ((-M "$CHANGE_JSON") > (-M "$CHANGE_ROWS"))) then
    echo "$APP-$API ($0 $$) -- creating $CHANGE_ROWS" >>! $TMP/LOG
    /usr/local/bin/in2csv -k "results" "$CHANGE_JSON" >! "$CHANGE_ROWS"
    # extract only rows with specified classifier
    head -1 "$CHANGE_ROWS" >! "$CHANGE_ROWS.$$"
    tail +2 "$CHANGE_ROWS" | egrep ",$class," >> "$CHANGE_ROWS.$$"
    mv -f "$CHANGE_ROWS.$$" "$CHANGE_ROWS"
else
    echo "$APP-$API ($0 $$) -- $CHANGE_ROWS is current with $CHANGE_JSON" >>! $TMP/LOG
endif

#
# Build intervals for all records
#
set datetime = ( doc/year doc/month doc/day doc/hour doc/minute doc/second )
set dtcolumns = `echo "$datetime" | sed "s/ /,/g"`
set colset = `/usr/local/bin/csvstat -n "$CHANGE_ROWS" | /usr/local/bin/gawk '{ print $2 }'`

set CLASS_INTERVALS = "$TMP/$DB-$class-intervals.$$.csv"
if ((! -e "$CLASS_INTERVALS") || ((-M "$CHANGE_ROWS") > (-M "$CLASS_INTERVALS"))) then
    # get all columns as set and convert to CSV header
    set colnam = `echo $colset | sed "s/ /,/g"`

    echo "$APP-$API ($0 $$) -- creating $CLASS_INTERVALS" >>! $TMP/LOG
    echo "interval,ampm,week,day,id" >! "$TMP/$DB-$class-intervals.$$.csv"

    # cut out data/time columns and produce interval calculations using GAWK
    set datetime = ( doc/year doc/month doc/day doc/hour doc/minute doc/second )
    set dtcolumns = `echo "$datetime" | sed "s/ /,/g"`
    /usr/local/bin/csvcut -c "id","$dtcolumns" "$CHANGE_ROWS" | \
	tail +2 | \
	/usr/local/bin/gawk -F, '{ m=$5*60+$6; m = m / 15; t=mktime(sprintf("%4d %2d %2d %2d %2d %2d", $2, $3, $4, $5, $6, $7)); printf "%d,%s,%s,%s,%s\n", m, strftime("%p",t),strftime("%U",t),strftime("%A",t), $1 }' >> "$CLASS_INTERVALS"
else
    echo "$APP-$API ($0 $$) -- $CLASS_INTERVALS is current with $CHANGE_ROWS" >>! $TMP/LOG
endif

#
# get all intervals values for class
#
set CLASS_VALUES = "$TMP/$DB-$class-values.$$.csv"
if ((! -e "$CLASS_VALUES") || ((-M "$CHANGE_ROWS") > (-M "$CLASS_VALUES"))) then
    echo "$APP-$API ($0 $$) -- creating $CLASS_VALUES " >>! $TMP/LOG
    echo "classifier,score,$dtcolumns,id" >! "$CLASS_VALUES"

    # check Alchemy when classifier is lowercase
    set vi = `echo $class | sed "s/\([a-z]\)*.*/\1/"`
    if ($vi != "") then
	set acolset = `/usr/local/bin/csvstat -n "$CHANGE_ROWS" | /usr/local/bin/gawk '{ print $2 }' | egrep "alchemy/text"`
	foreach j ( $acolset )
	    /usr/local/bin/csvcut -c "$j","$j:h/score","$dtcolumns","id" "$CHANGE_ROWS" | egrep "^$class," >> "$CLASS_VALUES"
	end
    endif

    # check VisualInsights when classifier is uppercase
    set vi = `echo $class | sed "s/\([A-Z]\)*.*/\1/"`
    if ($vi != "") then
	set vcolset = `/usr/local/bin/csvstat -n "$CHANGE_ROWS" | /usr/local/bin/gawk '{ print $2 }' | egrep "classifier_id"`
	foreach j ( $vcolset )
	    /usr/local/bin/csvcut -c "$j","$j:h/score","$dtcolumns","id" "$CHANGE_ROWS" | egrep "^$class," >> "$CLASS_VALUES"
	end
    endif
else
    echo "$APP-$API ($0 $$) -- $CLASS_VALUES is current with $CHANGE_ROWS" >>! $TMP/LOG
endif

#
# extract only events by classifier specified
#
set CLASS_INTERVAL_VALUES = "$TMP/$DB-$class-interval-values.$$.csv" 
echo "$APP-$API ($0 $$) -- creating $CLASS_INTERVAL_VALUES " >>! $TMP/LOG
cat "$TMP/$DB-$class-values.$$.csv" | csvjoin -c "id,id" - $TMP/$DB-$class-intervals.$$.csv | csvcut -c "interval,day,week,classifier,score" >! "$CLASS_INTERVAL_VALUES"

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

#
# update JSON statistics 
#
set NEW_STATS = "$OLD_STATS.$$"

echo "$APP-$API ($0 $$) -- creating $NEW_STATS" >>! $TMP/LOG
echo -n '{ "seqid":'$seqid',"days":[' >! "$NEW_STATS"
set days = ( Sunday Monday Tuesday Wednesday Thursday Friday Saturday )
@ k = 0
foreach d ( $days )


    if ($k > 0) echo "," >> "$NEW_STATS"

    set nweek = `/usr/local/bin/csvgrep -c day -m "$d" $CLASS_INTERVAL_VALUES | /usr/local/bin/csvcut -c week | tail +2 | sort | uniq | wc -l`
    set numwk = `/usr/local/bin/jq '.days['$k'].numwk' "$OLD_STATS" | sed 's/"//g'`
    set nweek = `echo "$nweek + $numwk" | bc`

    echo "$APP-$API ($0 $$) -- calculating $d ($nweek)" >>! $TMP/LOG

    echo -n '{"weekday":"'$d'","numwk":"'$nweek'","intervals":[' >> "$NEW_STATS"

    @ j = 1
    foreach i ( $intervals )
	if ($j > 1) echo "," >> "$NEW_STATS"

	set count = `/usr/local/bin/jq '.days['$k'].intervals['$i'].count' "$OLD_STATS" | sed 's/"//g'`
	set sum = `/usr/local/bin/jq '.days['$k'].intervals['$i'].sum' "$OLD_STATS" | sed 's/"//g'`
	set mean = `/usr/local/bin/jq '.days['$k'].intervals['$i'].mean' "$OLD_STATS" | sed 's/"//g'`
	set stdev = `/usr/local/bin/jq '.days['$k'].intervals['$i'].stdev' "$OLD_STATS" | sed 's/"//g'`

	# echo "$APP-$API ($0 $$) -- day[$k].interval[$i] : $count $sum $mean $stdev" >>! $TMP/LOG
	set var = `echo "$stdev * $stdev * $count" | bc -l`

	set l = `egrep "^$i,$d," $CLASS_INTERVAL_VALUES | /usr/local/bin/gawk -v "c=$count" -v "s=$sum" -v "m=$mean" -v "vs=$var" -F, '{ c++; s=s+$5; m=s/c; vs=vs+($5-m)^2; v=vs/c } END { sd=sqrt(v); printf "%d %f %f %f", c, s, m, sd }'`

	# echo "$APP-$API ($0 $$) -- day[$k].interval[$i] : $l" >>! $TMP/LOG

	echo -n '{"count":"'$l[1]'","sum":"'$l[2]'","mean":"'$l[3]'","stdev":"'$l[4]'"}' >> "$NEW_STATS"
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
	    curl -s -q -X DELETE "$CU/$DB-stats/$class?rev=$rev"
	endif
	echo "$APP-$API ($0 $$) -- STORE $NEW_STATS" >>! $TMP/LOG
	curl -s -q -H "Content-type: application/json" -X PUT "$CU/$DB-stats/$class" -d "@$NEW_STATS"
    endif
    echo "$APP-$API ($0 $$) -- SUCCESS : $JSON" >>! $TMP/LOG
    # update statistics
    mv -f "$NEW_STATS" "$JSON"
    # remove temporary files
    rm -f $OLD_STATS $CHANGE_JSON $CHANGE_ROWS $CLASS_INTERVALS $CLASS_VALUES $CLASS_INTERVAL_VALUES
else
    echo "$APP-$API ($0 $$) -- No CLOUDANT update" >>! $TMP/LOG
endif
