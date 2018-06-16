#!/bin/tcsh -b
setenv APP "aah"
setenv API "scores"

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

# don't update statistics more than once per 12 hours
set TTL = `/bin/echo "12 * 60 * 60" | bc`
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
  if ($#cc > 1) set CN = $cc[2]
  if ($#cc > 2) set CP = $cc[3]
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
    set DB = `/bin/echo "$QUERY_STRING" | sed "s/.*db=\([^&]*\).*/\1/"` 
    set class = `/bin/echo "$QUERY_STRING" | sed "s/.*id=\([^&]*\)/\1/"`
endif
if ($#DB == 0) set DB = rough-fog
if ($#class == 0) set class = all
setenv QUERY_STRING "db=$DB&id=$class"

set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

if (-e "$OUTPUT") then
    /bin/echo `date` "$0 $$ == CURRENT $OUTPUT $DATE" >>&! $LOGTO
else
    /bin/echo `date` "$0 $$ -- requesting output ($OUTPUT)" >>&! $LOGTO
    ./$APP-make-$API.bash
    # remove old results
    set old = ( `ls -1 "$TMP/$APP-$API-$QUERY_STRING".*.json` )
    if ($#old > 0) then
	/bin/echo `date` "$0 $$ -- removing old output ($old)" >>&! $LOGTO
	rm -f $old
    endif
    # return redirect
    set URL = "https://$CU/$DB-$API/$class?include_docs=true"
    /bin/echo `date` "$0 $$ -- returning redirect ($URL)" >>&! $LOGTO
    set AGE = `/bin/echo "$SECONDS - $DATE" | bc`
    /bin/echo "Age: $AGE"
    /bin/echo "Cache-Control: max-age=$TTL"
    /bin/echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
    /bin/echo "Status: 302 Found"
    /bin/echo "Location: $URL"
    /bin/echo ""
    goto done
endif

output:

# prepare for output
/bin/echo "Content-Type: application/json; charset=utf-8"
/bin/echo "Access-Control-Allow-Origin: *"
set AGE = `/bin/echo "$SECONDS - $DATE" | bc`
/bin/echo "Age: $AGE"
/bin/echo "Cache-Control: max-age=$TTL"
/bin/echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
/bin/echo ""
cat "$OUTPUT"

done:

/bin/echo `date` "$0 $$ -- FINISH" >>&! $LOGTO
