#!/bin/csh -fb
onintr done
setenv APP "aah"
setenv API "review"
setenv WWW "http://www.dcmartin.com/CGI/"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

# don't update statistics more than once per 12 hours
set TTL = `echo "12 * 60 * 60" | bc`
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo ">>> $APP-$API ($0 $$) - BEGIN" `date` >>! $TMP/LOG

if (-e ~$USER/.cloudant_url) then
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
    echo "+++ $APP-$API ($0 $$) -- no Cloudant URL" >>! $TMP/LOG
    goto done
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

#
# defaults to rough-fog (kitchen) and all classes
#
if ($?DB == 0) set DB = rough-fog
if ($?class == 0) set class = all
setenv QUERY_STRING "db=$DB&id=$class"

if ($DB == "rough-fog") then
    setenv LANIP "192.168.1.34"
else if ($DB == "damp-cloud") then
    setenv LANIP "192.168.1.35"
else
    echo "+++ $APP-$API ($0 $$) -- no LANIP" >>! $TMP/LOG
    goto done
endif

# output set
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
set INPROGRESS = ( `echo "$OUTPUT".*` )

# check OUTPUT in-progress for current interval
if ($#INPROGRESS) then
    echo "+++ $APP-$API ($0 $$) - In-progress $OUTPUT" >>! $TMP/LOG
    exit
endif

#
# download old result
#
set OLD = "$OUTPUT".$$
echo "+++ $APP-$API ($0 $$) -- getting OLD ($OLD)" >>! $TMP/LOG
curl -s -q -o "$OLD" -X GET "$CU/$DB-$API/$class"
# check iff successful
set CLASS_DB = `/usr/local/bin/jq '._id' "$OLD" | sed 's/"//g'`
if ($CLASS_DB != $class) then
    echo "+++ $APP-$API ($0 $$) -- Not found ($CU/$DB-$API/$class)" >>! $TMP/LOG
    set prev_seqid = 0
else
    # get last sequence # for class specified
    set prev_seqid = `/usr/local/bin/jq '.seqid' "$OLD"`
    if ($prev_seqid[1] == "null") set prev_seqid = 0
endif

#
# get CHANGES records
#
set CHANGES = "$OUTPUT:r-changes.json"
set seqid = 0
if ( ! -e "$CHANGES" ) then
    echo "+++ $APP-$API ($0 $$) -- creating $CHANGES" >>! $TMP/LOG
    curl -s -q -o "$CHANGES" "$CU/$DB/_changes?descending=true&include_docs=true&since=$prev_seqid"
    set seqid = ( `/usr/local/bin/jq .last_seq "$CHANGES"` )
    if ($seqid == "null") then
         echo "+++ $APP-$API ($0 $$) -- FAILURE RETRIEVING CHANGES" >>! $TMP/LOG
         exit
    endif
else
    set seqid = ( `/usr/local/bin/jq .last_seq "$CHANGES"` )
    if ($seqid == "null") then
         echo "+++ $APP-$API ($0 $$) -- BAD $CHANGES" >>! $TMP/LOG
         exit
    endif
    set ttyl = `echo "$SECONDS - $DATE" | bc`
    echo "+++ $APP-$API ($0 $$) -- CURRENT: $CHANGES ($TTL) UPDATE $ttyl" >>! $TMP/LOG
endif

set RESULTS = "$OUTPUT:r-results.json"
if (-s "$CHANGES" && (! -s "$RESULTS" || ((-M "$CHANGES") > (-M "$RESULTS")))) then
    echo "+++ $APP-$API ($0 $$) -- CREATING ($RESULTS)" >>! $TMP/LOG
    jq -c '[.results[].doc|{file:.visual.image,tag:.alchemy.text,score:.alchemy.score,year:.year,month:.month,day:.day,hour:.hour,minute:.minute,second:.second}]' "$CHANGES" \
	| jq -c '{results:.[]|[.file,.tag,.score,.year,.month,.day,.hour,.minute,.second]}' \
	| sed 's/"//g' \
	| sed 's/{results:\[//' \
	| sed 's/\]}//' \
	| gawk -F, \
	  '{ m=($7*60+$8)/15; \
	     t=mktime(sprintf("%4d %2d %2d %2d %2d %2d",$4,$5,$6,$7,$8,$9)); \
	     printf("{\"file\":\"%s\",\"tag\":\"%s\",\"score\":%f,\"ampm\":\"%s\",\"day\":\"%s\",\"interval\":%d}\n",$1,$2,$3,strftime("%p",t),strftime("%A",t),m); \
	   }' \
	| sort -r >! "$RESULTS"
else
    echo "+++ $APP-$API ($0 $$) -- CURRENT: $RESULTS ($TTL); UPDATE $ttyl" >>! $TMP/LOG
endif


#
# download images from RESULTS of CHANGES 
#
# { "file": "20160801182222-610-00.jpg", "tag": "NO_TAGS", "score": 0, "ampm": "PM", "day": "Monday", "interval": 73 }
#

# create temporary output for processing sequentially; ignore "ampm"
foreach line ( `jq -c '[.file,.tag,.score,.day,.interval]' "$RESULTS" | sed 's/\[//' | sed 's/\]//' | sed 's/ /_/g' | awk -F, '{ printf("%s,%s,%f,%s,%d\n", $1,$2,$3,$4,$5) }'` )
    set tuple = ( `echo "$line" | sed 's/,/ /g'` )
    if ($#tuple < 2) then
	echo "+++ $APP-$API ($0 $$) -- bad tuple ($tuple) ($line)" >>! $TMP/LOG
	continue
    endif
    set tag = `echo $tuple[2] | sed 's/"//g'`
    if (($tag == $class) || ($class == "all")) then
	# get filename
	set file = `echo $tuple[1] | sed 's/"//g'`
	# build image fullpath
	set image = "$TMP/$DB/$tag/$file"
	# ensure directory exists
	mkdir -p "$image:h"
	# test if image already exists
	if (! -s "$image") then
	    set ftp = "ftp://$LANIP/$file" 
	    curl -s -q "$ftp" -o "$image"
	    if ($status != 0) then
		echo "+++ $APP-$API ($0 $$) -- FAIL ($ftp)" >>! $TMP/LOG
		continue
	    endif
	    if (-s "$image") then
		echo "+++ $APP-$API ($0 $$) -- SUCCESS ($image)" >>! $TMP/LOG
		# optionally delete the source
		if ($?ftp_delete) then
		    echo "+++ $APP-$API ($0 $$) -- deleting ($file)" >>! $TMP/LOG
		    curl -s -q "ftp://$LANIP/" -Q "-DELE $file"
		endif
	   else
		echo "+++ $APP-$API ($0 $$) -- ZERO ($image)" >>! $TMP/LOG
	   endif
	else
	endif
    endif
end

# temporary stop
goto done

#
# update statistics
#
set NEW = "$OLD.$$"
# get current day-of-week
echo "+++ $APP-$API ($0 $$) -- CREATING ($NEW)" >>! $TMP/LOG
echo -n '{ "seqid":'$seqid',"classes":[' >! "$NEW"
set classes = ( `/bin/ls -1 "$TMP/$DB"` )
@ k = 0
foreach i ( $classes )
    if ($k > 0) echo "," >> "$NEW"
    echo -n '"'$i'"' >> "$NEW"
    @ k++
end
echo -n ']', ' >> "$NEW"
@ l = 0
foreach i ( $classes )
    if ($l > 0) echo "," >> "$NEW"
    echo -n '"'$i'":[' >> "$NEW"
    set files = ( `/bin/ls -1 "$TMP/$DB/$i"` )
    @ k = 0
    foreach j ( $files )
	if ($k > 0) echo "," >> "$NEW"
	echo -n '"'$j'", >> "$NEW"
	@ k++
    end
    echo -n ']' >> "$NEW"
    @ l++
end
echo "] }" >> "$NEW"

+
# update Cloudant
#
if ($?CLOUDANT_OFF == 0 && $?CU && $?DB) then
    set DEVICE_DB = `curl -s -q -X GET "$CU/$DB-$API" | /usr/local/bin/jq '.db_name'`
    if ( "$DEVICE_DB" == "null" ) then
        # create DB
        set DEVICE_DB = `curl -s -q -X PUT "$CU/$DB-$API" | /usr/local/bin/jq '.ok'`
        # test for success
        if ( "$DEVICE_DB" != "true" ) then
            # failure
            setenv CLOUDANT_OFF TRUE
        endif
    endif
    if ( $?CLOUDANT_OFF == 0 ) then
        set doc = ( `cat "$OLD" | /usr/local/bin/jq ._id,._rev | sed 's/"//g'` )
        if ($#doc == 2 && $doc[1] == $class && $doc[2] != "") then
            set rev = $doc[2]
            echo "+++ $APP-$API ($0 $$) -- DELETE $rev" >>! $TMP/LOG
            curl -s -q -X DELETE "$CU/$DB-$API/$class?rev=$rev" >>! $TMP/LOG
        endif
        echo "+++ $APP-$API ($0 $$) -- STORE $NEW" >>! $TMP/LOG
        curl -s -q -H "Content-type: application/json" -X PUT "$CU/$DB-$API/$class" -d "@$NEW" >>! $TMP/LOG
    endif
    echo "+++ $APP-$API ($0 $$) -- SUCCESS : $JSON" >>! $TMP/LOG
    # update statistics
    mv -f "$NEW" "$OUTPUT"
    # remove temporary files
    rm -f $OLD
else
    echo "+++ $APP-$API ($0 $$) -- No CLOUDANT update" >>! $TMP/LOG
endif

#
# CLEANUP
#

done:
    onintr -
    /bin/rm -f "$OUTPUT".*
