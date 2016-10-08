#!/bin/csh -fb
setenv APP "aah"
setenv API "review"
setenv WWW "http://www.dcmartin.com/CGI/"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"
setenv LANIP "192.168.1.34"

# don't update statistics more than once per 12 hours
set TTL = `echo "12 * 60 * 60" | bc`
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo ">>> $APP-$API ($0 $$) - BEGIN" $DATE >>! $TMP/LOG

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
if ($?class == 0) set class = all
setenv QUERY_STRING "db=$DB&id=$class"

# output set
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
set INPROGRESS = ( `echo "$OUTPUT".*` )

# check OUTPUT in-progress for current interval
if ($#INPROGRESS) then
    echo "+++ $APP-$API ($0 $$) -- in-progress ($INPROGRESS)" >>! $TMP/LOG
    goto done
else
    echo "$APP-$API ($0 $$) ++ MAKING ($OUTPUT)" >>! $TMP/LOG
    ./$APP-make-$API.bash
    # find old results
    set OLD = ( `ls -1t "$TMP/$APP-$API-$QUERY_STRING".*.json` )
    if ($#OLD == 0) then
	# note change in DATE to last TTL interval (not necessarily the same as statistics interval, independent)
	set DATE = `echo "(($SECONDS - $TTL ) / $TTL) * $TTL" | bc`
	set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
        if (! -e "$OUTPUT") then
	    echo "$APP-$API ($0 $$) << RETRIEVING ($OUTPUT)" >>! $TMP/LOG
	    curl -s -q -o "$OUTPUT" "https://$CU/$DB-$API/$class"
	endif
	set ERROR = `/usr/local/bin/jq '.error' "$OUTPUT" | sed 's/"//g'`
	if ($ERROR == "not_found") then
	    echo "$APP-$API ($0 $$) ** ERROR ($ERROR)" >>! $TMP/LOG
	    exit
        endif
    else if ($#OLD > 0) then
	echo "$APP-$API ($0 $$) == OLD $OUTPUT ($OLD)" >>! $TMP/LOG
	set OUTPUT = "$OLD[1]"
	if ($#OLD > 1) then
	    echo "$APP-$API ($0 $$) -- DELETING $OLD[2-]" >>! $TMP/LOG
	    /bin/rm -f "$OLD[2-]"
	endif
    endif
endif

if ($#OUTPUT == 0) then
    echo "$APP-$API ($0 $$) ** NONE ($OUTPUT)" >>! $TMP/LOG
    echo "Status: 202 Accepted"
    goto done
else if (-e "$OUTPUT") then
    echo "$APP-$API ($0 $$) --" `ls -al $OUTPUT` >>! $TMP/LOG
endif

#
# prepare for output
#
echo "Content-Type: application/json; charset=utf-8"
echo "Access-Control-Allow-Origin: *"
set AGE = `echo "$SECONDS - $DATE" | bc`
echo "Age: $AGE"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo ""

cat "$OUTPUT"
exit

if ($?day && $?interval) then
    if ($day == "all" && $interval == "all") then
        echo "+++ CALCULATING day ($day) and interval ($interval)" >>! $TMP/LOG
        # get images for all days across all intervals
    	goto done
    else if ($day != "all" && $interval != "all") then
        echo "+++ CALCULATING day ($day) and interval ($interval)" >>! $TMP/LOG
	# get specific interval
	goto done
    endif
endif

if ($?day) then
    if ($day != "all") then
        echo -n "+++ RETRIEVING day ($day) " >>! $TMP/LOG
        echo "+++" >>! $TMP/LOG
    else
        echo -n "+++ RETRIEVING day ($day) " >>! $TMP/LOG
	@ i = 0
	echo '{ "days": ['
	while ($i < 7)
	    if ($i > 0) echo ","
	    @ i++
	end
	echo "]}"
        echo "+++" >>! $TMP/LOG
	rm -f "$TMP/$APP-$API.$$.json"
    endif
# test interval
else if ($?interval) then
    if ($interval != "all") then
        echo "+++ RETRIEVING interval ($interval)" >>! $TMP/LOG
    else
        echo "+++ RETRIEVING interval ($interval)" >>! $TMP/LOG
	@ i = 0
	echo '{ "intervals": ['
	while ($i < 96)
	    if ($i > 0) echo ","
	    @ i++
	end
	echo "]}"
	rm -f "$TMP/$APP-$API.$$.json"
    endif
else
    cat "$OUTPUT" | /usr/local/bin/jq -c '.days[].intervals[]'
endif

# all done
done:
    echo ""
