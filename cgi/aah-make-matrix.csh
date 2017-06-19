#!/bin/csh -fb
setenv APP "aah"
setenv API "matrix"
setenv LAN "192.168"
setenv WWW "$LAN".32
setenv WAN "www.dcmartin.com"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

setenv DEBUG true

if ($?TTL == 0) set TTL = 5
if ($?SECONDS == 0) set SECONDS = `/bin/date "+%s"`
if ($?DATE == 0) set DATE = `/bin/echo $SECONDS \/ $TTL \* $TTL | /usr/bin/bc`

if (-e ~$USER/.cloudant_url) then
    set cc = ( `cat ~$USER/.cloudant_url` )
    if ($#cc > 0) set CU = $cc[1]
    if ($#cc > 1) set CN = $cc[2]
    if ($#cc > 2) set CP = $cc[3]
endif

if ($?CLOUDANT_URL) then
    set CU = $CLOUDANT_URL
else if ($?CN && $?CP) then
    set CU = "$CN":"$CP"@"$CN.cloudant.com"
else
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- no Cloudant URL" >>! $TMP/LOG
    goto done
endif

#
# SETUP THE PROBLEM
#

set JSON = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
set TEST = "$TMP/$APP-$API-$QUERY_STRING-test.$DATE.json"
set CSV = "$TMP/$APP-$API-$QUERY_STRING-test.$DATE.csv"
set CSV = "$TMP/matrix/$model.csv"

if ((-s "$JSON") && (-s "$CSV") && (-M "$JSON") <= (-M "$CSV")) then
    echo `date` "$0 $$ -- EXISTING && UP-TO-DATE $JSON" >& /dev/stderr
    goto output
endif

if ((-M "$TEST") > (-M "$JSON") || (-M "$JSON") > (-M "$CSV")) then
    echo `date` "$0 $$ -- rebuilding matrix" >& /dev/stderr
    # remove all residuals
    rm -f "$JSON:r".*
endif

#
# PROCESS THE TEST RESULTS
#

set sets = ( `/usr/local/bin/jq -r '.sets[].set' "$TEST"` )
if ($#sets) then
  echo `date` "$0 $$ -- building $JSON on $#sets ($sets)" >>! "$TMP/LOG"

  unset matrix
  set total = 0

  foreach this ( $sets )
    echo -n `date` "$0 $$ -- $this [ " >& /dev/stderr
    if (! -s "$TMP/matrix/$model.$this.json") then
	/usr/local/bin/jq -c '.sets[]|select(.set=="'"$this"'").results[]?' "$TEST" >! "$TMP/matrix/$model.$this.json"
    endif
    # make matrix
    if ($?matrix) then
        set matrix = "$matrix"',{"set":"'$this'","truth":'
    else
	set names = ( `/usr/local/bin/jq '.sets[].set' "$TEST"` )
	set tested_on = `/usr/local/bin/jq -r '.date' "$TEST"`
	set names = `echo "$names" | sed 's/ /,/g'`
	set matrix = '{"name":"'"$device"'","model":"'"$model"'","date":'"$tested_on"',"size":'$#sets',"sets":['"$names"'],"matrix":[{"set":"'$this'","truth":'
	unset names
    endif
    unset truth
    foreach class ( $sets )
      echo -n "$class " >& /dev/stderr
      if (! -s "$TMP/matrix/$model.$this.$class.csv") then
	@ match = 0
	set noglob
	@ count = 0
	foreach line ( `cat "$TMP/matrix/$model.$this.json"` )
	  set id = `echo "$line" | /usr/local/bin/jq -r '.id'`
	  if ($id != "null") then
	    set score = `echo "$line" | /usr/local/bin/jq -r '.classes[]|select(.class=="'"$class"'").score'`
	    set top = `echo "$line" | /usr/local/bin/jq -r '.classes|sort_by(.score)[-1].class'`
	    if ($class == $top) @ match++
	    echo "$id,$score" >>! "$TMP/matrix/$model.$this.$class.csv.$$"
	    @ count++
	  endif
	end
	unset noglob
	echo "id,label,$class" >! "$TMP/matrix/$model.$this.$class.csv"
	cat "$TMP/matrix/$model.$this.$class.csv.$$" | sed "s/\(.*\),\(.*\)/\1,$this,\2/" >> "$TMP/matrix/$model.$this.$class.csv"
	rm -f "$TMP/matrix/$model.$this.$class.csv.$$"
	if ($?found) then
	  set found = ( $found $class )
	else
	  set found = ( $class )
	endif
	if ($?truth) then
	  set truth = "$truth"','"$match"
	else
	  set truth = '['"$match"
	endif
      endif
    end
    if ($?truth) then
      set matrix = "$matrix""$truth"'],"count":'"$count"'}'
    else
      set matrix = "$matrix"'null}'
    endif
    @ total += $count
    if ($?found) then
      set out = ( "$TMP/matrix/$model.$this".*.csv )
      set found = `echo "$found" | sed 's/ /,/g'`
      csvjoin -c "id" $out | csvcut -c "id,label,$found" >! "$TMP/matrix/$model.$this.csv"
      unset found
      rm -f $out
    endif
    rm "$TMP/matrix/$model.$this.json"
    echo "]" >& /dev/stderr
  end
  set matrix = "$matrix"'],"count":'$total'}'

  echo "$matrix" | /usr/local/bin/jq . >! "$TMP/matrix/$model.json"
  echo `date` "$0 $$ -- MADE $TMP/matrix/$model.json" >& /dev/stderr

  set out = ( "$TMP/matrix/$model".*.csv )
  if ($#out) then
    head -1 $out[1] >! "$TMP/matrix/$model.csv"
    tail +2 -q $out >> "$TMP/matrix/$model.csv"
    echo `date` "$0 $$ -- MADE $TMP/matrix/$model.csv" >& /dev/stderr
  else
    echo `date` "$0 $$ -- FAILURE $TMP/matrix/$model.csv" >& /dev/stderr
  endif
endif

rm -f $out

