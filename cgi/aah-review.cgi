#!/bin/tcsh -b
setenv APP "aah"
setenv API "review"

# debug on/off
setenv DEBUG true
setenv VERBOSE true

# environment
if ($?LAN == 0) setenv LAN "192.168.1"
if ($?DIGITS == 0) setenv DIGITS "$LAN".30
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"
if ($?CREDENTIALS == 0) setenv CREDENTIALS /usr/local/etc
if ($?LOGTO == 0) setenv LOGTO /dev/stderr

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

# don't update statistics more than once per (in seconds)
setenv TTL 1800
setenv SECONDS `date "+%s"`
setenv DATE `/bin/echo $SECONDS \/ $TTL \* $TTL | bc`

# default image limit
if ($?IMAGE_LIMIT == 0) setenv IMAGE_LIMIT 100

if ($?QUERY_STRING) then
    set db = `/bin/echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
    set class = `/bin/echo "$QUERY_STRING" | sed 's/.*class=\([^&]*\).*/\1/'`
    if ($class == "$QUERY_STRING") unset class
    set limit = `/bin/echo "$QUERY_STRING" | sed 's/.*limit=\([^&]*\).*/\1/'`
    if ($limit == "$QUERY_STRING") unset limit
endif

if ($?db == 0) set db = "rough-fog"
if ($?class == 0) set class = "all"
if ($?limit == 0) set limit = $IMAGE_LIMIT

# standardize QUERY_STRING (rendezvous w/ APP-make-API.csh script)
setenv QUERY_STRING "db=$db"
if ($?since) then
  setenv QUERY_STRING "$QUERY_STRING&since=$since"
endif
if ($?limit) then
  setenv QUERY_STRING "$QUERY_STRING&limit=$limit"
endif

/bin/echo `date` "$0 $$ -- START ($QUERY_STRING)" >>! $LOGTO

# initiate new output
if ($?DEBUG) /bin/echo `date` "$0 $$ ++ REQUESTING ./$APP-make-$API.bash" >>! $LOGTO
./$APP-make-$API.bash

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

#
# find cache
#
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"

if (! -s "$OUTPUT") then
  /bin/rm -f "$OUTPUT:r:r".*

  curl -s -q -f -L "$HTTP_HOST/CGI/aah-images.cgi?db=$db&limit=$limit" \
        | jq -r '.ids[]?' \
        | /usr/bin/xargs -I % curl -s -q -f -L "$HTTP_HOST/CGI/aah-updates.cgi?db=$db&id=%" \
        | jq -j '.class,"/",.id,".jpg\n"' >! "$OUTPUT"
endif

if (-s "$OUTPUT") then
    set output = '{"images":'
    foreach i ( `/bin/cat "$OUTPUT"` )
      if (-s "$TMP/$db/$i") then
        if ($?stat) then
          set output = "$output"','
        else
          set output = "$output"'['
        endif
	set stat = "$i"
        set output = "$output"'"'"$i"'"'
      else if (-l "$TMP/$db/$i") then
        if ($?DEBUG) /bin/echo `date` "$0 $$ -- $TMP/$db/$i linked" >>&! $LOGTO
      else
        if ($?DEBUG) /bin/echo `date` "$0 $$ -- $TMP/$db/$i missing" >>&! $LOGTO
      endif
    end
    if ($?stat) then
      set output = "$output"']'
    else
      set output = "$output"'null'
    endif
    set output = "$output"'}'
    goto output
else
  if ($?DEBUG) /bin/echo `date` "$0 $$ -- no $OUTPUT exists" >>&! $LOGTO
  goto done
endif



  if ($class == "any" || $class == "all") then
    set out = "/tmp/$0:t.$$.json"
    set url = "$db-$API/_all_docs"
    curl -m 5 -s -q -f -L "$CU/$url" -o "$out"
    if ($status != 22 && $status != 28 && -s "$out") then
      set classes = ( `jq -r '.rows[]?.id' "$out"` )
      if ($?DEBUG) /bin/echo `date` "$0 $$ ++ SUCCESS ($classes)" >>&! $LOGTO
      rm -f "$out"
    else 
      if ($?DEBUG) /bin/echo `date` "$0 $$ ++ FAILURE ($url)" >>&! $LOGTO
      rm -f "$out"
      goto done
    endif
    if ($class == "all") then
      /bin/echo '{"date":'"$DATE"',"name":"'"$db"'","count":'$#classes',"classes":[' >! "$OUTPUT.$$"
    else 
      /bin/echo '{"date":'"$since"',"name":"'"$db"'","classes":[' >! "$OUTPUT.$$"
    endif
    @ k = 0
    set all = "/tmp/$0:t.$$.csv"
    foreach c ( $classes )
      set url = "$db-$API/$c"
      set out = "/tmp/$0:t.$$.json"
      curl -s -q -f -L "$CU/$url" -o "$out"
      if ($status == 22 || ! -s "$out") then
	if ($?DEBUG) /bin/echo `date` "$0 $$ ++ FAIL ($url)" >>&! $LOGTO
	rm -f "$out"
	continue
      endif
      if ($class != "any") then
	if ($k) /bin/echo ',' >> "$OUTPUT.$$"
        jq '{"name":"'"$c"'","date":.date,"count":.count }' "$out" >> "$OUTPUT.$$"
	@ k++
      else
        jq -j '.ids[]?|select(.date>'"$since"')|.date,",","'"$c"'",",",.id,"\n"' "$out" >>! "$all"
      endif
    end
    if ($class == "any") then
      sort -t, -k1,1 -nr "$all" | head -"$limit" >! "$all.$$"
      set classes = ( `awk -F, '{ print $2 }' "$all.$$" | sort | uniq` )
      @ k = 0
      foreach c ( $classes )
	if ($k) /bin/echo ',' >> "$OUTPUT.$$"
        /bin/echo '{"class":"'"$c"'","ids":[' >> "$OUTPUT.$$"
	egrep ','"$c"',' "$all.$$" | awk -F, '{ printf("\"%s\",", $3) }' | sed 's/,$//' >> "$OUTPUT.$$"
        /bin/echo ']}' >> "$OUTPUT.$$"
	@ k++
      end
      rm -f "$all" "$all.$$"
    endif
    /bin/echo ']}' >> "$OUTPUT.$$"
    mv "$OUTPUT.$$" "$OUTPUT"
  else if ($class == "all") then
    set url = "https://$CU/$db-$API/$class"
    curl -s -q -f -L "$url" | jq '{"name":.name,"date":.date,"count":.count,"classes":.classes}' >! "$OUTPUT"
  else
    set url = "https://$CU/$db-$API/$class"
    curl -s -q -f -L "$url" | jq '{"name":.name,"date":.date,"count":.count,"ids":.ids}' >! "$OUTPUT"
  endif
endif

#
# output
#

output:

/bin/echo "Content-Type: application/json; charset=utf-8"
/bin/echo "Access-Control-Allow-Origin: *"

if (-s "$OUTPUT") then
    @ age = $SECONDS - $DATE
    /bin/echo "Age: $age"
    @ refresh = $TTL - $age
    # check back if using old
    if ($refresh < 0) @ refresh = $TTL
    /bin/echo "Refresh: $refresh"
    /bin/echo "Cache-Control: max-age=$TTL"
    /bin/echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
    /bin/echo ""
    jq -c '.' "$OUTPUT"
    if ($?DEBUG) /bin/echo `date` "$0 $$ -- output ($OUTPUT) Age: $age Refresh: $refresh" >>! $LOGTO
else
    /bin/echo "Cache-Control: no-cache"
    /bin/echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
    /bin/echo ""
    /bin/echo '{ "error": "not found" }'
endif

cleanup:
  rm -f "$OUTPUT".$$

done:
  /bin/echo `date` "$0 $$ -- FINISH ($QUERY_STRING)" >>! $LOGTO

