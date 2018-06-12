#!/bin/tcsh -b
setenv APP "aah"
setenv API "models"

# setenv DEBUG true
# setenv VERBOSE true

# environment
if ($?LAN == 0) setenv LAN "192.168.1"
if ($?DIGITS == 0) setenv DIGITS "$LAN".30
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

# don't update service cache(s) (and this service output) more than once per (in seconds)
set TTL = `echo "60 * 1 * 1  * 1" | bc`
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

###
### START
###

echo "$0:t $$" `date` "START" >>&! $LOGTO

## PROCESS query string
if ($?QUERY_STRING) then
    set db = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
    set model = `echo "$QUERY_STRING" | sed 's/.*model=\([^&]*\).*/\1/'`
    if ($model == "$QUERY_STRING") unset model
    set include_ids = `echo "$QUERY_STRING" | sed 's/.*include_ids\([^&]*\).*/\1/'`
    if ($include_ids == "$QUERY_STRING") unset include_ids
endif
if ($?db == 0) set db = "rough-fog"
setenv QUERY_STRING "db=$db"
if ($?model) then
  setenv QUERY_STRING "$QUERY_STRING"'&model='"$model"
endif
if ($?include_ids) then
  setenv QUERY_STRING "$QUERY_STRING"'&include_ids=true'
endif

## ACCESS CLOUDANT
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
  echo `date` "$0:t $$ -- FAILURE: no Cloudant credentials" >>&! $LOGTO
  goto done
endif

##
## OUTPUT
##

set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

if (-s "$OUTPUT") then
  if ($?VERBOSE) echo "EXISTING OUTPUT $OUTPUT" >>&! $LOGTO
else
  if ($?VERBOSE) echo "BUILDING OUTPUT $OUTPUT" >>&! $LOGTO
  set TRAIN = "$TMP/$APP-$API-$db-train.$DATE.json" 
  if (! -s "$TRAIN") then
    if ($?VERBOSE) echo "NO TRAINING DATA $TRAIN" >>&! $LOGTO
    set url = "$CU/$db-train/_all_docs?include_docs=true" 
    if ($?DEBUG) echo "RETRIEVE TRAINING DATA ($TRAIN) FROM CLOUDANT ($url)" >>&! $LOGTO
    curl -s -q -f -L "$url" -o "$TRAIN.$$"
    if ($status == 22 || ! -s "$TRAIN.$$") then
      if ($?DEBUG) echo "FAILURE -- $TRAIN from $url" >>&! $LOGTO
      set old = ( `echo "$TRAIN:r:r".*` )
      if ($?old) then
        if ($?VERBOSE) echo "OLD TRAINING FILES (COUNT = $#old)" >>&! $LOGTO
        if ($#old) then
          if (-s "$old[$#old]") then
            set TRAIN = "$old[$#old]"
          else
            if ($?VERBOSE) echo "no existing $old[$#old] for $TRAIN" >>&! $LOGTO
            unset TRAIN
          endif
        endif
      else
        if ($?VERBOSE) echo "NO OLD TRAINING FILES: $TRAIN" >>&! $LOGTO
        unset TRAIN
      endif
    else if (-s "$TRAIN.$$") then
      if ($?VERBOSE) echo "SUCCESS -- $TRAIN from $url" >>&! $LOGTO
      mv -f "$TRAIN.$$" "$TRAIN"
      if ($?old) then
        @ i = 1
        while ($i <= $#old) 
          if ($?DEBUG) echo `date` "$0:t $$ -- DEBUG: removing $i/$#old from $old" >>&! $LOGTO
          rm -f "$old[$i]"
          @ i++
        end
      endif
    else
      if ($?DEBUG) echo "FAILURE -- $url" >>&! $LOGTO
      unset TRAIN
    endif
  endif

  # process training information
  if ($?TRAIN == 0) then
    if ($?VERBOSE) echo "no training data" >>&! $LOGTO
  else if (! -s "$TRAIN") then
    if ($?VERBOSE) echo "no training cache $TRAIN" >>&! $LOGTO
  else
    set models = ( `jq -r '.rows[].id' "$TRAIN"` )
    if ($status == 0 && $#models) then
      if ($?VERBOSE) echo "found models $models" >>&! $LOGTO
      foreach m ( $models )
        if ($?model) then
          if ("$m" != "$model") then
            if ($?VERBOSE) echo "model $model only; skipping non-matching model ($m)" >>&! $LOGTO
            continue
          endif
        endif
        if ($?include_ids) then
          if ($?VERBOSE) echo "finding row for model ($m) including ids" >>&! $LOGTO
          jq '.rows[]|select(.id=="'$m'")' "$TRAIN" | \
            jq '{"model":.id,"date":.doc.date,"device":.doc.name,"labels":[.doc.images[]|{"class":.class,"bytes":.bytes,"count":.count,"ids":.ids}],"negative":.doc.negative,"classes":.doc.classes,"detail":.doc.detail}' >! "$OUTPUT.$$.$$"
        else
          if ($?VERBOSE) echo "finding row for model ($m)" >>&! $LOGTO
          jq '.rows[]|select(.id=="'$m'")' "$TRAIN" | \
            jq '{"model":.id,"date":.doc.date,"device":.doc.name,"labels":[.doc.images[]|{"class":.class,"bytes":.bytes,"count":.count}],"negative":.doc.negative,"classes":.doc.classes,"detail":.doc.detail}' >! "$OUTPUT.$$.$$"
        endif
        if ($status == 0 && -s "$OUTPUT.$$.$$") then
          if ($?DEBUG) echo "FOUND model ($m)" >>&! $LOGTO
          if ($?model) then
            # found one model
            jq -c '.' "$OUTPUT.$$.$$" >>! "$OUTPUT.$$"
            break
          else
            if (! -e "$OUTPUT.$$") then
              # start list of matching models
              echo '{ "models": [' >! "$OUTPUT.$$"
            else 
              echo ',' >> "$OUTPUT.$$"
            endif
            jq -c '.' "$OUTPUT.$$.$$" >> "$OUTPUT.$$"
          endif
        else
          if ($?DEBUG) echo "DID NOT FIND model ($m)" >>&! $LOGTO
        endif
        rm -f "$OUTPUT.$$.$$"
      end
      if ($?model == 0) then
        # terminate list of matching models
        echo ']}' >>! "$OUTPUT.$$"
      endif
      if (-s "$OUTPUT.$$") then
        if ($?VERBOSE) echo "testing output for JSON" >>&! $LOGTO
        jq -c '.' "$OUTPUT.$$" >! "$OUTPUT"
	if ($status != 0) then
	  if ($?DEBUG) echo "bad json" `cat $OUTPUT.$$` >>&! $LOGTO
	  rm -f "$OUTPUT" "$OUTPUT.$$"
        else
	  if ($?DEBUG) echo "good json" >>&! $LOGTO
          rm -f "$OUTPUT.$$"
	endif
      else
        if ($?DEBUG) echo "no or zero size output" >>&! $LOGTO
        rm -f "$OUTPUT.$$"
      endif
    else
      if ($?DEBUG) echo "no models in $TRAIN" >>&! $LOGTO
      goto output
    endif
  endif
endif

output:

if (! -s "$OUTPUT") then
  if ($?DEBUG) echo `date` "$0:t $$ -- no models found ($db)" >>&! $LOGTO
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
  echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
  echo ""
  jq -c '.' "$OUTPUT"
endif

done:

echo `date` "$0:t $$ -- FINISH" >>&! $LOGTO
