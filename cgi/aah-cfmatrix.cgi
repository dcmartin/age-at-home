#!/bin/tcsh -b
setenv APP "aah"
setenv API "cfmatrix"

# setenv DEBUG true
# setenv VERBOSE true

# environment
if ($?LAN == 0) setenv LAN "192.168.1"
if ($?DIGITS == 0) setenv DIGITS "$LAN".30
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"
if ($?CREDENTIALS == 0) setenv CREDENTIALS /usr/local/etc
if ($?LOGTO == 0) setenv LOGTO /dev/stderr

# don't update statistics more than once per 15 minutes
set TTL = `/bin/echo "30 * 1" | bc`
set SECONDS = `date "+%s"`
set DATE = `/bin/echo $SECONDS \/ $TTL \* $TTL | bc`

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

/bin/echo `date` "$0:t $$ -- START" >>& "$LOGTO"

if ($?QUERY_STRING) then
    set db = `/bin/echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") then
      set db = `/bin/echo "$QUERY_STRING" | sed 's/.*device=\([^&]*\).*/\1/'`
      if ($db == "$QUERY_STRING") unset db
    endif
    set model = `/bin/echo "$QUERY_STRING" | sed 's/.*model=\([^&]*\).*/\1/'`
    if ($model == "$QUERY_STRING") unset model
endif

if ($?db && $?model) then
    setenv QUERY_STRING "db=$db&model=$model"
else if ($?model) then
    setenv QUERY_STRING "model=$model"
else if ($?db) then
    setenv QUERY_STRING "db=$db"
endif

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

set creds = $CREDENTIALS/.watson.visual-recognition.json
if (-s $creds) then
    set api_key = ( `jq -r '.[0]|.credentials.api_key' "$creds"` )
    if ($?DEBUG) /bin/echo `date` "$0:t $$ -- USING APIKEY $api_key" >>& "$LOGTO"
    set url = ( `jq -r '.[0]|.credentials.url' "$creds"` )
    if ($?DEBUG) /bin/echo `date` "$0:t $$ -- USING URL $url" >>& "$LOGTO"
    # set base
    set TU = $url
    /bin/echo `date` "$0:t $$ -- CREDENTIALS ($creds); $TU" >>& "$LOGTO"
else if ($?TU == 0) then
    /bin/echo `date` "$0:t $$ -- NO CREDENTIALS ($creds); create file and copy credentials from visual-recognition service on bluemix.net" >>& "$LOGTO"
    goto done
endif

if ($?verid == 0) set verid = "v3"
if ($?vdate == 0) set vdate = "2016-05-20"

# find models and dbs
set CLASSIFIERS = "$TMP/$APP-$API-classifiers.$DATE.json"
if (! -s "$CLASSIFIERS") then
  rm -f "$TMP/$APP-$API-classifiers".*.json
  curl -q -s -L "$TU/$verid/classifiers?api_key=$api_key&version=$vdate" >! "$CLASSIFIERS"
endif

if (-s "$CLASSIFIERS") then
    set tmp = ( `cat "$CLASSIFIERS" | jq '.'` )

    if ($?db == 0 && $?model == 0) then
	set classifiers = ( `/bin/echo "$tmp" | jq -r '.classifiers[]|select(.status=="ready").classifier_id'` )
    else if ($?model) then
	set classifiers = ( `/bin/echo "$tmp" | jq -r '.classifiers[]|select(.classifier_id=="'"$model"'")|select(.status=="ready").classifier_id'` )
    else  if ($?db) then
	set classifiers = ( `/bin/echo "$tmp" | jq -r '.classifiers[]|select(.name=="'"$db"'")|select(.status=="ready").classifier_id'` )
    endif
else
  set classifiers = ()
endif

if ($#classifiers == 0) then
  if ($?DEBUG) /bin/echo `date` "$0:t $$ -- NO CLASSIFIERS FOUND ($TU/$verid,$vdate)" >>& "$LOGTO"
  /bin/echo "Content-Type: application/json; charset=utf-8"
  /bin/echo "Access-Control-Allow-Origin: *"
  /bin/echo "Cache-Control: no-cache"
  /bin/echo ""
  /bin/echo '{"error":"not found"}'
else if ($?model) then
  set OUTPUT = "$TMP/matrix/$model.json"
  if (-s "$OUTPUT") then
    /bin/echo "Content-Type: application/json; charset=utf-8"
    /bin/echo "Access-Control-Allow-Origin: *"
    set AGE = `/bin/echo "$SECONDS - $DATE" | bc`
    /bin/echo "Age: $AGE"
    /bin/echo "Cache-Control: max-age=$TTL"
    /bin/echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
    /bin/echo ""
    cat "$OUTPUT"
  else
    # return redirect
    set URL = "https://$CU/$db-$API/$model?include_docs=true"
    /bin/echo `date` "$0:t $$ -- returning redirect ($URL)" >>! $LOGTO
    set AGE = `/bin/echo "$SECONDS - $DATE" | bc`
    /bin/echo "Age: $AGE"
    /bin/echo "Cache-Control: max-age=$TTL"
    /bin/echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
    /bin/echo "Status: 302 Found"
    /bin/echo "Location: $URL"
    /bin/echo ""
  endif
else if ($#classifiers) then
    /bin/echo "Content-Type: application/json; charset=utf-8"
    /bin/echo "Access-Control-Allow-Origin: *"
    /bin/echo "Cache-Control: no-cache"
    /bin/echo ""
    /bin/echo -n '{"models":['
    unset j
    foreach i ( $classifiers )
      if ($?j) then
        set j = "$j"',"'"$i"'"'
      else
        set j = '"'"$i"'"'
      endif
    end
    /bin/echo -n "$j"'],"count":'$#classifiers
    /bin/echo '}'
endif

done:

/bin/echo `date` "$0:t $$ -- FINISH" >>& $LOGTO
