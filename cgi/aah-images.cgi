#!/bin/csh -fb
setenv APP "aah"
setenv API "images"
setenv LAN "192.168.1"
setenv WWW "www.dcmartin.com"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

# don't update statistics more than once per 12 hours
set TTL = `echo "12 * 60 * 60" | bc`
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo "BEGIN: $APP-$API ($0 $$) - " $DATE >>! $TMP/LOG

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($DB == "$QUERY_STRING") unset DB
    set class = `echo "$QUERY_STRING" | sed 's/.*id=\([^&]*\).*/\1/'`
    if ($class == "$QUERY_STRING") unset class
    set match = `echo "$QUERY_STRING" | sed 's/.*match=\([^&]*\).*/\1/'`
    if ($match == "$QUERY_STRING") unset match
endif

#
# defaults (rough-fog; NO_TAGS; <this-month>*)
#
if ($?DB == 0) set DB = rough-fog
if ($?class == 0) set class = NO_TAGS
if ($?match == 0) set match = `date '+%Y%m'`

# hard image limit
if ($?IMAGE_LIMIT == 0) setenv IMAGE_LIMIT 100

# standardize QUERY_STRING to cache results
setenv QUERY_STRING "db=$DB&id=$class&match=$match"

# output set
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

# check OUTPUT exists
if (-e "$OUTPUT") then
    echo "DEBUG: $APP-$API ($0 $$) -- existing ($OUTPUT)" >>! $TMP/LOG
    goto output
else
    # cleanup errant directories
    rmdir "$TMP/$DB/"* >&! /dev/null

    # get review information (hmmm..)
    set REVIEW = "$TMP/$APP-$API-review.$$.json"
    curl -L -s -q "http://$WWW/CGI/aah-review.cgi?db=$DB" >! "$REVIEW"
    if ($status != 0) then
	echo "DEBUG: $APP-$API ($0 $$) -- ERROR: $REVIEW" >>! $TMP/LOG
	goto done
    else
	echo "DEBUG: $APP-$API ($0 $$) -- SUCCESS: $REVIEW" >>! $TMP/LOG
    endif
    # get seqid 
    set seqid = ( `/usr/local/bin/jq '.seqid' "$REVIEW"` )

    # calculate expected class list
    set classes = ( `/usr/local/bin/jq '.classes[]|.name' "$REVIEW" | sed 's/"//g'` )

    echo "DEBUG: $APP-$API ($0 $$) -- CLASSES: $#classes" >>! $TMP/LOG

    foreach i ( $classes )
        if ($i == $class) break
    end
    if ($i != $class) then
	echo "DEBUG: $APP-$API ($0 $$) -- NO CLASS: $class" >>! $TMP/LOG
        goto done
    endif

    set NEW = "$OUTPUT.$$"
    set CDIR = "$TMP/$DB/$class"

    echo -n '{ "seqid":'$seqid',"device":"'"$DB"'","match":"'"$match"'","class":"'"$class"'",' >! "$NEW"
    if (-d "$CDIR") then
	echo "DEBUG: $APP-$API ($0 $$) -- FILES: $CDIR/$match*" >>! $TMP/LOG
	set files = ( `/bin/ls -1r "$CDIR/$match"*` )
	echo "DEBUG: $APP-$API ($0 $$) -- FILES: $#files" >>! $TMP/LOG
	echo -n '"count":'$#files',' >> "$NEW"
	@ k = 0
	echo -n '"images":[' >> "$NEW"
	foreach j ( $files )
	    if ($k > 0) echo -n "," >> "$NEW"
	    # echo -n '"http://'"$WEB/$APP/$DB/$j:t"'"' >> "$NEW"
	    echo -n '"'$j:t'"' >> "$NEW"
	    @ k++
	    if ($?IMAGE_LIMIT) then
		if ($k > $IMAGE_LIMIT) then
		    echo "DEBUG: $APP-$API ($0 $$) -- IMAGE LIMIT EXCEEDED: $k of $#files" >>! $TMP/LOG
		    break
		endif
	    endif
	end
	echo "] }" >> "$NEW"
    else
	echo -n '"count":0',' >> "$NEW"
	echo -n '"images":[' >> "$NEW"
	echo "] }" >> "$NEW"
    endif
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

# all done
done:

rm -f "$TMP/$APP-$API*$$*"
echo "FINISH: $APP-$API ($0 $$) - " $DATE >>! $TMP/LOG
