#!/bin/tcsh
setenv APP "aah"
setenv API "stats"
setenv WWW "http://www.dcmartin.com/CGI/"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/tmp"
# don't update statistics more than once per 15 minutes
set TTL = `echo "30 * 60" | bc`
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

if (-e ~$USER/.cloudant_url) then 
    set cc = ( `cat ~$USER/.cloudant_url` )
    if ($#cc > 0) set CU = $cc[1]
    if ($#cc > 1) set CN = $cc[2]
endif

if ($?CLOUDANT_URL) then
    setenv CU $CLOUDANT_URL
else if ($?CN) then
    set CU = "$CN.cloudant.com"
else
    echo "$APP-$API ($0 $$) -- No Cloudant URL" >>! $TMP/LOG
    exit
endif

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($DB == "$QUERY_STRING") unset DB
    set class = `echo "$QUERY_STRING" | sed 's/.*id=\([^&]*\).*/\1/'`
    if ($class == "$QUERY_STRING") unset class
    set day = `echo "$QUERY_STRING" | sed 's/.*day=\([^&]*\).*/\1/'`
    if ($day == "$QUERY_STRING") unset day
    set interval = `echo "$QUERY_STRING" | sed 's/.*interval=\([^&]*\).*/\1/'`
    if ($interval == "$QUERY_STRING") unset interval
endif


if ($?DB == 0) set DB = rough-fog
if ($?class == 0) set class = person
setenv QUERY_STRING "db=$DB&id=$class"

echo -n "$APP-$API ($0 $$) -- db=$DB id=$class " >>! $TMP/LOG
if ($?day) then
    echo -n "day=$day " >>! $TMP/LOG
else
    echo -n "day=<unset> " >>! $TMP/LOG
endif
if ($?interval) then
    echo -n "interval=$interval" >>! $TMP/LOG
else
    echo -n "interval=<unset> " >>! $TMP/LOG
endif
echo "" >>! $TMP/LOG

set JSON = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

if (! -e "$JSON") then
    echo "$APP-$API ($0 $$) -- initiating ./$APP-make-$API.bash ($JSON)" >>! $TMP/LOG
    ./$APP-make-$API.bash
    # find old results
    set OLD_JSON = `ls -1t $TMP/$APP-$API-QUERY_STRING.*.json`
    if ($#OLD_JSON == 0) then
	# note change in DATE to last TTL interval (not necessarily the same as statistics interval, independent)
	set DATE = `echo "(($SECONDS - $TTL ) / $TTL) * $TTL" | bc`
        set JSON = "/tmp/$APP-$API-$QUERY_STRING.$DATE.json"
	echo "$APP-$API ($0 $$) -- retrieving $JSON" >>! $TMP/LOG
	curl -s -o "$JSON" "https://$CU/$DB-$API/$class"
	set ERROR = `jq '.error' "$JSON" | sed 's/"//g'`
	if ($ERROR == "not_found") then
	    echo "$APP-$API ($0 $$) -- error ($ERROR)" >>! $TMP/LOG
	    exit
        endif
    else if ($#OLD_JSON > 1) then
	echo "$APP-$API ($0 $$) -- deleting $OLD_JSON[2-]" >>! $TMP/LOG
        /bin/rm -f "$OLD_JSON[2-]"
	set JSON = "$OLD_JSON[1]"
    endif
endif

if ($#JSON == 0) then
    echo "$APP-$API ($0 $$) -- No JSON ($JSON)" >>! $TMP/LOG
    echo "Status: 202 Accepted"
    exit
endif

#
# prepare for output
#

echo "Status: 200 OK"
echo "Content-Type: application/json"
set AGE = `echo "$SECONDS - $DATE" | bc`
echo "Age: $AGE"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo ""

echo "$APP-$API ($0 $$) -- last-modified" `date -r $DATE` >>! $TMP/LOG

echo "$APP-$API ($0 $$) -- day=$?day; interval=$?interval" >>! $TMP/LOG

if ($?day && $?interval) then
    if ($day == "all" && $interval == "all") then
        # get statistics for all days across all intervals
	cat "$JSON" | /usr/local/bin/jq -c '.days[].intervals[].count' | sed 's/"//g' | \
	    /usr/local/bin/gawk 'BEGIN { mx=0; mn=0; c=0; nz=0; s=0 } { c++; if ($1 > mx) mx=$1; if ($1 < mn) mn=$1; if($1 > 0) { nz++; s += $1; m = s/nz; vs += ($1 - m)^2; v=vs/nz} } END { sd = sqrt(v/nz); printf "{\"count\":\"%d\",\"non-zero\":\"%d\",\"min\":\"%d\",\"max\":\"%d\",\"sum\":\"%d\",\"mean\":\"%f\",\"stdev\":\"%f\"}\n", c, nz, mn, mx, s, m, sd  }'
    	exit
    else if ($day != "all" && $interval != "all") then
	# get specific interval
	cat "$JSON" | /usr/local/bin/jq -c '.days['$day'].intervals['$interval']'
	exit
    endif
endif

if ($?day) then
    if ($day != "all") then
	cat "$JSON" | /usr/local/bin/jq -c '.days['$day'].intervals[].count' | sed 's/"//g' | \
	    /usr/local/bin/gawk 'BEGIN { mx=0; mn= 0; nz=0; c=0; s=0 } { c++; if ($1 > mx) mx=$1; if ($1 < mn) mn=$1; if($1 > 0) { nz++; s += $1; m = s/nz; vs += ($1 - m)^2; v=vs/nz} } END { sd = sqrt(v/nz); printf "{\"count\":\"%d\",\"non-zero\":\"%d\",\"min\":\"%d\",\"max\":\"%d\",\"sum\":\"%d\",\"mean\":\"%f\",\"stdev\":\"%f\"}\n", c, nz, mn, mx, s, m, sd  }'
    else
	@ i = 0
	echo '{ "days": ['
	while ($i < 7)
	    if ($i > 0) echo ","
	    cat "$JSON" | /usr/local/bin/jq -c '.days['$i'].intervals[].count' | sed 's/"//g' | \
		/usr/local/bin/gawk 'BEGIN { mx=0; mn= 0; nz=0;c=0; s = 0 } { c++; if ($1 > mx) mx=$1; if ($1 < mn) mn=$1; if($1 > 0) { nz++; s += $1; m = s/nz; vs += ($1 - m)^2; v=vs/nz} } END { if(nz > 0) { sd = sqrt(v/nz) } else { sd = 0 }; printf "{\"count\":\"%d\",\"non-zero\":\"%d\",\"min\":\"%d\",\"max\":\"%d\",\"sum\":\"%d\",\"mean\":\"%f\",\"stdev\":\"%f\"}", c, nz, mn, mx, s, m, sd  }'
	    @ i++
	end
	echo "]}"
	rm -f "$TMP/$APP-$API.$$.json"
    endif
# test interval
else if ($?interval) then
    if ($interval != "all") then
	cat "$JSON" | /usr/local/bin/jq -c '.days[].intervals['$interval'].count' | sed 's/"//g' | \
	    /usr/local/bin/gawk 'BEGIN { mx=0; mn= 0; nz=0;c=0; s = 0 } { c++; if ($1 > mx) mx=$1; if ($1 < mn) mn=$1; if($1 > 0) { nz++; s += $1; m = s/nz; vs += ($1 - m)^2; v=vs/nz} } END { sd = sqrt(v/nz); printf "{\"count\":\"%d\",\"non-zero\":\"%d\",\"min\":\"%d\",\"max\":\"%d\",\"sum\":\"%d\",\"mean\":\"%f\",\"stdev\":\"%f\"}\n", c, nz, mn, mx, s, m, sd  }'
    else
	@ i = 0
	echo '{ "intervals": ['
	while ($i < 96)
	    if ($i > 0) echo ","
	    cat "$JSON" | /usr/local/bin/jq -c '.days[].intervals['$i'].count' | sed 's/"//g' | \
		/usr/local/bin/gawk 'BEGIN { mx=0; mn= 0; nz=0;c=0; s = 0 } { c++; if ($1 > mx) mx=$1; if ($1 < mn) mn=$1; if($1 > 0) { nz++; s += $1; m = s/nz; vs += ($1 - m)^2; v=vs/nz} } END { if(nz > 0) { sd = sqrt(v/nz) } else { sd = 0 }; printf "{\"count\":\"%d\",\"non-zero\":\"%d\",\"min\":\"%d\",\"max\":\"%d\",\"sum\":\"%d\",\"mean\":\"%f\",\"stdev\":\"%f\"}", c, nz, mn, mx, s, m, sd  }'
	    @ i++
	end
	echo "]}"
	rm -f "$TMP/$APP-$API.$$.json"
    endif
else
    cat "$JSON"
endif
