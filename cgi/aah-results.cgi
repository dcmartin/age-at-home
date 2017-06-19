#!/bin/csh -fb
setenv APP "aah"
setenv API "results"

setenv DEBUG true

if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

# don't update service cache(s) (and this service output) more than once per (in seconds)
set TTL = `echo "60 * 1 * 1  * 1" | bc`
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo `date` "$0 $$ -- START" >>& "$TMP/LOG"

if ($?QUERY_STRING) then
    set db = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
    set model = `echo "$QUERY_STRING" | sed 's/.*model=\([^&]*\).*/\1/'`
    if ($model == "$QUERY_STRING") unset model
    set all_scores = `echo "$QUERY_STRING" | sed 's/.*all_scores\([^&]*\).*/\1/'`
    if ($all_scores == "$QUERY_STRING") unset all_scores
endif
if ($?db == 0) set db = "rough-fog"
setenv QUERY_STRING "db=$db"
if ($?model) then
  setenv QUERY_STRING "$QUERY_STRING"'&model='"$model"
endif
if ($?all_scores) then
  setenv QUERY_STRING "$QUERY_STRING"'&all_scores=true'
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
    echo `date` "$0 $$ -- no Cloudant URL" >>& $TMP/LOG
    goto done
endif

set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
if (! -s "$OUTPUT") then
  set TEST = "$TMP/$APP-$API-$db-test.$DATE.json" 
  if (! -s "$TEST") then
    set old = ( `echo "$TEST:r:r".*` )
    if ($?DEBUG) echo `date` "$0 $$ -- DEBUG: variable (old) is defined (0/1)? ($?old)" >>& "$TMP/LOG"

    echo `date` "$0 $$ -- retrieving from Cloudant: $TEST" >>& "$TMP/LOG"
    curl -s -q -f -L "$CU/$db-test/_all_docs?include_docs=true" -o "$TEST.$$"
    if ($status == 22 || ! -s "$TEST.$$") then
      echo `date` "$0 $$ -- cannot retrieve $TEST from $CU/$db-test" >>& "$TMP/LOG"
      if ($?old) then
        if ($#old) then
	  if (-s "$old[$#old]") then
	    set TEST = "$old[$#old]"
	  else
	    echo `date` "$0 $$ -- no existing $old[$#old] for $TEST" >>& "$TMP/LOG"
	    unset TEST
	  endif
	endif
      else
	echo `date` "$0 $$ -- no old for $TEST" >>& "$TMP/LOG"
	unset TEST
      endif
    else
      echo `date` "$0 $$ -- success retrieving from Cloudant $TEST.$$" >>& "$TMP/LOG"
      mv -f "$TEST.$$" "$TEST"
      if ($?old) then
	@ i = 1
	while ($i <= $#old) 
	  if ($?DEBUG) echo `date` "$0 $$ -- DEBUG: removing $i/$#old from $old" >>& "$TMP/LOG"
	  rm -f "$old[$i]"
	  @ i++
	end
      endif
    endif
  endif
  # process testing information
  if ($?TEST) then
    if (-s "$TEST") then
      set results = ( `/usr/local/bin/jq -r '.rows[].id' "$TEST"` )
      if ($status == 0 && $#results) then
	foreach m ( $results )
	  if ($?model) then
	    if ("$m" != "$model") continue
	  endif
	  if ($?all_scores) then
	    /usr/local/bin/jq '.rows[]|select(.id=="'$m'")' "$TEST" | \
	      /usr/local/bin/jq '{"model":.doc.model,"results":[.doc.sets[]|{"class":.set,"all":[.results[]|{"id":.id,"scores":.classes|sort_by(.score)}]}]}' >! "$OUTPUT.$$.$$"
	  else
	    /usr/local/bin/jq '.rows[]|select(.id=="'$m'")' "$TEST" | \
	      /usr/local/bin/jq '{"model":.doc.model,"results":[.doc.sets[]|{"class":.set,"top":[.results[]|{"id":.id,"class":.classes|sort_by(.score)[-1].class}]}]}' >! "$OUTPUT.$$.$$"
	  endif
	  if ($status == 0 && -s "$OUTPUT.$$.$$") then
	    /usr/local/bin/jq -c '.' "$OUTPUT.$$.$$" >>! "$OUTPUT.$$"
	  else
	    echo `date` "$0 $$ -- failure model ($m)" >>& "$TMP/LOG"
	  endif
	  rm -f "$OUTPUT.$$.$$"
	end
	if (-s "$OUTPUT.$$") then
	  /usr/local/bin/jq -c '.' "$OUTPUT.$$" >! "$OUTPUT"
	endif
	if ($status != 0) then
	  echo `date` "$0 $$ -- bad JSON ($OUTPUT.$$)" >>& "$TMP/LOG"
	  rm -f "$OUTPUT"
	endif
	rm -f "$OUTPUT.$$"
      else
	echo `date` "$0 $$ -- no results in $TEST" >>& "$TMP/LOG"
	rm -f "$OUTPUT".*
	goto output
      endif
    else
      echo `date` "$0 $$ -- no testing cache $TEST" >>& "$TMP/LOG"
    endif
  else
    echo `date` "$0 $$ -- no model data" >>& "$TMP/LOG"
  endif
else
  echo `date` "$0 $$ -- $OUTPUT is up-to-date ($DATE)" >>& "$TMP/LOG"
endif

output:

if (! -s "$OUTPUT") then
  if ($?DEBUG) echo `date` "$0 $$ -- no results found ($db)" >>& "$TMP/LOG"
  echo "Content-Type: application/json; charset=utf-8"
  echo "Access-Control-Allow-Origin: *"
  echo "Cache-Control: no-cache"
  echo ""
  echo '{"error":"not found"}'
else 
  echo "Content-Type: application/json; charset=utf-8"
  echo "Access-Control-Allow-Origin: *"
  set AGE = `echo "$SECONDS - $DATE" | bc`
  echo "Age: $AGE"
  echo "Cache-Control: max-age=$TTL"
  echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
  echo ""
  /usr/local/bin/jq -c '.' "$OUTPUT"
endif

done:

echo `date` "$0 $$ -- FINISH" >>& $TMP/LOG
