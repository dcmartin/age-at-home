#!/bin/csh -fb
onintr done
setenv APP "aah"
setenv API "review"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

# don't update statistics more than once per hour
set TTL = `echo "1 * 60 * 60" | bc`
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo `date` "$0 $$ -- START"  >>! $TMP/LOG

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

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($DB == "$QUERY_STRING") unset DB
endif

#
# defaults to rough-fog (kitchen) and all classes
#
if ($?DB == 0) set DB = rough-fog
# always process all classes (for now)
set class = "all"
# standardize QUERY_STRING
setenv QUERY_STRING "db=$DB&class=$class"

if ($DB == "rough-fog" && $?LANIP == 0) then
    setenv LANIP "192.168.1.34"
else if ($DB == "damp-cloud" && $?LANIP == 0) then
    setenv LANIP "192.168.1.35"
else
    echo `date` "$0 $$ -- no LANIP" >>! $TMP/LOG
    goto done
endif

# output set
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
set INPROGRESS = ( `echo "$OUTPUT".*` )
# check OUTPUT in-progress for current interval
if ($#INPROGRESS) then
    echo `date` "$0 $$ -- in-progress $DATE" >>! $TMP/LOG
    goto done
endif

#
# download old result
#
set OLD = "$OUTPUT".$$
echo `date` "$0 $$ -- get OLD ($CU/$DB-$API/$class)" >>! $TMP/LOG
/usr/bin/curl -s -q -o "$OLD" -X GET "$CU/$DB-$API/$class"
echo `date` "$0 $$ -- got OLD ($OLD)" >>! $TMP/LOG
# default
set prev_seqid = 0
# check iff successful
set CLASS_DB = `/usr/local/bin/jq '._id' "$OLD" | sed 's/"//g'`
if ($CLASS_DB != $class) then
    echo `date` "$0 $$ -- not found ($CU/$DB-$API/$class)" >>! $TMP/LOG
else
    echo `date` "$0 $$ -- class found ($CLASS_DB)" >>! $TMP/LOG
    # get last sequence # for class specified
    set prev_seqid = `/usr/local/bin/jq '.seqid' "$OLD" | sed 's/"//g'`
    echo `date` "$0 $$ -- prev_seqid ($prev_seqid)" >>! $TMP/LOG
    if ($#prev_seqid < 1) set prev_seqid = 0
    if ($prev_seqid[1] == "null") set prev_seqid = 0
endif

echo `date` "$0 $$ -- prev_seqid ($prev_seqid)" >>! $TMP/LOG

#
# get CHANGES records
#
set CHANGES = "$TMP/$APP-$API-$QUERY_STRING.changes.$DATE.json"
set seqid = 0
if ( ! -e "$CHANGES" ) then
    # remove old changes
    set old = ( `ls -1 "$TMP/$APP-$API-$QUERY_STRING.changes".*.json` )
    echo `date` "$0 $$ -- removing old changes ($old)" >>! $TMP/LOG
    if ($#old > 0) rm -f $old
    echo `date` "$0 $$ -- get changes ($CU/$DB/_changes?descending=true&include_docs=true&since=$prev_seqid)" >>! $TMP/LOG
    /usr/bin/curl -s -q -o "$CHANGES" "$CU/$DB/_changes?descending=true&include_docs=true&since=$prev_seqid"
    echo `date` "$0 $$ -- got ($CHANGES)" >>! $TMP/LOG
    set seqid = ( `/usr/local/bin/jq .last_seq "$CHANGES"` )
    if ($seqid == "null") then
         echo `date` "$0 $$ -- failure retrieving changes" >>! $TMP/LOG
         exit
    endif
else
    set seqid = ( `/usr/local/bin/jq .last_seq "$CHANGES" | sed 's/"//g'` )
    if ($seqid == "null") then
        echo `date` "$0 $$ -- invalid changes" >>! $TMP/LOG
        exit
    else
        echo `date` "$0 $$ -- last sequence ($seqid)" >>! $TMP/LOG
    endif
    set ttyl = `echo "$SECONDS - $DATE" | bc`
    echo `date` "$0 $$ -- changes are current ($TTL) update in $ttyl" >>! $TMP/LOG
endif

set RESULTS = "$TMP/$APP-$API-$QUERY_STRING.results.$DATE.json"
if (-s "$CHANGES" && (! -s "$RESULTS" || ((-M "$CHANGES") > (-M "$RESULTS")))) then
    # remove old results
    set old = ( `ls -1 "$TMP/$APP-$API-$QUERY_STRING.results".*.json` )
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

set NEW = "$OLD.$$"
echo -n '{ "seqid":"'$seqid'","date":"'$DATE'","device":"'"$DB"'","count":'$#classes',"classes":[' >! "$NEW"

@ k = 0
# this should really be fed by a find(1) command
foreach i ( $classes )
    if ($k > 0) echo "," >> "$NEW"
    set nfiles = ( `/bin/ls -1 "$TMP/$DB/$i" | wc | awk '{ print $1 }'` )
    echo -n '{"name":"'$i'","count":'$nfiles'}' >> "$NEW"
    @ k++
end
echo -n ']}' >> "$NEW"

/usr/local/bin/jq -c '.' "$NEW" >>! $TMP/LOG
if ($status != 0) then
    echo `date` "$0 $$ -- malformed JSON ($NEW)" >>! $TMP/LOG
endif

#
# update Cloudant
#
if ($?CLOUDANT_OFF == 0 && $?CU && $?DB) then
    set DEVICE_DB = `/usr/bin/curl -s -q -X GET "$CU/$DB-$API" | /usr/local/bin/jq '.db_name'`
    if ( "$DEVICE_DB" == "null" ) then
        # create DB
        set DEVICE_DB = `/usr/bin/curl -s -q -X PUT "$CU/$DB-$API" | /usr/local/bin/jq '.ok'`
        # test for success
        if ( "$DEVICE_DB" != "true" ) then
            # failure
	    echo `date` "$0 $$ -- failure creating Cloudant database ($DB-$API)" >>! $TMP/LOG
            setenv CLOUDANT_OFF TRUE
        endif
    endif
    if ( $?CLOUDANT_OFF == 0 ) then
        set doc = ( `cat "$OLD" | /usr/local/bin/jq ._id,._rev | sed 's/"//g'` )
        if ($#doc == 2 && $doc[1] == $class && $doc[2] != "") then
            set rev = $doc[2]
            echo `date` "$0 $$ -- deleting old output ($rev)" >>! $TMP/LOG
            /usr/bin/curl -s -q -X DELETE "$CU/$DB-$API/$class?rev=$rev" >>! $TMP/LOG
        endif
        echo `date` "$0 $$ -- storing new output" >>! $TMP/LOG
        /usr/bin/curl -s -q -H "Content-type: application/json" -X PUT "$CU/$DB-$API/$class" -d "@$NEW" >>! $TMP/LOG
    else
	echo `date` "$0 $$ -- Cloudant OFF ($DB-$API)" >>! $TMP/LOG
    endif
    echo `date` "$0 $$ -- success ($NEW)" >>! $TMP/LOG
else
    echo `date` "$0 $$ -- no Cloudant update" >>! $TMP/LOG
endif

# update statistics
mv -f "$NEW" "$OUTPUT"
# remove OLD
rm -f "$OLD"

done:

echo `date` "$0 $$ -- FINISH"  >>! $TMP/LOG
