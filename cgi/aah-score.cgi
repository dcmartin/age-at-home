#!/bin/tcsh -b
setenv APP "aah"
setenv API "score"

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

# don't update statistics more than once per 24 hours
set TTL = `/bin/echo "24 * 60 * 60" | bc`
set SECONDS = `date "+%s"`
set DATE = `/bin/echo $SECONDS \/ $TTL \* $TTL | bc`

/bin/echo `date` "$0:t $$ -- START" >>! $LOGTO

if ($?QUERY_STRING) then
    set DB = `/bin/echo "$QUERY_STRING" | sed "s/.*db=\([^&]*\).*/\1/"`
    if ($#DB == 0) set DB = rough-fog
else
    set DB = rough-fog
endif
setenv QUERY_STRING "db=$DB"

set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
if (! -e "$OUTPUT") then
    rm -f "$TMP/$APP-$API-$QUERY_STRING".*.json
    if ($DB == "damp-cloud") then
    	# damp cloud (visual-classifier, score, time) Public Access
	curl -L -s -q -o "$OUTPUT.$$" "https://ibmcds.looker.com/looks/gGt5s3SmqfMt2HDbr7R2pCNcM2th3h4s.json?apply_formatting=true"
    else
	curl -L -s -q -o "$OUTPUT.$$" "https://ibmcds.looker.com/looks/9fBDPkqVtjHyBJqQBr6xrW4JP9dXgkRv.json?apply_formatting=true"
    endif

    /bin/echo '{"device":"'$DB'", "scores":' >! "$OUTPUT".$$.$$

    if ($DB == "damp-cloud") then
	cat "$OUTPUT".$$ \
	    | sed "s/dampcloud\.alchemy_//" \
	    | sed "s/dampcloud_visual_scores\.//g" >> "$OUTPUT".$$.$$
    else
	cat "$OUTPUT".$$ \
	    | sed "s/roughfog\.alchemy_//" \
	    | sed "s/roughfog_visual_scores\.//g" >> "$OUTPUT".$$.$$
    endif
    rm -f "$OUTPUT.$$"
    /bin/echo '}' >> "$OUTPUT.$$.$$"
    mv -f "$OUTPUT".$$.$$ "$OUTPUT"
endif

/bin/echo "Content-Type: application/json; charset=utf-8"
/bin/echo "Access-Control-Allow-Origin: *"
set AGE = `/bin/echo "$SECONDS - $DATE" | bc`
/bin/echo "Age: $AGE"
/bin/echo "Cache-Control: max-age=$TTL"
/bin/echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
/bin/echo ""
cat "$OUTPUT"

done:

/bin/echo `date` "$0:t $$ -- FINISH" >>! $LOGTO
