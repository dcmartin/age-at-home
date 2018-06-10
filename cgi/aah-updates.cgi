#!/bin/tcsh -b
setenv APP "aah"
setenv API "updates"

# debug on/off
setenv DEBUG true
setenv VERBOSE true

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

# environment
if ($?LAN == 0) setenv LAN "192.168.1"
if ($?DIGITS == 0) setenv DIGITS "$LAN".30
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"
if ($?CREDENTIALS == 0) setenv CREDENTIALS /usr/local/etc
if ($?LOGTO == 0) setenv LOGTO /dev/stderr

# don't update statistics more than once per (in seconds)
setenv TTL 5
setenv SECONDS `date "+%s"`
setenv DATE `echo $SECONDS \/ $TTL \* $TTL | bc`
# default image limit
if ($?UPDATE_LIMIT == 0) setenv UPDATE_LIMIT 1000000
if ($?UPDATE_SET_LIMIT == 0) setenv UPDATE_SET_LIMIT 100

if ($?QUERY_STRING) then
    set db = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
    set id = `echo "$QUERY_STRING" | sed 's/.*id=\([^&]*\).*/\1/'`
    if ($id == "$QUERY_STRING") unset id
    set force = `echo "$QUERY_STRING" | sed 's/.*force=\([^&]*\).*/\1/'`
    if ($force == "$QUERY_STRING") unset force
    set limit = `echo "$QUERY_STRING" | sed 's/.*limit=\([^&]*\).*/\1/'`
    if ($limit == "$QUERY_STRING") unset limit
    set since = `echo "$QUERY_STRING" | sed 's/.*since=\([^&]*\).*/\1/'`
    if ($since == "$QUERY_STRING") unset since
    set include_scores = `echo "$QUERY_STRING" | sed 's/.*include_scores=\([^&]*\).*/\1/'`
    if ($include_scores == "$QUERY_STRING") unset include_scores
endif

if ($?db == 0) set db = all
if ($?id && $db == "all") unset id
if ($?since && $?id) unset id
if ($?id == 0 && $?include_scores) unset include_scores

if ($?limit) then
  if ($limit > $UPDATE_LIMIT) set limit = $UPDATE_LIMIT
else
  set limit = $UPDATE_SET_LIMIT
endif

# standardize QUERY_STRING (rendezvous w/ APP-make-API.csh script)
setenv QUERY_STRING "db=$db"

if ($?VERBOSE) echo `date` "$0 $$ -- START ($QUERY_STRING)" >>! $LOGTO

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
  echo `date` "$0:t $$ -- FAILURE: no Cloudant credentials" >>& $LOGTO
  goto done
endif

# output target
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
# test if been-there-done-that
if ($?id == 0 && $?since == 0 && $?force == 0 && -s "$OUTPUT") goto output
/bin/rm -f "$OUTPUT:r:r".*

