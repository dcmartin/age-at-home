#!/bin/csh -fb
setenv APP "aah"
setenv API "models"

setenv DEBUG true

if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

# don't update cache more than once per (in seconds)
set TTL = `echo "5 * 1 * 1  * 1" | bc`
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo `date` "$0 $$ -- START" >>& "$TMP/LOG"

if ($?QUERY_STRING) then
    set db = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
endif
if ($?db == 0) set db = "rough-fog"
setenv QUERY_STRING "db=$db"

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
  set TRAIN = "$TMP/$APP-$API-$QUERY_STRING-train.$DATE.json" 
  if (! -s "$TRAIN") then
    set old = ( `echo "$TRAIN:r:r".*` )
    if ($?DEBUG) echo `date` "$0 $$ -- DEBUG: variable (old) is defined (0/1)? ($?old)" >>& "$TMP/LOG"

    echo `date` "$0 $$ -- retrieving from Cloudant: $TRAIN" >>& "$TMP/LOG"
    curl -s -q -f -L "$CU/$db-train/_all_docs?include_docs=true" -o "$TRAIN.$$"
    if ($status == 22 || ! -s "$TRAIN.$$") then
      echo `date` "$0 $$ -- cannot retrieve $TRAIN from $CU/$db-train" >>& "$TMP/LOG"
      if ($?old) then
        if ($#old) then
	  if (-s "$old[$#old]") then
	    set TRAIN = "$old[$#old]"
	  else
	    echo `date` "$0 $$ -- no existing $old[$#old] for $TRAIN" >>& "$TMP/LOG"
	    unset TRAIN
	  endif
	endif
      else
	echo `date` "$0 $$ -- no old for $TRAIN" >>& "$TMP/LOG"
	unset TRAIN
      endif
    else
      echo `date` "$0 $$ -- success retrieving from Cloudant $TRAIN.$$" >>& "$TMP/LOG"
      mv -f "$TRAIN.$$" "$TRAIN"
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
  # process training information
  if ($?TRAIN) then
    if (-s "$TRAIN") then
      set models = ( `/usr/local/bin/jq -r '.rows[].id' "$TRAIN"` )
      if ($status == 0 && $#models) then
	foreach m ( $models )
	  /usr/local/bin/jq '.rows[]|select(.id=="'$m'")' "$TRAIN" | \
	    /usr/local/bin/jq '{"model":.id,"date":.doc.date,"device":.doc.name,"labels":[.doc.images[]|{"class":.class,"bytes":.bytes,"count":.count}],"negative":.doc.negative,"classes":.doc.classes,"detail":.doc.detail}' >! "$OUTPUT.$$.$$"
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
	echo `date` "$0 $$ -- no models in $TRAIN" >>& "$TMP/LOG"
	rm -f "$OUTPUT".*
	goto output
      endif
    else
      echo `date` "$0 $$ -- no training cache $TRAIN" >>& "$TMP/LOG"
    endif
  else
    echo `date` "$0 $$ -- no model data" >>& "$TMP/LOG"
  endif
else
  echo `date` "$0 $$ -- $OUTPUT is up-to-date ($DATE)" >>& "$TMP/LOG"
endif

output:

if (! -s "$OUTPUT") then
  if ($?DEBUG) echo `date` "$0 $$ -- no models found ($db)" >>& "$TMP/LOG"
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
