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

echo `date` "$0 $$ - START" >>! $TMP/LOG

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
setenv QUERY_STRING "db=$DB&id=$class&match=$match"

# output set
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

# check OUTPUT exists
if (-e "$OUTPUT") then
    echo `date` "$0 $$ -- returning existing ($OUTPUT)" >>! $TMP/LOG
    goto output
else
    # get review information (hmmm..)
    set REVIEW = "$TMP/$APP-$API.$$.review.json"
    echo `date` "$0 $$ -- curl aah-review $DB ($REVIEW)" >>! $TMP/LOG
    curl -L -s -q "http://$WWW/CGI/aah-review.cgi?db=$DB" >! "$REVIEW"
    if ($status == 0 && (-s "$REVIEW")) then
	echo `date` "$0 $$ -- success ($REVIEW)" >>! $TMP/LOG
    else
	echo `date` "$0 $$ -- failure ($REVIEW)" >>! $TMP/LOG
	goto done
    endif

    # get seqid 
    set seqid = ( `/usr/local/bin/jq '.seqid' "$REVIEW"` )
    if ($seqid == "null") then
	echo `date` "$0 $$ -- no sequence id" >>! $TMP/LOG
    endif

    # calculate expected class list
    set classes = ( `/usr/local/bin/jq '.classes[]|.name' "$REVIEW" | sed 's/"//g'` )

    echo `date` "$0 $$ -- found $#classes classes" >>! $TMP/LOG

    # search for matching class
    foreach i ( $classes )
        if ($i == $class) break
    end
    if ($i != $class) then
	echo `date` "$0 $$ -- no matching class ($class" >>! $TMP/LOG
        goto done
    endif

    # new output
    set NEW = "$OUTPUT.$$"
    echo -n '{ "seqid":'$seqid',"date":"'`date`'","device":"'"$DB"'","match":"'"$match"'","class":"'"$class"'",' >! "$NEW"

    set CDIR = "$TMP/$DB/$class"
    if (-d "$CDIR") then
	echo `date` "$0 $$ -- finding images in ($CDIR) matching ($match)" >>! $TMP/LOG
	echo -n '"images":[' >> "$NEW"
	@ k = 0
	foreach j ( `find "$CDIR" -name "$match*" -print` )
	    if ($k < $IMAGE_LIMIT) then
		if ($k > 0) echo -n "," >> "$NEW"
		echo -n '"'$j:t'"' >> "$NEW"
	    endif
	    @ k++
	end
	echo '],"count":'$k' }' >> "$NEW"
	echo `date` "$0 $$ -- found $k images" >>! $TMP/LOG
    else
	echo `date` "$0 $$ -- directory $CDIR does not exist" >>! $TMP/LOG
	echo -n '"count":0',' >> "$NEW"
	echo -n '"images":[' >> "$NEW"
	echo "] }" >> "$NEW"
    endif
    # cleanup 
    echo `date` "$0 $$ -- removing $REVIEW and any old $OUTPUT:r:r" >>! $TMP/LOG
    rm -f "$REVIEW"
    rm -f "$OUTPUT:r:r".*.json
    # create new OUTPUT
    mv "$NEW" "$OUTPUT"
endif

output:

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

#
# all done
#
done:

echo `date` "$0 $$ - FINISH" >>! $TMP/LOG
