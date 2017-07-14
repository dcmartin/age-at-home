#!/bin/csh -fb
setenv APP "aah"
setenv API "updates"
setenv LAN "192.168.1"
setenv WWW "$LAN".32
setenv DIGITS "$LAN".30
setenv WAN "www.dcmartin.com"
setenv TMP "/var/lib/age-at-home"

# setenv DEBUG true

# don't update statistics more than once per (in seconds)
setenv TTL 5
setenv SECONDS `date "+%s"`
setenv DATE `/bin/echo $SECONDS \/ $TTL \* $TTL | bc`
# default image limit
if ($?UPDATE_LIMIT == 0) setenv UPDATE_LIMIT 1000000
if ($?UPDATE_SET_LIMIT == 0) setenv UPDATE_SET_LIMIT 100

if ($?QUERY_STRING) then
    set db = `/bin/echo "$QUERY_STRING" | /usr/bin/sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
    set id = `/bin/echo "$QUERY_STRING" | /usr/bin/sed 's/.*id=\([^&]*\).*/\1/'`
    if ($id == "$QUERY_STRING") unset id
    set force = `/bin/echo "$QUERY_STRING" | /usr/bin/sed 's/.*force=\([^&]*\).*/\1/'`
    if ($force == "$QUERY_STRING") unset force
    set limit = `/bin/echo "$QUERY_STRING" | /usr/bin/sed 's/.*limit=\([^&]*\).*/\1/'`
    if ($limit == "$QUERY_STRING") unset limit
    set since = `/bin/echo "$QUERY_STRING" | /usr/bin/sed 's/.*since=\([^&]*\).*/\1/'`
    if ($since == "$QUERY_STRING") unset since
    set include_scores = `/bin/echo "$QUERY_STRING" | /usr/bin/sed 's/.*include_scores=\([^&]*\).*/\1/'`
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

if ($?VERBOSE) /bin/echo `date` "$0 $$ -- START ($QUERY_STRING)" >>! $TMP/LOG

#
# get read-only access to cloudant
#
if (-e ~$USER/.cloudant_url) then
    set cc = ( `cat ~$USER/.cloudant_url` )
    if ($#cc > 0) set CU = $cc[1]
    if ($#cc > 1) set CN = $cc[2]
    if ($#cc > 2) set CP = $cc[3]
    set CU = "$CN":"$CP"@"$CU"
endif
if ($?CU == 0) then
    /bin/echo `date` "$0 $$ -- no Cloudant URL" >>! $TMP/LOG
    goto done
endif

# output target
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
# test if been-there-done-that
if ($?id == 0 && $?since == 0 && $?force == 0 && -s "$OUTPUT") goto output
rm -f "$OUTPUT:r:r".*

# handle singleton
if ($db != "all" && $?id) then
  set url = "$CU/$db-updates/$id"
  set out = "/tmp/$0:t.$$.json"
  /usr/bin/curl -s -q -f -L "$url" -o "$out"
  if ($status == 22 || $status == 28 || ! -s "$out") then
    set output = '{"error":"not found","db":"'"$db"'","id":"'"$id"'"}'
  else 
    set class = ( `/usr/local/bin/jq -r '.class' "$out" | /usr/bin/sed "s/ /_/g"` )
    set model = ( `/usr/local/bin/jq -r '.model' "$out" | /usr/bin/sed "s/ /_/g"` )
    # handle special case for Watson default classifier
    if ($model =~ "/*") then
      set class = "$model"
      set model = "default"
    endif
    set output = ( `/usr/local/bin/jq '{"id":._id,"date":.date,"class":"'"$class"'","model":"'"$model"'","score":.score,"count":.count,"min":.min,"max":.max,"sum":.sum,"mean":.mean,"stdev":.stdev,"kurtosis":.kurtosis}' "$out"` )
    if ($?include_scores) then
      set event = ( `/usr/bin/curl -s -q -f -L "$CU/$db/$id" | /usr/local/bin/jq '.'` )
      set output = ( `/bin/echo "$output" | sed 's/}//'` )

      set output = "$output"',"scores":'
      if ($#event) then
	set output = "$output"'['
        set models = ( `/bin/echo "$event" | /usr/local/bin/jq -r '.visual.scores[].name' | /usr/bin/sed 's/ /_/g' | /usr/bin/sort | /usr/bin/uniq` )
        if ($#models) then
	  # special case for Watson VR default classifier
          foreach m ( $models )
            # handle hierarchies (/*) as special case for Watson default classifier
            if ($m =~ "/*") continue # only type hierarchies have spaces in "name" field
	    if ($?classes) set output = "$output"','
            set output = "$output"'{"model":"'"$m"'","classes":'
            set classes = ( `/bin/echo "$event" | /usr/local/bin/jq -r '.visual.scores[]|select(.name=="'"$m"'").classifier_id' | /usr/bin/sed 's/ /_/g'` )
	    if ($#classes) then
	      set output = "$output"'['
	      unset val
	      foreach c ( $classes )
		if ($?val) set output = "$output"','
	        set cid = ( `/bin/echo "$c" | /usr/bin/sed 's/_/ /g'` )
	        set val = ( `/bin/echo "$event" | /usr/local/bin/jq -r '.visual.scores[]|select(.name=="'"$m"'")|select(.classifier_id=="'"$cid"'").score'` )
		set output = "$output"'{"class":"'"$c"'","score":'"$val"'}'
              end
	      if ($m == "default") then
	        set types = ( `/bin/echo "$event" | /usr/local/bin/jq -r '.visual.scores[].name|match("/.*";"g")|.string' | /usr/bin/sed 's/ /_/g'` )
	        foreach t ( $types )
		  if ($?val) set output = "$output"','
	          set tid = ( `/bin/echo "$t" | /usr/bin/sed 's/_/ /g'` )
	          set val = ( `/bin/echo "$event" | /usr/local/bin/jq -r '.visual.scores[]|select(.name=="'"$tid"'").score'` )
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
  rm -f "$out"
  goto output
endif

# find devices
if ($db == "all") then
  set devices = ( `curl "$WWW/CGI/aah-devices.cgi" | /usr/local/bin/jq -r '.devices[].name'` )
  if ($#devices == 0) then
    if ($?VERBOSE) /bin/echo `date` "$0 $$ ++ FAILURE ($url)" >>&! $TMP/LOG
    goto done
  endif
else
  set devices = ($db)
endif

if ($?VERBOSE) /bin/echo `date` "$0 $$ ++ SUCCESS -- devices ($devices)" >>&! $TMP/LOG

@ k = 0
set all = '{"date":'"$DATE"',"devices":['
foreach d ( $devices )

  # initiate new output
  set qs = "$QUERY_STRING"
  setenv QUERY_STRING "device=$d"
  if ($?force) then
    setenv QUERY_STRING "$QUERY_STRING&force=true"
  endif
  if ($?DEBUG) /bin/echo `date` "$0 $$ ++ REQUESTING ./$APP-make-$API.bash ($QUERY_STRING)" >>! $TMP/LOG
  ./$APP-make-$API.bash
  setenv QUERY_STRING "$qs"

  # get device entry
  set url = "device-$API/$d"
  set out = "/tmp/$0:t.$$.json"
  curl -s -q -f -L "$CU/$url" -o "$out"
  if ($status == 22 || $status == 28 || ! -s "$out") then
    if ($?VERBOSE) /bin/echo `date` "$0 $$ ++ FAILURE ($url) ($status)" >>&! $TMP/LOG
    rm -f "$out"
    continue
  endif
  set cd = `/usr/local/bin/jq -r '.date?' "$out"`; if ($cd == "null") set cd = 0
  set cc = `/usr/local/bin/jq -r '.count?' "$out"`; if ($cc == "null") set cc = 0
  set ct = `/usr/local/bin/jq -r '.total?' "$out"`; if ($ct == "null") set ct = 0
  if ($db != "all" && $d == "$db") then
    if ($?since) then
      if ($?force && $limit < $ct) set limit = $ct
      set url = "$db-updates/_all_docs?include_docs=true&descending=true&limit=$limit"
    else
      set url = "$db-updates/_all_docs?include_docs=true&descending=true&limit=$UPDATE_SET_LIMIT"
    endif
    # get updates
    /usr/bin/curl -s -q -f -L "$CU/$url" -o "$out"
    if ($status == 22 || $status == 28 || ! -s "$out") then
      if ($?VERBOSE) /bin/echo `date` "$0 $$ ++ FAILURE ($url) ($status)" >>&! $TMP/LOG
      echo '{"name":"'"$d"'","date":'"$cd"',"count":0,"total":'"$ct"',"ids":[] }' >! "$OUTPUT"
    else
      set total_rows = ( `/usr/local/bin/jq '.total_rows' "$out"` )
      if ($?since == 0) then
        set ids = ( `/usr/local/bin/jq '[limit('"$cc"';.rows?|sort_by(.id)|reverse[].doc|select(.date<='"$cd"')._id)]' "$out"` )
        set cc = ( `/bin/echo "$ids" | /usr/local/bin/jq '.|length'` )
        echo '{"name":"'"$d"'","date":'"$cd"',"count":'"$cc"',"total":'"$ct"',"limit":'"$limit"',"ids":'"$ids"' }' >! "$OUTPUT"
      else
        set all = ( `/usr/local/bin/jq -r '.rows[]?.doc|select(.date<='"$cd"')|select(.date>'"$since"')._id' "$out"` )
        set len = $#all
	if ($limit > $len) then
          set ids = ( $all[1-$len] )
        else
          set ids = ( $all[1-$limit] )
        endif
        set num = $#ids
	if ($num > 0) then
          set all = ( `/bin/echo "$ids" | /usr/bin/sed 's/\([^ ]*\)/"\1"/g' | sed 's/ /,/g'` )
	else
  	  set all = ""
	endif
        echo '{"name":"'"$d"'","date":'"$cd"',"count":'"$num"',"total":'"$len"',"limit":'"$limit"',"ids":['"$all"']}' >! "$OUTPUT"
      endif
    endif
    rm -f "$out"
    goto output
  else if ($db == "all") then
    set json = '{"name":"'"$d"'","date":'"$cd"',"count":'"$cc"',"total":'"$ct"'}'
  else
    unset json
  endif
  if ($k) set all = "$all"','
  @ k++
  if ($?json) then
    set all = "$all""$json"
  endif
end
set all = "$all"']}'

/bin/echo "$all" | /usr/local/bin/jq -c '.' >! "$OUTPUT"

#
# output
#

output:

/bin/echo "Content-Type: application/json; charset=utf-8"
/bin/echo "Access-Control-Allow-Origin: *"

# /bin/echo "Content-Location: $WWW/CGI/$APP-$API.cgi?$QUERY_STRING"

if ($?output == 0 && -s "$OUTPUT") then
  @ age = $SECONDS - $DATE
  /bin/echo "Age: $age"
  @ refresh = $TTL - $age
  # check back if using old
  if ($refresh < 0) @ refresh = $TTL
  /bin/echo "Refresh: $refresh"
  /bin/echo "Cache-Control: max-age=$TTL"
  /bin/echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
  /bin/echo ""
  /usr/local/bin/jq -c '.' "$OUTPUT"
  if ($?VERBOSE) /bin/echo `date` "$0 $$ -- output ($OUTPUT) Age: $age Refresh: $refresh" >>! $TMP/LOG
else
  /bin/echo "Cache-Control: no-cache"
  /bin/echo "Last-Modified:" `date -r $SECONDS '+%a, %d %b %Y %H:%M:%S %Z'`
  /bin/echo ""
  if ($?output) then
    /bin/echo "$output"
  else
    /bin/echo '{ "error": "not found" }'
  endif
endif

# done

done:

if ($?VERBOSE) /bin/echo `date` "$0 $$ -- FINISH ($QUERY_STRING)" >>! $TMP/LOG
