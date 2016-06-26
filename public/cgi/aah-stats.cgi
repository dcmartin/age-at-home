#!/bin/csh -fb
setenv APP "aah"
setenv API "stats"
setenv WWW "http://www.dcmartin.com/CGI/"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/tmp"
# don't update statistics more than once per TTL seconds
set TTL = 3600
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo "$APP-$API ($0 $$) BEGIN $DATE" >>! $TMP/LOG

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
    echo "$APP-$API ($0 $$) ** No Cloudant URL" >>! $TMP/LOG
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

if (-e "$JSON") then
    echo "$APP-$API ($0 $$) == CURRENT $JSON $DATE" >>! $TMP/LOG
else
    echo "$APP-$API ($0 $$) ++ MAKING ($JSON)" >>! $TMP/LOG
    ./$APP-make-$API.bash
    # find old results
    set OLD_JSON = ( `ls -1t "$TMP/$APP-$API-$QUERY_STRING".*.json` )
    if ($#OLD_JSON == 0) then
	# note change in DATE to last TTL interval (not necessarily the same as statistics interval, independent)
	set DATE = `echo "(($SECONDS - $TTL ) / $TTL) * $TTL" | bc`
	set JSON = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
        if (! -e "$JSON") then
	    echo "$APP-$API ($0 $$) << RETRIEVING ($JSON)" >>! $TMP/LOG
	    curl -s -q -o "$JSON" "https://$CU/$DB-$API/$class"
	endif
	set ERROR = `/usr/local/bin/jq '.error' "$JSON" | sed 's/"//g'`
	if ($ERROR == "not_found") then
	    echo "$APP-$API ($0 $$) ** ERROR ($ERROR)" >>! $TMP/LOG
	    exit
        endif
    else if ($#OLD_JSON > 0) then
	echo "$APP-$API ($0 $$) == OLD $JSON ($OLD_JSON)" >>! $TMP/LOG
	set JSON = "$OLD_JSON[1]"
	if ($#OLD_JSON > 1) then
	    echo "$APP-$API ($0 $$) -- DELETING $OLD_JSON[2-]" >>! $TMP/LOG
	    /bin/rm -f "$OLD_JSON[2-]"
	endif
    endif
endif

if ($#JSON == 0) then
    echo "$APP-$API ($0 $$) ** NONE ($JSON)" >>! $TMP/LOG
    echo "Status: 202 Accepted"
    goto done
else if (-e "$JSON") then
    echo "$APP-$API ($0 $$) --" `ls -al $JSON` >>! $TMP/LOG
endif

#
# prepare for output
#
echo "Content-Type: application/json; charset=utf-8"
echo "Access-Control-Allow-Origin: http://age-at-home.mybluemix.net/*"
set AGE = `echo "$SECONDS - $DATE" | bc`
echo "Age: $AGE"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo ""


# cat "$JSON"
# exit

if ($?day && $?interval) then
    if ($day == "all" && $interval == "all") then
        echo "+++ CALCULATING day ($day) and interval ($interval)" >>! $TMP/LOG
        # get statistics for all days across all intervals
	cat "$JSON" | /usr/local/bin/jq -c '.days[].intervals[].count' | sed 's/"//g' | \
	    /usr/local/bin/gawk 'BEGIN { mx=0; mn=0; c=0; nz=0; s=0;v=0 } { c++; if ($1 > mx) mx=$1; if ($1 < mn) mn=$1; if($1 > 0) { nz++; s += $1; m = s/nz; vs += ($1 - m)^2; v=vs/nz} } END { sd = sqrt(v); printf "{\"count\":%d,\"non-zero\":%d,\"min\":%d,\"max\":%d,\"sum\":%d,\"mean\":%f,\"stdev\":%f}\n", c, nz, mn, mx, s, m, sd  }'
    	goto done
    else if ($day != "all" && $interval != "all") then
        echo "+++ CALCULATING day ($day) and interval ($interval)" >>! $TMP/LOG
	# get specific interval
	cat "$JSON" | /usr/local/bin/jq -c '.days['$day'].intervals['$interval']'
	goto done
    endif
endif

if ($?day) then
    if ($day != "all") then
        echo -n "+++ CALCULATING day ($day) " >>! $TMP/LOG
	cat "$JSON" | /usr/local/bin/jq -c '.days['$day'].intervals[].count' | sed 's/"//g' | \
	    /usr/local/bin/gawk 'BEGIN { mx=0; mn= 0; nz=0; c=0; s=0;v=0 } { c++; if ($1 > mx) mx=$1; if ($1 < mn) mn=$1; if($1 > 0) { nz++; s += $1; m = s/nz; vs += ($1 - m)^2; v=vs/nz} } END { sd = sqrt(v); printf "{\"count\":%d,\"non-zero\":%d,\"min\":%d,\"max\":%d,\"sum\":%d,\"mean\":%f,\"stdev\":%f}\n", c, nz, mn, mx, s, m, sd  }'
        echo "+++" >>! $TMP/LOG
    else
        echo -n "+++ CALCULATING day ($day) " >>! $TMP/LOG
	@ i = 0
	echo '{ "days": ['
	while ($i < 7)
	    if ($i > 0) echo ","
	    cat "$JSON" | /usr/local/bin/jq -c '.days['$i'].intervals[].count' | sed 's/"//g' | \
		/usr/local/bin/gawk 'BEGIN { mx=0; mn= 0; nz=0;c=0; s = 0;v=0 } { c++; if ($1 > mx) mx=$1; if ($1 < mn) mn=$1; if($1 > 0) { nz++; s += $1; m = s/nz; vs += ($1 - m)^2; v=vs/nz} } END { sd = sqrt(v); printf "{\"count\":%d,\"non-zero\":%d,\"min\":%d,\"max\":%d,\"sum\":%d,\"mean\":%f,\"stdev\":%f}", c, nz, mn, mx, s, m, sd  }'
	    @ i++
	end
	echo "]}"
        echo "+++" >>! $TMP/LOG
	rm -f "$TMP/$APP-$API.$$.json"
    endif
# test interval
else if ($?interval) then
    if ($interval != "all") then
        echo "+++ CALCULATING interval ($interval)" >>! $TMP/LOG
	cat "$JSON" | /usr/local/bin/jq -c '.days[].intervals['$interval'].count' | sed 's/"//g' | \
	    /usr/local/bin/gawk 'BEGIN { mx=0; mn= 0; nz=0;c=0; s = 0 ;v=0} { c++; if ($1 > mx) mx=$1; if ($1 < mn) mn=$1; if($1 > 0) { nz++; s += $1; m = s/nz; vs += ($1 - m)^2; v=vs/nz} } END { sd = sqrt(v); printf "{\"count\":%d,\"non-zero\":%d,\"min\":%d,\"max\":%d,\"sum\":%d,\"mean\":%f,\"stdev\":%f}\n", c, nz, mn, mx, s, m, sd  }'
    else
        echo "+++ CALCULATING interval ($interval)" >>! $TMP/LOG
	@ i = 0
	echo '{ "intervals": ['
	while ($i < 96)
	    if ($i > 0) echo ","
	    cat "$JSON" | /usr/local/bin/jq -c '.days[].intervals['$i'].count' | sed 's/"//g' | \
		/usr/local/bin/gawk 'BEGIN { mx=0; mn= 0; nz=0;c=0; s = 0;v=0 } { c++; if ($1 > mx) mx=$1; if ($1 < mn) mn=$1; if($1 > 0) { nz++; s += $1; m = s/nz; vs += ($1 - m)^2; v=vs/nz} } END { sd = sqrt(v); printf "{\"count\":%d,\"non-zero\":%d,\"min\":%d,\"max\":%d,\"sum\":%d,\"mean\":%f,\"stdev\":%f}", c, nz, mn, mx, s, m, sd  }'
	    @ i++
	end
	echo "]}"
	rm -f "$TMP/$APP-$API.$$.json"
    endif
else
    cat "$JSON" | /usr/local/bin/jq -c '.days[].intervals[]'
endif

# all done
done:
    echo ""
