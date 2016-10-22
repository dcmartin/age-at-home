#!/bin/csh -fb
onintr done
setenv APP "aah"
setenv API "images"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

if ($?TTL == 0) set TTL = 300
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
    set class = `echo "$QUERY_STRING" | sed 's/.*id=\([^&]*\).*/\1/'`
    if ($class == "$QUERY_STRING") unset class
    set match = `echo "$QUERY_STRING" | sed 's/.*match=\([^&]*\).*/\1/'`
    if ($match == "$QUERY_STRING") unset match
endif

if ($?DB == 0) set DB = rough-fog
if ($?class == 0) set class = NO_TAGS
if ($?match == 0) set match = `date +%Y%m`
# standardize QUERY_STRING
setenv QUERY_STRING "db=$DB&id=$class&match=$match"

echo `date` "$0 $$ -- START ($QUERY_STRING)"  >>! $TMP/LOG

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
/usr/bin/curl -s -q -o "$OLD" -X GET "$CU/$DB-$API/$class-$match"
echo `date` "$0 $$ -- got OLD ($OLD)" >>! $TMP/LOG
# default
set prev_seqid = 0
# check iff successful
set CLASS_DB = `/usr/local/bin/jq '._id' "$OLD" | sed 's/"//g'`
if ($CLASS_DB != $class-$match) then
    echo `date` "$0 $$ -- not found ($CU/$DB-$API/$class-$match)" >>! $TMP/LOG
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
# make new results
#

set NEW = "$OUTPUT".$$

#
# update Cloudant
#
if ($?CLOUDANT_OFF == 0 && $?CU && $?DB) then
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
    if ((-s "$NEW") && $?CLOUDANT_OFF == 0) then
        set doc = ( `cat "$OLD" | /usr/local/bin/jq ._id,._rev | sed 's/"//g'` )
        if ($#doc == 2 && $doc[1] == $class && $doc[2] != "") then
            set rev = $doc[2]
            echo `date` "$0 $$ -- deleting old output ($rev)" >>! $TMP/LOG
            /usr/bin/curl -s -q -X DELETE "$CU/$DB-$API/$class-$match?rev=$rev" >>! $TMP/LOG
	else
            echo `date` "$0 $$ -- no old output to delete" >>! $TMP/LOG
        endif
        echo `date` "$0 $$ -- storing new output" >>! $TMP/LOG
        /usr/bin/curl -s -q -H "Content-type: application/json" -X PUT "$CU/$DB-$API/$class-$match" -d "@$NEW" >>! $TMP/LOG
	if ($status == 0) then
	    echo `date` "$0 $$ -- success storing new output" >>! $TMP/LOG
	else
	    echo `date` "$0 $$ -- failure storing new output" >>! $TMP/LOG
	endif
    else if ($?CLOUDANT_OFF) then
	echo `date` "$0 $$ -- Cloudant off" >>! $TMP/LOG
    else
	echo `date` "$0 $$ -- nothing new ($NEW)" >>! $TMP/LOG
    endif
else
    echo `date` "$0 $$ -- CLOUDANT_OFF ($CLOUDANT_OFF) CU ($CU) DB ($DB)" >>! $TMP/LOG
endif

# update statistics
mv -f "$NEW" "$OUTPUT"
# remove OLD
rm -f "$OLD"

done:

echo `date` "$0 $$ -- FINISH ($QUERY_STRING)"  >>! $TMP/LOG
