#!/bin/csh -fb
setenv APP "aah"
setenv API "images"
setenv LAN "192.168.1"
setenv WWW "www.dcmartin.com"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

# don't update output more than once per (in seconds)
setenv TTL 30
setenv SECONDS `date "+%s"`
setenv DATE `echo $SECONDS \/ $TTL \* $TTL | bc`

# default image limit
if ($?IMAGE_LIMIT == 0) setenv IMAGE_LIMIT 100


if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($DB == "$QUERY_STRING") unset DB
    set class = `echo "$QUERY_STRING" | sed 's/.*id=\([^&]*\).*/\1/'`
    if ($class == "$QUERY_STRING") unset class
    set match = `echo "$QUERY_STRING" | sed 's/.*match=\([^&]*\).*/\1/'`
    if ($match == "$QUERY_STRING") unset match
    set limit = `echo "$QUERY_STRING" | sed 's/.*limit=\([^&]*\).*/\1/'`
    if ($limit == "$QUERY_STRING") unset limit
endif

#
# defaults (rough-fog; NO_TAGS; <this-month>*)
#
if ($?DB == 0) set DB = rough-fog
if ($?class == 0) set class = NO_TAGS
if ($?match == 0) set match = `date '+%Y%m'`
if ($?limit == 0) set limit = $IMAGE_LIMIT

# standardize QUERY_STRING to cache results
setenv QUERY_STRING "db=$DB&id=$class&match=$match&limit=$limit"

echo `date` "$0 $$ - START ($QUERY_STRING)" >>! $TMP/LOG

# output set
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

# check OUTPUT exists
if (-s "$OUTPUT") then
    echo `date` "$0 $$ -- existing ($OUTPUT)" >>! $TMP/LOG
    goto output
else if ($?USE_OLD_OUTPUT) then
    echo `date` "$0 $$ ++ requesting ($OUTPUT)" >>! $TMP/LOG
    ./$APP-make-$API.bash
    set old = ( `find "$TMP/" -name "$APP-$API-$QUERY_STRING.*.json" -print | sort -t . -k 2,2 -n -r` )
    if ($#old > 0) then
        set OUTPUT = $old[1]
	echo `date` "$0 $$ -- using old output ($OUTPUT)" >>! $TMP/LOG
	setenv DATE `echo "$OUTPUT" | awk -F. '{ print $2 }'`
	if ($#old > 1) then
	    echo `date` "$0 $$ -- removing old output ($old[2-])" >>! $TMP/LOG
	    rm -f $old[2-]
	endif
	goto output
    endif
    # return redirect
    set URL = "https://$CU/$DB-$API/$class-images"
    echo `date` "$0 $$ -- returning redirect ($URL)" >>! $TMP/LOG
    set age = `echo "$SECONDS - $DATE" | bc`
    set refresh = `echo "$TTL - $age | bc`
    echo "Age: $age"
    echo "Refresh: $refresh"
    echo "Cache-Control: max-age=$TTL"
    echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
    echo "Status: 302 Found"
    echo "Location: $URL"
    echo ""
    goto done
else
    set old = ( `find "$TMP/" -name "$APP-$API-$QUERY_STRING.*.json" -print | sort -t . -k 2,2 -n -r` )
    if ($#old > 0) then
	echo `date` "$0 $$ -- removing old output ($old)" >>! $TMP/LOG
	rm -f $old
    endif
    # get review information (hmmm..)
    set REVIEW = "$TMP/$APP-$API.$$.review.json"
    echo `date` "$0 $$ -- get http://$WWW/CGI/aah-review.cgi?db=$DB" >>! $TMP/LOG
    curl -L -s -q "http://$WWW/CGI/aah-review.cgi?db=$DB" -o "$REVIEW"
    if ($status == 0 && (-s "$REVIEW")) then
	echo -n `date` "$0 $$ -- got " >>! $TMP/LOG
	/usr/local/bin/jq -c '.' "$REVIEW" >>! $TMP/LOG
    else
	echo `date` "$0 $$ -- fail ($REVIEW)" >>! $TMP/LOG
	cat "$REVIEW" >>! $TMP/LOG
	rm -f "$REVIEW"
	goto done
    endif

    # get seqid 
    set seqid = ( `/usr/local/bin/jq '.seqid' "$REVIEW"` )
    if ($seqid == "null") then
	echo `date` "$0 $$ -- no sequence id" >>! $TMP/LOG
    endif
    # get seqid 
    set date = ( `/usr/local/bin/jq '.date' "$REVIEW" | sed 's/"//g'` )
    if ($date == "null") then
	echo `date` "$0 $$ -- no date" >>! $TMP/LOG
    endif

    # calculate expected class list
    set allclasses = ( `/usr/local/bin/jq '.classes[]|.name' "$REVIEW" | sed 's/"//g'` )

    echo `date` "$0 $$ -- found $#allclasses classes" >>! $TMP/LOG

    # search for matching class
    set i = all
    foreach i ( $allclasses )
        if ($i == $class) break
    end
    if ($i != $class && $class != all) then
	echo `date` "$0 $$ -- no matching class ($class)" >>! $TMP/LOG
        goto done
    endif

    # new output
    set NEW = "$OUTPUT.$$"
    echo -n '{ "seqid":'$seqid',"date":"'$date'","device":"'"$DB"'","match":"'"$match"'","class":"'"$class"'","limit":"'"$limit"'","images":[' >> "$NEW"

    if ($class == all) then
        set CDIR = "$TMP/$DB"
    else
	set CDIR = "$TMP/$DB/$class"
    endif
    if (-d "$CDIR") then
	echo `date` "$0 $$ -- finding images in ($CDIR) matching ($match)" >>! $TMP/LOG
	@ k = 0
	foreach j ( `find "$CDIR" -name "$match*" -print | sort -t / -k 7,7 -n -r` )
	    if ($k < $limit) then
		echo `date` "$0 $$ -- file ($j)" >>! $TMP/LOG
		if ($k > 0) echo -n "," >> "$NEW"
		if ($class == all) then
		    echo -n '"'$j:h:t/$j:t'"' >> "$NEW"
		else
		    echo -n '"'$j:t'"' >> "$NEW"
		endif
	    endif
	    @ k++
	end
	echo '],"count":'$k' }' >> "$NEW"
	echo `date` "$0 $$ -- found $k images" >>! $TMP/LOG
    else
	echo `date` "$0 $$ -- directory $CDIR does not exist" >>! $TMP/LOG
	echo '],"count":0 }' >> "$NEW"
    endif
    # cleanup 
    echo `date` "$0 $$ -- removing $REVIEW" >>! $TMP/LOG
    rm -f "$REVIEW"
    # create new OUTPUT
    mv "$NEW" "$OUTPUT"
endif

output:

#
# prepare for output
#
echo "Content-Type: application/json; charset=utf-8"
echo "Access-Control-Allow-Origin: *"
set age = `echo "$SECONDS - $DATE" | bc`
set refresh = `echo "$TTL - $age" | bc`
echo "Age: $age"
echo "Refresh: $refresh"
echo "Cache-Control: max-age=$TTL"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
echo ""
/usr/local/bin/jq -c '.' "$OUTPUT"

#
# all done
#
done:

echo `date` "$0 $$ -- FINISH ($QUERY_STRING)" >>! $TMP/LOG
