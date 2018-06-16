#!/bin/tcsh -b
setenv APP "aah"
setenv API "stats"

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

# don't update statistics more than once per TTL seconds
set TTL = 3600
set SECONDS = `date "+%s"`
set DATE = `/bin/echo $SECONDS \/ $TTL \* $TTL | bc`

/bin/echo `date` "$0 $$ -- START" >>&! $LOGTO

##
## ACCESS CLOUDANT
##
if ($?CLOUDANT_URL) then
  set CU = $CLOUDANT_URL
else if (-s $CREDENTIALS/.cloudant_url) then
  set cc = ( `cat $CREDENTIALS/.cloudant_url` )
  if ($#cc > 0) set CU = $cc[1]
  # if ($#cc > 1) set CN = $cc[2]
  # if ($#cc > 2) set CP = $cc[3]
  if ($?CP && $?CN && $?CU) then
    set CU = 'https://'"$CN"':'"$CP"'@'"$CU"
  else if ($?CU) then
    set CU = "https://$CU"
  endif
else
  /bin/echo `date` "$0:t $$ -- FAILURE: no Cloudant credentials" >>&! $LOGTO
  goto done
endif

if ($?QUERY_STRING) then
    set DB = `/bin/echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($DB == "$QUERY_STRING") unset DB
    set class = `/bin/echo "$QUERY_STRING" | sed 's/.*id=\([^&]*\).*/\1/'`
    if ($class == "$QUERY_STRING") unset class
    set day = `/bin/echo "$QUERY_STRING" | sed 's/.*day=\([^&]*\).*/\1/'`
    if ($day == "$QUERY_STRING") unset day
    set interval = `/bin/echo "$QUERY_STRING" | sed 's/.*interval=\([^&]*\).*/\1/'`
    if ($interval == "$QUERY_STRING") unset interval
endif

if ($?DB == 0) set DB = rough-fog
if ($?class == 0) set class = person
setenv QUERY_STRING "db=$DB&id=$class"

/bin/echo -n `date` "$0 $$ -- db=$DB id=$class " >>&! $LOGTO
if ($?day) then
    /bin/echo -n "day=$day " >>&! $LOGTO
else
    /bin/echo -n "day=<unset> " >>&! $LOGTO
endif
if ($?interval) then
    /bin/echo -n "interval=$interval" >>&! $LOGTO
else
    /bin/echo -n "interval=<unset> " >>&! $LOGTO
endif
/bin/echo "" >>&! $LOGTO

set JSON = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

if (-e "$JSON") then
    /bin/echo `date` "$0 $$ == CURRENT $JSON $DATE" >>&! $LOGTO
else
    /bin/echo `date` "$0 $$ ++ MAKING ($JSON)" >>&! $LOGTO
    ./$APP-make-$API.bash
    # find old results
    set OLD_JSON = ( `ls -1t "$TMP/$APP-$API-$QUERY_STRING".*.json` )
    if ($#OLD_JSON == 0) then
	# note change in DATE to last TTL interval (not necessarily the same as statistics interval, independent)
	set DATE = `/bin/echo "(($SECONDS - $TTL ) / $TTL) * $TTL" | bc`
	set JSON = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
        if (! -e "$JSON") then
	    /bin/echo `date` "$0 $$ -- RETRIEVING ($JSON)" >>&! $LOGTO
	    curl -s -q -o "$JSON" "https://$CU/$DB-$API/$class"
	endif
	set ERROR = `jq '.error' "$JSON" | sed 's/"//g'`
	if ($ERROR == "not_found") then
	    /bin/echo `date` "$0 $$ -- ERROR ($ERROR)" >>&! $LOGTO
            rm -f "$JSON"
	    exit
        endif
    else if ($#OLD_JSON > 0) then
	/bin/echo `date` "$0 $$ == OLD $JSON ($OLD_JSON)" >>&! $LOGTO
	set JSON = "$OLD_JSON[1]"
	if ($#OLD_JSON > 1) then
	    /bin/echo `date` "$0 $$ -- DELETING $OLD_JSON[2-]" >>&! $LOGTO
	    /bin/rm -f "$OLD_JSON[2-]"
	endif
    endif
endif

if ($#JSON == 0) then
    /bin/echo `date` "$0 $$ ** NONE ($JSON)" >>&! $LOGTO
    /bin/echo "Status: 202 Accepted"
    goto done
else if (-e "$JSON") then
    /bin/echo `date` "$0 $$ --" `ls -al $JSON` >>&! $LOGTO
endif

#
# prepare for output
#
/bin/echo "Content-Type: application/json; charset=utf-8"
/bin/echo "Access-Control-Allow-Origin: *"
set AGE = `/bin/echo "$SECONDS - $DATE" | bc`
/bin/echo "Age: $AGE"
/bin/echo "Cache-Control: max-age=$TTL"
/bin/echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
/bin/echo ""

if ($?day && $?interval) then
    if ($day == "all" && $interval == "all") then
        /bin/echo `date` "$0 $$ -- CALCULATING day ($day) and interval ($interval)" >>&! $LOGTO
        # get statistics for all days across all intervals
	cat "$JSON" | jq -c '.days[].intervals[].count' | sed 's/"//g' | \
	    gawk 'BEGIN { mx=0; mn=0; c=0; nz=0; s=0;v=0 } { c++; if ($1 > mx) mx=$1; if ($1 < mn) mn=$1; if($1 > 0) { nz++; s += $1; m = s/nz; vs += ($1 - m)^2; v=vs/nz} } END { sd = sqrt(v); printf "{\"count\":%d,\"non-zero\":%d,\"min\":%d,\"max\":%d,\"sum\":%d,\"mean\":%f,\"stdev\":%f}\n", c, nz, mn, mx, s, m, sd  }'
    	goto done
    else if ($day != "all" && $interval != "all") then
        /bin/echo `date` "$0 $$ -- CALCULATING day ($day) and interval ($interval)" >>&! $LOGTO
	# get specific interval
	cat "$JSON" | jq -c '.days['$day'].intervals['$interval']'
	goto done
    endif
endif

if ($?day) then
    if ($day != "all") then
        /bin/echo -n `date` "$0 $$ -- CALCULATING day ($day) " >>&! $LOGTO
	cat "$JSON" | jq -c '.days['$day'].intervals[].count' | sed 's/"//g' | \
	    gawk 'BEGIN { mx=0; mn=100; nz=0; c=0; s=0;v=0 } { c++; if ($1 > mx) mx=$1; if ($1 < mn) mn=$1; if($1 > 0) { nz++; s += $1; m = s/nz; vs += ($1 - m)^2; v=vs/nz} } END { sd = sqrt(v); printf "{\"count\":%d,\"non-zero\":%d,\"min\":%d,\"max\":%d,\"sum\":%d,\"mean\":%f,\"stdev\":%f}\n", c, nz, mn, mx, s, m, sd  }'
        /bin/echo "+++" >>&! $LOGTO
    else
        /bin/echo -n `date` "$0 $$ -- CALCULATING day ($day) " >>&! $LOGTO
	@ i = 0
	/bin/echo '{ "days": ['
	while ($i < 7)
	    if ($i > 0) /bin/echo ","
	    cat "$JSON" | jq -c '.days['$i'].intervals[].count' | sed 's/"//g' | \
		gawk 'BEGIN { mx=0; mn=100; nz=0;c=0; s = 0;v=0 } { c++; if ($1 > mx) mx=$1; if ($1 < mn) mn=$1; if($1 > 0) { nz++; s += $1; m = s/nz; vs += ($1 - m)^2; v=vs/nz} } END { sd = sqrt(v); printf "{\"count\":%d,\"non-zero\":%d,\"min\":%d,\"max\":%d,\"sum\":%d,\"mean\":%f,\"stdev\":%f}", c, nz, mn, mx, s, m, sd  }'
	    @ i++
	end
	/bin/echo "]}"
        /bin/echo "+++" >>&! $LOGTO
	rm -f "$TMP/$APP-$API.$$.json"
    endif
# test interval
else if ($?interval) then
    if ($interval != "all") then
        /bin/echo `date` "$0 $$ -- CALCULATING interval ($interval)" >>&! $LOGTO
	cat "$JSON" | jq -c '.days[].intervals['$interval'].count' | sed 's/"//g' | \
	    gawk 'BEGIN { mx=0; mn=100; nz=0;c=0; s = 0 ;v=0} { c++; if ($1 > mx) mx=$1; if ($1 < mn) mn=$1; if($1 > 0) { nz++; s += $1; m = s/nz; vs += ($1 - m)^2; v=vs/nz} } END { sd = sqrt(v); printf "{\"count\":%d,\"non-zero\":%d,\"min\":%d,\"max\":%d,\"sum\":%d,\"mean\":%f,\"stdev\":%f}\n", c, nz, mn, mx, s, m, sd  }'
    else
        /bin/echo `date` "$0 $$ -- CALCULATING interval ($interval)" >>&! $LOGTO
	@ i = 0
	/bin/echo '{ "intervals": ['
	while ($i < 96)
	    if ($i > 0) /bin/echo ","
	    cat "$JSON" | jq -c '.days[].intervals['$i'].count' | sed 's/"//g' | \
		gawk 'BEGIN { mx=0; mn=100; nz=0;c=0; s = 0;v=0 } { c++; if ($1 > mx) mx=$1; if ($1 < mn) mn=$1; if($1 > 0) { nz++; s += $1; m = s/nz; vs += ($1 - m)^2; v=vs/nz} } END { sd = sqrt(v); printf "{\"count\":%d,\"non-zero\":%d,\"min\":%d,\"max\":%d,\"sum\":%d,\"mean\":%f,\"stdev\":%f}", c, nz, mn, mx, s, m, sd  }'
	    @ i++
	end
	/bin/echo "]}"
	rm -f "$TMP/$APP-$API.$$.json"
    endif
else
    cat "$JSON" | jq -c '.days[].intervals[]'
endif

/bin/echo ""

# all done
done:

/bin/echo `date` "$0 $$ -- FINISH" >>&! $LOGTO