# handle singleton
if ($db != "all" && $?id) then
  set url = "$CU/$db-updates/$id"
  set out = "/tmp/$0:t.$$.json"
  curl -s -q -f -L "$url" -o "$out"
  if ($status == 22 || $status == 28 || ! -s "$out") then
    /bin/rm -f "$out"
    set output = '{"error":"not found","db":"'"$db"'","id":"'"$id"'"}'
  else 
    set class = ( `jq -r '.class' "$out" | sed "s/ /_/g"` )
    set model = ( `jq -r '.model' "$out" | sed "s/ /_/g"` )
    # handle special case for Watson default classifier
    if ($model =~ "/*") then
      set class = "$model"
      set model = "default"
    endif
    set output = ( `jq '{"id":._id,"date":.date,"class":"'"$class"'","model":"'"$model"'","score":.score,"count":.count,"min":.min,"max":.max,"sum":.sum,"mean":.mean,"stdev":.stdev,"kurtosis":.kurtosis}' "$out"` )
    if ($?include_scores) then
      set event = ( `curl -s -q -f -L "$CU/$db/$id" | jq '.'` )
      set output = ( `echo "$output" | sed 's/}//'` )

      set output = "$output"',"scores":'
      if ($#event) then
	set output = "$output"'['
        set models = ( `echo "$event" | jq -r '.visual.scores[].name' | sed 's/ /_/g' | /usr/bin/sort | /usr/bin/uniq` )
        if ($#models) then
	  # special case for Watson VR default classifier
          foreach m ( $models )
            # handle hierarchies (/*) as special case for Watson default classifier
            if ($m =~ "/*") continue # only type hierarchies have spaces in "name" field
	    if ($?classes) set output = "$output"','
            set output = "$output"'{"model":"'"$m"'","classes":'
            set classes = ( `echo "$event" | jq -r '.visual.scores[]|select(.name=="'"$m"'").classifier_id' | sed 's/ /_/g'` )
	    if ($#classes) then
	      set output = "$output"'['
	      unset val
	      foreach c ( $classes )
		if ($?val) set output = "$output"','
	        set cid = ( `echo "$c" | sed 's/_/ /g'` )
	        set val = ( `echo "$event" | jq -r '.visual.scores[]|select(.name=="'"$m"'")|select(.classifier_id=="'"$cid"'").score'` )
		set output = "$output"'{"class":"'"$c"'","score":'"$val"'}'
              end
	      if ($m == "default") then
	        set types = ( `echo "$event" | jq -r '.visual.scores[].name|match("/.*";"g")|.string' | sed 's/ /_/g'` )
	        foreach t ( $types )
		  if ($?val) set output = "$output"','
	          set tid = ( `echo "$t" | sed 's/_/ /g'` )
	          set val = ( `echo "$event" | jq -r '.visual.scores[]|select(.name=="'"$tid"'").score'` )
		  set output = "$output"'{"class":"'"$t"'","score":'"$val"'}'
	        end
	      endif
	      set output = "$output"']'
            else
	      set output = "$output"'null'
	    endif
	    set output = "$output"'}'
	  end 
	  set output = "$output"']'
	else # no models
	  set output = "$output"'null'
	endif
      endif
      set output = "$output"'}'
    endif # include_scores
  endif # found
  /bin/rm -f "$out"
  goto output
endif

##
## HANDLE ALL DEVICES (non-singleton)
##

# find devices
if ($db == "all") then
  set url = "$HTTP_HOST/CGI/aah-devices.cgi"
  set devices = ( `curl -s -q -L "$url" | jq -r '.devices[].name'` )
  if ($#devices == 0) then
    if ($?VERBOSE) echo `date` "$0 $$ ++ FAILURE ($url)" >>&! $LOGTO
    goto done
  endif
else
  set devices = ($db)
endif

if ($?VERBOSE) echo `date` "$0 $$ ++ SUCCESS -- devices ($devices)" >>&! $LOGTO

@ k = 0
set all = '{"date":'"$DATE"',"devices":['
foreach d ( $devices )

  # initiate new output
  set qs = "$QUERY_STRING"
  setenv QUERY_STRING "device=$d"
  if ($?force) then
    setenv QUERY_STRING "$QUERY_STRING&force=true"
  endif
  if ($?DEBUG) echo `date` "$0 $$ ++ REQUESTING ./$APP-make-$API.bash ($QUERY_STRING)" >>! $LOGTO
  ./$APP-make-$API.bash
  setenv QUERY_STRING "$qs"

  # get device entry
  set url = "device-$API/$d"
  set out = "/tmp/$0:t.$$.json"
  curl -s -q -f -L "$CU/$url" -o "$out"
  if ($status == 22 || $status == 28 || ! -s "$out") then
    if ($?VERBOSE) echo `date` "$0 $$ ++ FAILURE ($url) ($status)" >>&! $LOGTO
    /bin/rm -f "$out"
    continue
  endif
  set cd = `jq -r '.date?' "$out"`; if ($cd == "null") set cd = 0
  set cc = `jq -r '.count?' "$out"`; if ($cc == "null") set cc = 0
  set ct = `jq -r '.total?' "$out"`; if ($ct == "null") set ct = 0
  if ($db != "all" && $d == "$db") then
    if ($?since) then
      if ($?force && $limit < $ct) set limit = $ct
      set url = "$db-updates/_all_docs?include_docs=true&descending=true&limit=$limit"
    else
      set url = "$db-updates/_all_docs?include_docs=true&descending=true&limit=$UPDATE_SET_LIMIT"
    endif
    # get updates
    curl -s -q -f -L "$CU/$url" -o "$out"
    if ($status == 22 || $status == 28 || ! -s "$out") then
      if ($?VERBOSE) echo `date` "$0 $$ ++ FAILURE ($url) ($status)" >>&! $LOGTO
      echo '{"name":"'"$d"'","date":'"$cd"',"count":0,"total":'"$ct"',"ids":[] }' >! "$OUTPUT"
    else
      set total_rows = ( `jq '.total_rows' "$out"` )
      if ($?since == 0) then
        set ids = ( `jq '[limit('"$cc"';.rows?|sort_by(.id)|reverse[].doc|select(.date<='"$cd"')._id)]' "$out"` )
        set cc = ( `echo "$ids" | jq '.|length'` )
        echo '{"name":"'"$d"'","date":'"$cd"',"count":'"$cc"',"total":'"$ct"',"limit":'"$limit"',"ids":'"$ids"' }' >! "$OUTPUT"
      else if ($?since) then
        set all = ( `jq -r '.rows[]?.doc|select(.date<='"$cd"')|select(.date>'"$since"')._id' "$out"` )
        set len = $#all
	if ($limit > $len) then
          set ids = ( $all[1-$len] )
        else
          set ids = ( $all[1-$limit] )
        endif
        set num = $#ids
	if ($num > 0) then
          set all = ( `echo "$ids" | sed 's/\([^ ]*\)/"\1"/g' | sed 's/ /,/g'` )
	else
  	  set all = ""
	endif
        echo '{"name":"'"$d"'","date":'"$cd"',"count":'"$num"',"total":'"$len"',"limit":'"$limit"',"ids":['"$all"']}' >! "$OUTPUT"
      else
        set ids = ( `jq '[.rows?|sort_by(.id)|reverse[].doc|select(.date<='"$cd"')._id]' "$out"` )
        set cc = ( `echo "$ids" | jq '.|length'` )
        echo '{"name":"'"$d"'","date":'"$cd"',"count":'"$cc"',"total":'"$ct"',"limit":'"$limit"',"ids":'"$ids"' }' >! "$OUTPUT"
      endif
    endif
    /bin/rm -f "$out"
    goto output
  else if ($db == "all") then
    set json = '{"name":"'"$d"'","date":'"$cd"',"count":'"$cc"',"total":'"$ct"'}'
  else
    unset json
  endif
  /bin/rm -f "$out"
  if ($k) set all = "$all"','
  @ k++
  if ($?json) then
    set all = "$all""$json"
  endif
end
set all = "$all"']}'

echo "$all" | jq -c '.' >! "$OUTPUT"

#
# output
#

output:

echo "Content-Type: application/json; charset=utf-8"
echo "Access-Control-Allow-Origin: *"

# echo "Content-Location: $HTTP_HOST/CGI/$APP-$API.cgi?$QUERY_STRING"

if ($?output == 0 && -s "$OUTPUT") then
  @ age = $SECONDS - $DATE
  echo "Age: $age"
  @ refresh = $TTL - $age
  # check back if using old
  if ($refresh < 0) @ refresh = $TTL
  echo "Refresh: $refresh"
  echo "Cache-Control: max-age=$TTL"
  echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
  echo ""
  jq -c '.' "$OUTPUT"
  if ($?VERBOSE) echo `date` "$0 $$ -- output ($OUTPUT) Age: $age Refresh: $refresh" >>! $LOGTO
else
  echo "Cache-Control: no-cache"
  echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`
  echo ""
  if ($?output) then
    echo "$output"
  else
    echo '{ "error": "not found" }'
  endif
endif

# done

done:

if ($?VERBOSE) echo `date` "$0 $$ -- FINISH ($QUERY_STRING)" >>! $LOGTO
