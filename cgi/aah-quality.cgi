#!/bin/tcsh -b
setenv APP "aah"
setenv API "quality"

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

# don't update file information more than once per (in seconds)
set TTL = 1800
set SECONDS = `date "+%s"`
set DATE = `/bin/echo $SECONDS \/ $TTL \* $TTL | bc`

#
# check provided QUERY_STRING (arguments)
#
if ($?QUERY_STRING) then
    set db = `/bin/echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") then
      set db = `/bin/echo "$QUERY_STRING" | sed 's/.*device=\([^&]*\).*/\1/'`
      if ($db == "$QUERY_STRING") unset db
    endif
    set model = `/bin/echo "$QUERY_STRING" | sed 's/.*model=\([^&]*\).*/\1/'`
    if ($model == "$QUERY_STRING") unset model
else
    /bin/echo `date` "$0 $$ -- NO QUERY_STRING" >>&! $LOGTO
    goto done
endif

#
# Test parameters by rebuilding QUERY_STRING
#
if ($?db == 0) then
    /bin/echo `date` "$0 $$ -- NO DB/DEVICE SPECIFIED ($QUERY_STRING)" >>&! $LOGTO
    goto done
else if ($?model) then
    setenv QUERY_STRING "db=$db&model=$model"
else 
    setenv QUERY_STRING "db=$db"
endif

/bin/echo `date` "$0 $$ -- START" >>&! $LOGTO

#
# look for model
#
if ($?model) then
  set OUTPUT = "$AAHDIR/quality/$model.json"
  if (-s "$OUTPUT") then
    /bin/echo "Content-Type: application/json; charset=utf-8"
    /bin/echo "Access-Control-Allow-Origin: *"
    set AGE = `/bin/echo "$SECONDS - $DATE" | bc`
    /bin/echo "Age: $AGE"
    /bin/echo "Cache-Control: max-age=$TTL"
    /bin/echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
    /bin/echo ""
    cat "$OUTPUT"
    goto done
  else
    # ./$APP-make-$API.bash
    set output = '{ "error": "initializing", "query": "'"$QUERY_STRING"'" }'
    goto output
  endif
endif

#
# get all models for this device 
#

set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
if (! -s "$OUTPUT") then

  # BE SINGLE-THREADED
  set INPROGRESS = ( `/bin/echo "$OUTPUT".*` )
  # note that we're in-progress
  touch "$OUTPUT".$$
  if ($#INPROGRESS) then
    set pid = "$INPROGRESS[$#INPROGRESS]:e"
    set pid = `ps axw | egrep "$pid" | egrep "$API" | awk '{ print $1 }'` )
    if ($#pid) then
      /bin/echo `date` "$0 $$ -- IN PROGRESS ($pid) $#INPROGRESS $INPROGRESS[$#INPROGRESS]" >>&! $LOGTO
      set output = '{ "error": "in-progress", "query":"'"$QUERY_STRING"'" }'
      goto output
    endif
    rm -f $INPROGRESS
  endif

  set MODELS = "$OUTPUT:r.$$.json"
  if ($?model) then
    curl -s -q -f -L "$HTTP_HOST/CGI/aah-models.cgi?db=$db&model=$model"-o "$MODELS"
  else 
    curl -s -q -f -L "$HTTP_HOST/CGI/aah-models.cgi?db=$db"-o "$MODELS"
  endif
  if ($status == 22 || ! -s "$MODELS") then
    /bin/echo `date` "$0 $$ -- NO MODELS ($q)" >>&! $LOGTO
    rm -f "$MODELS"
    rm -f "$OUTPUT".$$
    set output = '{ "error":"no models", "query":"'"$q"'" }'
    goto output
  endif
  if ($?model) then
    /bin/echo `date` "$0 $$ -- NEED TO BUILD THE MODEL" >>&! $LOGTO
  else
    # get ready classifiers
    set classifiers = ( `jq -r '.detail.classifier_id' "$MODELS"` )
    if ($#classifiers == 0) then
      /bin/echo `date` "$0 $$ -- NO (ready) CLASSIFIERS FOUND" >>&! $LOGTO
      rm -f "$OUTPUT"
      set output = '{ "error": "none ready", "query": "'"$q"'" }'
      goto output
    endif
    # create new
    /bin/echo -n '{"models":[' >! "$OUTPUT".$$
    unset j
    foreach i ( $classifiers )
      if ($?j) then
	set j = "$j"',"'"$i"'"' >> "$OUTPUT.$$"
      else
	set j = '"'"$i"'"' >> "$OUTPUT.$$"
      endif
    end
    /bin/echo -n "$j"'],"count":'$#classifiers >> "$OUTPUT.$$"
    /bin/echo '}' >> "$OUTPUT.$$"
    mv -f "$OUTPUT.$$" "$OUTPUT"
  endif
endif

output:

if (! -s "$OUTPUT") then
  /bin/echo "Content-Type: application/json; charset=utf-8"
  /bin/echo "Access-Control-Allow-Origin: *"
  /bin/echo "Cache-Control: no-cache"
  /bin/echo ""
  if ($?output) then
    /bin/echo "$output"
  else
    /bin/echo '{"error":"not found"}'
  endif
else 
  # return redirect
  set AGE = `/bin/echo "$SECONDS - $DATE" | bc`
  /bin/echo "Age: $AGE"
  /bin/echo "Cache-Control: max-age=$TTL"
  /bin/echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
  /bin/echo ""
  cat "$OUTPUT"
endif

done:

/bin/echo `date` "$0 $$ -- FINISH" >>&! $LOGTO
