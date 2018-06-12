#!/bin/tcsh -b
setenv APP "aah"
setenv API "matrix"

# debug on/off
setenv DEBUG true
setenv VERBOSE true

# environment
if ($?LAN == 0) setenv LAN "192.168.1"
if ($?DIGITS == 0) setenv DIGITS "$LAN".30
if ($?TMP == 0) setenv TMP "/tmp"
if ($?AAHDIR == 0) setenv AAHDIR "/var/lib/age-at-home"
if ($?CREDENTIALS == 0) setenv CREDENTIALS /usr/local/etc
if ($?LOGTO == 0) setenv LOGTO $TMP/$APP.log

if ($?TTL == 0) set TTL = 5
if ($?SECONDS == 0) set SECONDS = `/bin/date "+%s"`
if ($?DATE == 0) set DATE = `/bin/echo $SECONDS \/ $TTL \* $TTL | /usr/bin/bc`

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
  /bin/echo `date` "$0:t $$ -- FAILURE: no Cloudant credentials" >>&! $LOGTO
  goto done
endif

#
# SETUP THE PROBLEM
#

set JSON = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
set TEST = "$TMP/$APP-$API-$QUERY_STRING-test.$DATE.json"
set CSV = "$TMP/$APP-$API-$QUERY_STRING-test.$DATE.csv"
set CSV = "$AAHDIR/matrix/$model.csv"

if ((-s "$JSON") && (-s "$CSV") && (-M "$JSON") <= (-M "$CSV")) then
    /bin/echo `date` "$0 $$ -- EXISTING && UP-TO-DATE $JSON" >& /dev/stderr
    goto output
endif

if ((-M "$TEST") > (-M "$JSON") || (-M "$JSON") > (-M "$CSV")) then
    /bin/echo `date` "$0 $$ -- rebuilding matrix" >& /dev/stderr
    # remove all residuals
    rm -f "$JSON:r".*
endif

#
# PROCESS THE TEST RESULTS
#

set sets = ( `jq -r '.sets[].set' "$TEST"` )
if ($#sets) then
  /bin/echo `date` "$0 $$ -- building $JSON on $#sets ($sets)" >>&! $LOGTO

  unset matrix
  set total = 0

  foreach this ( $sets )
    /bin/echo -n `date` "$0 $$ -- $this [ " >& /dev/stderr
    if (! -s "$AAHDIR/matrix/$model.$this.json") then
	jq -c '.sets[]|select(.set=="'"$this"'").results[]?' "$TEST" >! "$AAHDIR/matrix/$model.$this.json"
    endif
    # make matrix
    if ($?matrix) then
        set matrix = "$matrix"',{"set":"'$this'","truth":'
    else
	set names = ( `jq '.sets[].set' "$TEST"` )
	set tested_on = `jq -r '.date' "$TEST"`
	set names = `/bin/echo "$names" | sed 's/ /,/g'`
	set matrix = '{"name":"'"$device"'","model":"'"$model"'","date":'"$tested_on"',"size":'$#sets',"sets":['"$names"'],"matrix":[{"set":"'$this'","truth":'
	unset names
    endif
    unset truth
    foreach class ( $sets )
      /bin/echo -n "$class " >& /dev/stderr
      if (! -s "$AAHDIR/matrix/$model.$this.$class.csv") then
	@ match = 0
	set noglob
	@ count = 0
	foreach line ( `cat "$AAHDIR/matrix/$model.$this.json"` )
	  set id = `/bin/echo "$line" | jq -r '.id'`
	  if ($id != "null") then
	    set score = `/bin/echo "$line" | jq -r '.classes[]|select(.class=="'"$class"'").score'`
	    set top = `/bin/echo "$line" | jq -r '.classes|sort_by(.score)[-1].class'`
	    if ($class == $top) @ match++
	    /bin/echo "$id,$score" >>! "$AAHDIR/matrix/$model.$this.$class.csv.$$"
	    @ count++
	  endif
	end
	unset noglob
	/bin/echo "id,label,$class" >! "$AAHDIR/matrix/$model.$this.$class.csv"
	cat "$AAHDIR/matrix/$model.$this.$class.csv.$$" | sed "s/\(.*\),\(.*\)/\1,$this,\2/" >> "$AAHDIR/matrix/$model.$this.$class.csv"
	rm -f "$AAHDIR/matrix/$model.$this.$class.csv.$$"
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
      set out = ( "$AAHDIR/matrix/$model.$this".*.csv )
      set found = `/bin/echo "$found" | sed 's/ /,/g'`
      csvjoin -c "id" $out | csvcut -c "id,label,$found" >! "$AAHDIR/matrix/$model.$this.csv"
      unset found
      rm -f $out
    endif
    rm "$AAHDIR/matrix/$model.$this.json"
    /bin/echo "]" >& /dev/stderr
  end
  set matrix = "$matrix"'],"count":'$total'}'

  /bin/echo "$matrix" | jq . >! "$AAHDIR/matrix/$model.json"
  /bin/echo `date` "$0 $$ -- MADE $AAHDIR/matrix/$model.json" >& /dev/stderr

  set out = ( "$AAHDIR/matrix/$model".*.csv )
  if ($#out) then
    head -1 $out[1] >! "$AAHDIR/matrix/$model.csv"
    tail +2 -q $out >> "$AAHDIR/matrix/$model.csv"
    /bin/echo `date` "$0 $$ -- MADE $AAHDIR/matrix/$model.csv" >& /dev/stderr
  else
    /bin/echo `date` "$0 $$ -- FAILURE $AAHDIR/matrix/$model.csv" >& /dev/stderr
  endif
endif

rm -f $out

