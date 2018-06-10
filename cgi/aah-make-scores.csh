#!/bin/tcsh -b
setenv APP "aah"
setenv API "scores"

# debug on/off
setenv DEBUG true
setenv VERBOSE true

# environment
if ($?LAN == 0) setenv LAN "192.168.1"
if ($?DIGITS == 0) setenv DIGITS "$LAN".30
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"
if ($?CREDENTIALS == 0) setenv CREDENTIALS /usr/local/etc
if ($?LOGTO == 0) setenv LOGTO /dev/stderr

# don't update statistics more than once per 12 hours
set TTL = `/bin/echo "12 * 60 * 60" | bc`
set SECONDS = `date "+%s"`
set DATE = `/bin/echo $SECONDS \/ $TTL \* $TTL | bc`

/bin/echo `date` "$0 $$ -- START" >>! $LOGTO

##
## ACCESS CLOUDANT
##
if ($?CLOUDANT_URL) then
  set CU = $CLOUDANT_URL
else if (-s $CREDENTIALS/.cloudant_url) then
  set cc = ( `cat $CREDENTIALS/.cloudant_url` )
  if ($#cc > 0) set CU = $cc[1]
  if ($#cc > 1) set CN = $cc[2]
  if ($#cc > 2) set CP = $cc[3]
  if ($?CP && $?CN && $?CU) then
    set CU = 'https://'"$CN"':'"$CP"'@'"$CU"
  else if ($?CU) then
    set CU = "https://$CU"
  endif
else
  /bin/echo `date` "$0:t $$ -- FAILURE: no Cloudant credentials" >>& $LOGTO
  goto done
endif

if ($?QUERY_STRING) then
    set DB = `/bin/echo "$QUERY_STRING" | sed "s/.*db=\([^&]*\).*/\1/"` 
    # only process "all" (for now)
    # set class = `/bin/echo "$QUERY_STRING" | sed "s/.*id=\([^&]*\)/\1/"`
endif
if ($DB != "damp-cloud") set DB = rough-fog
if ($?class == 0) set class = all
setenv QUERY_STRING "db=$DB&id=$class"

# output set
set JSON = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
set INPROGRESS = ( `/bin/echo "$JSON".*` )

# check JSON in-progress for current interval
if ($#INPROGRESS) then
    /bin/echo `date` "$0 $$ -- in-progress" >>! $LOGTO
    goto done    
else
    if ($DB == "damp-cloud") then
        # damp cloud (visual-classifier, score, time) Public Access
        curl -L -s -q -o "$JSON.$$" "https://ibmcds.looker.com/looks/gGt5s3SmqfMt2HDbr7R2pCNcM2th3h4s.json?apply_formatting=true"
    else
        # rough fog (visual-classifier, score, time) Public Access
        curl -L -s -q -o "$JSON.$$" "https://ibmcds.looker.com/looks/9fBDPkqVtjHyBJqQBr6xrW4JP9dXgkRv.json?apply_formatting=true"
    endif

    /bin/echo '{"device":"'$DB'", "scores":' >! "$JSON".$$.$$

    if ($DB == "damp-cloud") then
        cat "$JSON".$$ \
            | sed "s/dampcloud\.alchemy_//" \
            | sed "s/dampcloud_visual_scores\.name/name/" \
            | sed 's/"dampcloud_visual_scores\.score":"\([^"]*\)"/"score":\1/g' >> "$JSON".$$.$$
    else
        cat "$JSON".$$ \
            | sed "s/roughfog\.alchemy_//" \
            | sed "s/roughfog_visual_scores\.name/name/" \
            | sed 's/"roughfog_visual_scores\.score":"\([^"]*\)"/"score":\1/g' >> "$JSON".$$.$$
    endif
    rm -f "$JSON.$$"
    /bin/echo '}' >> "$JSON.$$.$$"
    mv -f "$JSON".$$.$$ "$JSON"
endif

#
# update Cloudant
#
if ($?CLOUDANT_OFF == 0 && $?CU && $?DB && (-s $JSON)) then
    set DEVICE_DB = `curl -s -q -X GET "$CU/$DB-$API" | jq '.db_name'`
    if ( "$DEVICE_DB" == "null" ) then
	/bin/echo `date` "$0 $$ -- create Cloudant ($DB-$API)" >>! $LOGTO
	# create DB
	set DEVICE_DB = `curl -s -q -X PUT "$CU/$DB-$API" | jq '.ok'`
	# test for success
	if ( "$DEVICE_DB" != "true" ) then
	    # failure
	    /bin/echo `date` "$0 $$ -- FAILED: create Cloudant ($DB-$API)" >>! $LOGTO
	    setenv CLOUDANT_OFF TRUE
	endif
    endif
    if ( $?CLOUDANT_OFF == 0 ) then
	set doc = ( `curl -s -q "$CU/$DB-$API/$class" | jq ._id,._rev | sed 's/"//g'` )
	if ($#doc == 2 && $doc[1] == $class && $doc[2] != "") then
	    set rev = $doc[2]
	    /bin/echo `date` "$0 $$ -- DELETE $CU/$DB-$API/$class $rev" >>! $LOGTO
	    curl -s -q -X DELETE "$CU/$DB-$API/$class?rev=$rev"
	endif
	/bin/echo `date` "$0 $$ -- STORE $CU/$DB-$API/$class" >>! $LOGTO
	curl -s -q -H "Content-type: application/json" -X PUT "$CU/$DB-$API/$class" -d "@$JSON" >>! $LOGTO
    endif
else
    /bin/echo `date` "$0 $$ -- no Cloudant update" >>! $LOGTO
endif

done:
    /bin/echo `date` "$0 $$ -- FINISH" >>! $LOGTO
