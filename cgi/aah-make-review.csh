#!/bin/csh -fb
setenv APP "aah"
setenv API "review"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

if ($?TTL == 0) set TTL = 900
if ($?SECONDS == 0) set SECONDS = `date "+%s"`
if ($?DATE == 0) set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

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
    echo `date` "$0 $$ -- no Cloudant URL" >>! $TMP/LOG
    goto done
endif

#
# defaults to rough-fog (kitchen) and all classes
#
if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($DB == "$QUERY_STRING") unset DB
endif

if ($?DB == 0) set DB = rough-fog
if ($?class == 0) set class = all
# standardize QUERY_STRING
setenv QUERY_STRING "db=$DB&id=$class"

echo `date` "$0 $$ -- START ($QUERY_STRING)"  >>! $TMP/LOG

# output target
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
set INPROGRESS = ( `echo "$OUTPUT".*` )
# check OUTPUT in-progress for current interval
if ($#INPROGRESS) then
    echo `date` "$0 $$ -- in-progress $DATE" >>! $TMP/LOG
    goto done
else
    onintr done
    touch "$OUTPUT".$$
endif

if ($DB == "rough-fog" && $?LANIP == 0) then
    setenv LANIP "192.168.1.34"
else if ($DB == "damp-cloud" && $?LANIP == 0) then
    setenv LANIP "192.168.1.35"
else
    echo `date` "$0 $$ -- no LANIP" >>! $TMP/LOG
    goto done
endif

# check for old OUTPUT
set old = ( `find "$TMP/" -name "$APP-$API-$QUERY_STRING.*.json" -print | sort -t . -k 2,2 -n -r` )
if ($#old > 0) then
    set OLD = $old[1]
    echo `date` "$0 $$ -- found old results ($OLD)" >>! $TMP/LOG
    if ($#old > 1) then
	echo `date` "$0 $$ -- removing old results ($old[2-])" >>! $TMP/LOG
	rm -f $old[2-]
    endif
    # test old
    set class_id = `/usr/local/bin/jq '._id' "$OLD" | sed 's/"//g'`
    if ($class_id != $class) then
	echo `date` "$0 $$ -- bad results ($OLD)" >>! $TMP/LOG
	rm -f "$OLD"
    else
	echo `date` "$0 $$ -- results match ($class_id == $class)" >>! $TMP/LOG
    endif
endif

#
set prev_seqid = 0
# if we don't find it locally, download
if ($?OLD == 0) then
    # create temporary file
    set OLD = "$TMP/$APP-$API-$class.$$.json"
    echo `date` "$0 $$ -- get OLD ($CU/$DB-$API/$class)" >>! $TMP/LOG
    /usr/bin/curl -s -q -o "$OLD" -X GET "$CU/$DB-$API/$class"
    if ($status == 0 && (-s "$OLD")) then
	echo `date` "$0 $$ -- got OLD ($OLD)" >>! $TMP/LOG
	set class_id = `/usr/local/bin/jq '._id' "$OLD" | sed 's/"//g'`
	if ($class_id != $class) then
	    echo `date` "$0 $$ -- DB ($class_id) != ID ($class)" >>! $TMP/LOG
	    rm -f "$OLD"
	    set prev_seqid = 0
	else
	    # get prev_seqid
	    echo `date` "$0 $$ -- match found ($class_id == $class)" >>! $TMP/LOG
	    # get last sequence for old output
	    set prev_seqid = `/usr/local/bin/jq '.seqid' "$OLD" | sed 's/"//g'`
	    if ($status == 0) then
		echo `date` "$0 $$ -- OLD seqid ($prev_seqid)" >>! $TMP/LOG
		set date = `/usr/local/bin/jq '.date' "$OLD" | sed 's/"//g'`
		mv "$OLD" "$TMP/$APP-$API-$QUERY_STRING.$date.json"
	    else
		echo `date` "$0 $$ -- invalid OLD ($OLD; $prev_seqid)" >>! $TMP/LOG
	        rm -f "$OLD"
		set prev_seqid = 0
	    endif
	endif
    else
	echo `date` "$0 $$ ** failure getting $CU/$DB-$API/$class" >>! $TMP/LOG
	set prev_seqid = 0
	rm -f "$OLD"
        goto done
    endif
endif

echo `date` "$0 $$ -- prev_seqid ($prev_seqid)" >>! $TMP/LOG

#
# get CHANGES records
#
set CHANGES = "$TMP/$APP-$API-$QUERY_STRING-changes.$DATE.json"
set seqid = $prev_seqid
if ( ! -e "$CHANGES" ) then
    echo `date` "$0 $$ -- get changes ($CU/$DB/_changes?descending=true&include_docs=true&since=$prev_seqid" >>! $TMP/LOG
    /usr/bin/curl -s -q -o "$CHANGES" "$CU/$DB/_changes?descending=true&include_docs=true&since=$prev_seqid" >>&! $TMP/LOG
    echo `date` "$0 $$ -- got ($CHANGES)" >>! $TMP/LOG
    set seqid = ( `/usr/local/bin/jq .last_seq "$CHANGES" | sed 's/"//g'` )
    if ($seqid == "null") then
         echo `date` "$0 $$ -- failure processing changes" >>! $TMP/LOG
         goto done
    endif
    # remove old changes
    set old = ( `find "$TMP/" -name "$APP-$API-$QUERY_STRING-changes.*.json" -print | sort -t . -k 2,2 -n -r` )
    if ($#old > 1) then
	echo `date` "$0 $$ -- removing old changes ($old[2-])" >>! $TMP/LOG
	rm -f $old[2-]
    endif
else
    echo `date` "$0 $$ -- changes are current ($TTL) update in " `echo "$SECONDS - $DATE" | bc` >>! $TMP/LOG
endif
set seqid = ( `/usr/local/bin/jq .last_seq "$CHANGES" | sed 's/"//g'` )
if ($#seqid == 0 || $seqid == "null") then
    echo `date` "$0 $$ -- invalid changes ($CHANGES)" >>! $TMP/LOG
    goto done
else
    echo `date` "$0 $$ -- last sequence ($seqid)" >>! $TMP/LOG
endif

if ($?seqid && $?prev_seqid) then
    if ($#seqid > 0 && $#prev_seqid > 0 && $prev_seqid != 0 && $seqid != 0) then
	if ("$seqid" == "$prev_seqid") then
	    echo `date` "$0 $$ !! NO NEW EVENTS ($seqid)" >>! $TMP/LOG
	    goto done
	endif
    endif
endif

set RESULTS = "$TMP/$APP-$API-$QUERY_STRING-results.$DATE.json"
if (-s "$CHANGES" && (! -s "$RESULTS" || ((-M "$CHANGES") > (-M "$RESULTS")))) then
    # remove old results
    set old = ( `ls -1 "$TMP/$APP-$API-$QUERY_STRING-results".*.json` )
    echo `date` "$0 $$ -- removing old results ($old)" >>! $TMP/LOG
    if ($#old > 0) rm -f $old
    echo `date` "$0 $$ -- creating results from changes" >>! $TMP/LOG
    /usr/local/bin/jq -c '[.results[].doc|{file:.visual.image,tag:.alchemy.text,score:.alchemy.score,year:.year,month:.month,day:.day,hour:.hour,minute:.minute,second:.second}]' "$CHANGES" \
	| /usr/local/bin/jq -c '{results:.[]|[.file,.tag,.score,.year,.month,.day,.hour,.minute,.second]}' \
	| sed 's/"//g' \
	| sed 's/{results:\[//' \
	| sed 's/\]}//' \
	| /usr/local/bin/gawk -F, \
	  '{ m=($7*60+$8)/15; \
	     t=mktime(sprintf("%4d %2d %2d %2d %2d %2d",$4,$5,$6,$7,$8,$9)); \
	     printf("{\"file\":\"%s\",\"tag\":\"%s\",\"score\":%f,\"ampm\":\"%s\",\"day\":\"%s\",\"interval\":%d}\n",$1,$2,$3,strftime("%p",t),strftime("%A",t),m); \
	   }' \
	| sort -r >! "$RESULTS"
    echo `date` "$0 $$ -- completed ($RESULTS)" >>! $TMP/LOG
else
    echo `date` "$0 $$ -- results are current with changes" >>! $TMP/LOG
endif

#
# download images from RESULTS of CHANGES 
#
# { "file": "20160801182222-610-00.jpg", "tag": "NO_TAGS", "score": 0, "ampm": "PM", "day": "Monday", "interval": 73 }
#

if ($?FTP_GET == 0) then
    echo `date` "$0 $$ -- getting new images" >>! $TMP/LOG
    # create temporary output for processing sequentially; ignore "ampm"
    foreach line ( `/usr/local/bin/jq -c '[.file,.tag,.score,.day,.interval]' "$RESULTS" | sed 's/\[//' | sed 's/\]//' | sed 's/ /_/g' | awk -F, '{ printf("%s,%s,%f,%s,%d\n", $1,$2,$3,$4,$5) }'` )
	set tuple = ( `echo "$line" | sed 's/,/ /g'` )
	if ($#tuple < 2) then
	    echo `date` "$0 $$ -- bad tuple ($tuple) ($line)" >>! $TMP/LOG
	    continue
	endif
	set tag = `echo $tuple[2] | sed 's/"//g'`
	if (($tag == $class) || ($class == "all") && $tag != "null") then
	    # get filename
	    set file = `echo $tuple[1] | sed 's/"//g'`
	    # build image fullpath
	    set image = "$TMP/$DB/$tag/$file"
	    # ensure directory exists
	    mkdir -p "$image:h"
	    # test if image already exists
	    if (! -s "$image") then
		set ftp = "ftp://$LANIP/$file" 
		/usr/bin/curl -s -q "$ftp" -o "$image"
		if ($status != 0) then
		    echo `date` "$0 $$ -- fail ($ftp)" >>! $TMP/LOG
		    break
		endif
		if (-s "$image") then
		    echo `date` "$0 $$ -- success ($image)" >>! $TMP/LOG
		    # optionally delete the source
		    if ($?FTP_DELETE) then
			echo `date` "$0 $$ -- deleting ($file)" >>! $TMP/LOG
			/usr/bin/curl -s -q "ftp://$LANIP/" -Q "-DELE $file"
		    endif
	        else
		    echo `date` "$0 $$ -- removing ZERO ($image)" >>! $TMP/LOG
		    rm -f "$image"
	        endif
	    else
		echo `date` "$0 $$ -- done; found existing image ($image)" >>! $TMP/LOG
	        break
	    endif
	endif
    end
else
    echo `date` $0 $$ -- skipping new images" >>! $TMP/LOG
endif

#
# MAKE NEW STATISTICS
#

# only works for limited # and format of class names (no space)
set classes = ( `/bin/ls -1 "$TMP/$DB"` )
echo `date` "$0 $$ -- found $#classes classes" >>! $TMP/LOG

set NEW = "$OUTPUT".$$
echo -n '{ "seqid":"'$seqid'","date":"'$DATE'","device":"'"$DB"'","count":'$#classes',"classes":[' >! "$NEW"

echo `date` "$0 $$ -- iterating over $classes" >>! $TMP/LOG

@ k = 0
# this should really be fed by a find(1) command
foreach i ( $classes )
    if ($k > 0) echo "," >> "$NEW"
    set nfiles = ( `/bin/ls -1 "$TMP/$DB/$i" | wc | awk '{ print $1 }'` )
    echo -n '{"name":"'$i'","count":'$nfiles'}' >> "$NEW"
    echo `date` "$0 $$ -- $i, $nfiles" >>! $TMP/LOG
    @ k++
end
echo -n ']}' >> "$NEW"

/usr/local/bin/jq -c '.' "$NEW" >>! $TMP/LOG
if ($status != 0) then
    echo `date` "$0 $$ -- malformed JSON: `cat "$NEW"` >>! $TMP/LOG
    rm -f "$NEW"
    goto done
else
    echo `date` "$0 $$ -- good JSON ($NEW)" >>! $TMP/LOG
endif

# update statistics
mv -f "$NEW" "$OUTPUT"

#
# update Cloudant
#
if ($?CLOUDANT_OFF == 0 && $?CU && $?DB) then
    echo `date` "$0 $$ -- test if DB exists ($CU/$DB-$API)" >>! $TMP/LOG
    set DEVICE_DB = `/usr/bin/curl -s -q -X GET "$CU/$DB-$API" | /usr/local/bin/jq '.db_name'`
    if ( "$DEVICE_DB" == "null" ) then
	echo `date` "$0 $$ -- creating DB $CU/$DB-$API" >>! $TMP/LOG
        # create DB
        set DEVICE_DB = `/usr/bin/curl -s -q -X PUT "$CU/$DB-$API" | /usr/local/bin/jq '.ok'`
        # test for success
        if ( "$DEVICE_DB" != "true" ) then
            # failure
	    echo `date` "$0 $$ -- failure creating Cloudant database ($DB-$API)" >>! $TMP/LOG
            setenv CLOUDANT_OFF TRUE
	else
	    echo `date` "$0 $$ -- success creating DB $CU/$DB-$API" >>! $TMP/LOG
        endif
    endif
    if ( $?CLOUDANT_OFF == 0 ) then
	curl -s -q -o "$OLD" "$CU/$DB-$API/$class" >>&! $TMP/LOG
	if (-s "$OLD") then
	    set doc = ( `cat "$OLD" | /usr/local/bin/jq ._id,._rev | sed 's/"//g'` )
	    if ($#doc == 2 && $doc[1] == $class && $doc[2] != "") then
		set rev = $doc[2]
		echo `date` "$0 $$ -- deleting old output ($rev)" >>! $TMP/LOG
		/usr/bin/curl -s -q -X DELETE "$CU/$DB-$API/$class?rev=$rev" >>&! $TMP/LOG
	    endif
	else
            echo `date` "$0 $$ -- no old output to delete" >>! $TMP/LOG
        endif
        echo `date` "$0 $$ -- storing new output" >>! $TMP/LOG
        /usr/bin/curl -s -q -H "Content-type: application/json" -X PUT "$CU/$DB-$API/$class" -d "@$OUTPUT" >>&! $TMP/LOG
	if ($status == 0) then
	    echo `date` "$0 $$ -- success storing new output" >>! $TMP/LOG
	else
	    echo `date` "$0 $$ -- failure storing new output" >>! $TMP/LOG
	endif
    else
	echo `date` "$0 $$ -- Cloudant OFF ($DB-$API)" >>! $TMP/LOG
    endif
else
    echo `date` "$0 $$ -- no Cloudant update" >>! $TMP/LOG
endif

done:
echo `date` "$0 $$ -- FINISH"  >>! $TMP/LOG
