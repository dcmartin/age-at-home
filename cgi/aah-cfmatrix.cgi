#!/bin/csh -fb
setenv APP "aah"
setenv API "cfmatrix"

# setenv DEBUG true

if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

# don't update statistics more than once per 15 minutes
set TTL = `/bin/echo "30 * 1" | bc`
set SECONDS = `date "+%s"`
set DATE = `/bin/echo $SECONDS \/ $TTL \* $TTL | bc`

/bin/echo `date` "$0 $$ -- START" >>& "$TMP/LOG"

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

if (-s ~$USER/.cloudant_url) then
    set cc = ( `cat ~$USER/.cloudant_url` )
    if ($#cc > 0) set CU = $cc[1]
    if ($#cc > 1) set CN = $cc[2]
endif

if ($?CLOUDANT_URL) then
    setenv CU $CLOUDANT_URL
else if ($?CN) then
    set CU = "$CN.cloudant.com"
else
    /bin/echo `date` "$0 $$ -- no Cloudant URL" >>& $TMP/LOG
    goto done
endif

set creds = ~$USER/.watson.visual-recognition.json
if (-s $creds) then
    set api_key = ( `/usr/local/bin/jq -r '.[0]|.credentials.api_key' "$creds"` )
    if ($?DEBUG) /bin/echo `date` "$0 $$ -- USING APIKEY $api_key" >>& "$TMP/LOG"
    set url = ( `/usr/local/bin/jq -r '.[0]|.credentials.url' "$creds"` )
    if ($?DEBUG) /bin/echo `date` "$0 $$ -- USING URL $url" >>& "$TMP/LOG"
    # set base
    set TU = $url
    /bin/echo `date` "$0 $$ -- CREDENTIALS ($creds); $TU" >>& "$TMP/LOG"
else if ($?TU == 0) then
    /bin/echo `date` "$0 $$ -- NO CREDENTIALS ($creds); create file and copy credentials from visual-recognition service on bluemix.net" >>& "$TMP/LOG"
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
    set tmp = ( `cat "$CLASSIFIERS" | /usr/local/bin/jq '.'` )

    if ($?db == 0 && $?model == 0) then
	set classifiers = ( `/bin/echo "$tmp" | /usr/local/bin/jq -r '.classifiers[]|select(.status=="ready").classifier_id'` )
    else if ($?model) then
	set classifiers = ( `/bin/echo "$tmp" | /usr/local/bin/jq -r '.classifiers[]|select(.classifier_id=="'"$model"'")|select(.status=="ready").classifier_id'` )
    else  if ($?db) then
	set classifiers = ( `/bin/echo "$tmp" | /usr/local/bin/jq -r '.classifiers[]|select(.name=="'"$db"'")|select(.status=="ready").classifier_id'` )
    endif
else
  set classifiers = ()
endif

if ($#classifiers == 0) then
  if ($?DEBUG) /bin/echo `date` "$0 $$ -- NO CLASSIFIERS FOUND ($TU/$verid,$vdate)" >>& "$TMP/LOG"
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
    /bin/echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
    /bin/echo ""
    cat "$OUTPUT"
  else
    # return redirect
    set URL = "https://$CU/$db-$API/$model?include_docs=true"
    /bin/echo `date` "$0 $$ -- returning redirect ($URL)" >>! $TMP/LOG
    set AGE = `/bin/echo "$SECONDS - $DATE" | bc`
    /bin/echo "Age: $AGE"
    /bin/echo "Cache-Control: max-age=$TTL"
    /bin/echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
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

/bin/echo `date` "$0 $$ -- FINISH" >>& $TMP/LOG
