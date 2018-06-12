#!/bin/tcsh -b
setenv APP "aah"
setenv API "label"

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

# don't update statistics more than once per (in seconds)
set TTL = 15
set SECONDS = `date "+%s"`
set DATE = `/bin/echo $SECONDS \/ $TTL \* $TTL | bc`
 
setenv DEBUG true

/bin/echo `date` "$0 $$ -- START ($QUERY_STRING) from $HTTP_REFERER" >>&! $LOGTO

if ($?QUERY_STRING) then
    set db = `/bin/echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
    set class = `/bin/echo "$QUERY_STRING" | sed 's/.*class=\([^&]*\).*/\1/'`
    if ($class == "$QUERY_STRING") unset class
    set image = `/bin/echo "$QUERY_STRING" | sed 's/.*image=\([^&]*\).*/\1/'`
    if ($image == "$QUERY_STRING") unset image
    set old = `/bin/echo "$QUERY_STRING" | sed 's/.*old=\([^&]*\).*/\1/'`
    if ($old == "$QUERY_STRING") then
      unset old
    else
      # set old = ( `/bin/echo "$old" | sed "s|%2[Ff]|/|g"` )
    endif
    set new = `/bin/echo "$QUERY_STRING" | sed 's/.*new=\([^&]*\).*/\1/'`
    if ($new == "$QUERY_STRING") then
      unset new
    else
      # set new = ( `/bin/echo "$new" | sed "s|%2[Ff]|/|g"` )
    endif
    set add = `/bin/echo "$QUERY_STRING" | sed 's/.*add=\([^&]*\).*/\1/'`
    if ($add == "$QUERY_STRING" || $add == "") then
      unset add
    else
      # set add = ( `/bin/echo "$add" | sed "s|%2[Ff]|/|g"` )
    endif
    set skip = `/bin/echo "$QUERY_STRING" | sed 's/.*skip=\([^&]*\).*/\1/'`
    if ($skip == "$QUERY_STRING") unset skip
    set limit = `/bin/echo "$QUERY_STRING" | sed 's/.*limit=\([^&]*\).*/\1/'`
    if ($limit == "$QUERY_STRING") unset limit
    set match = `/bin/echo "$QUERY_STRING" | sed 's/.*match=\([^&]*\).*/\1/'`
    if ($match == "$QUERY_STRING") unset match
    set slave = `/bin/echo "$QUERY_STRING" | sed 's/.*slave=\([^&]*\).*/\1/'`
    if ($slave == "$QUERY_STRING") unset slave
else
    /bin/echo `date` "$0 $$ -- no QUERY_STRING" >>&! $LOGTO
    goto done
endif

if ($?DEBUG) /bin/echo `date` "$0 $$ -- $QUERY_STRING" >>&! $LOGTO

#
# handle skipping an image
#
if ($?db && $?class && $?old && $?skip) then
    set image = "$skip"
    set jpg = "$AAHDIR/$db/$old/$image"
    set dest = "$AAHDIR/$API/$db/.skipped"

    mkdir -p "$dest"
    if (-s "$jpg") then
	# remove any transformed image
	if (-s "$jpg:r.jpeg") rm -f "$jpg:r.jpeg"
	# destination is "label/<device>/.skipped"
	set dest = "$dest/$jpg:t"
	mv -n "$jpg" "$dest" >>&! $LOGTO
	if (-s "$dest" && ! -e "$jpg") then
	    if ($?DEBUG) /bin/echo `date` "$0 $$ -- moved $jpg -> $dest" >>&! $LOGTO
	    ln -s "$dest" "$jpg"
	    set OUTPUT = '{"result":"success","image":"'"$jpg"'","skip":"'"$skip"'"}'
	else if (-e "$jpg") then
	    ls -al "$jpg" >>&! $LOGTO
	    rm -f "$jpg"
	    if (! -e "$jpg") then
		ln -s "$dest" "$jpg"
	    endif
	    if (-e "$jpg" && -e "$dest") then
		set OUTPUT = '{"result":"success","image":"'"$jpg"'","skip":"'"$skip"'"}'
	    else
		if ($?DEBUG) /bin/echo `date` "$0 $$ -- FAIL to move $jpg -> $dest" >>&! $LOGTO
		set OUTPUT = '{"result":"fail-move","image":"'"$jpg"'","skip":"'"$skip"'"}'
	    endif
	endif
    else
	if ($?DEBUG) /bin/echo `date` "$0 $$ -- FAIL to move $jpg -> $dest" >>&! $LOGTO
	set OUTPUT = '{"result":"fail no image","image":"'"$jpg"'","skip":"'"$skip"'"}'
    endif
    # all done
    goto output
endif

#
# handle labeling an image
#
if ($?db && $?class && $?image && $?old && ($?new || $?add)) then
    if ($?add) then
	set new = "$add"
    endif

    set jpg = "$AAHDIR/$db/$old/$image"
    set link = "$AAHDIR/$API/$db/$new/$image"

    if (! -d "$AAHDIR/$API/$db/$new") then
        if ($?DEBUG) /bin/echo `date` "$0 $$ -- making directory $AAHDIR/$API/$db/$new" >>&! $LOGTO
	mkdir -p "$AAHDIR/$API/$db/$new"
    endif

    if (-s "$jpg") then
	if ($?DEBUG) /bin/echo `date` "$0 $$ -- old image exists ($jpg)" `ls -l "$jpg"` >>&! $LOGTO
	if (-e "$link") then
	    if ($?DEBUG) /bin/echo `date` "$0 $$ -- labeled image exists ($link)" `ls -l "$link"` >>&! $LOGTO
	    set OUTPUT = '{"result":"fail-exists","image":"'"$old/$image"'","link":"'"$new/$image"'"}'
	else 
	    if ($?DEBUG) /bin/echo `date` "$0 $$ -- moving and linking $jpg -> $link" >>&! $LOGTO
	    mv -n "$jpg" "$link" >>&! $LOGTO
	    mv -n "$jpg:r.jpeg" "$link:r.jpeg" >>&! $LOGTO
	    if (-s "$link") then
		if ($?DEBUG) /bin/echo `date` "$0 $$ -- move succeeded" `ls -l "$link"` >>&! $LOGTO
		ln -s "$link" "$jpg" >>&! $LOGTO
		ln -s "$link:r.jpeg" "$jpg:r.jpeg"
	    endif
	    if (-e "$jpg") then
		if ($?DEBUG) /bin/echo `date` "$0 $$ -- link succeeded" `ls -al "$jpg"` >>&! $LOGTO
		set OUTPUT = '{"result":"success","image":"'"$old/$image"'","link":"'"$new/$image"'"}'
	    else
		if ($?DEBUG) /bin/echo `date` "$0 $$ -- link failed ($link)" >>&! $LOGTO
		set OUTPUT = '{"result":"fail-link","image":"'"$old/$image"'","link":"'"$new/$image"'"}'
	    endif
	endif
    else
	if ($?DEBUG) /bin/echo `date` "$0 $$ -- DNE or zero ($jpg)" >>&! $LOGTO
	set OUTPUT = '{"result":"fail-invalid","image":"'"$old/$image"'","link":"'"$new/$image"'"}'
    endif
else
    if ($?DEBUG) /bin/echo `date` "$0 $$ -- insufficient arguments" >>&! $LOGTO
    set OUTPUT = '{"result":"badargs"}'
endif

output:

#
# prepare for output
#
/bin/echo "Content-Type: application/json; charset=utf-8"
/bin/echo "Cache-Control: no-cache"
/bin/echo "Last-Modified:" `$dateconv -i '%s' -f '%a, %d %b %Y %H:%M:%S %Z' $DATE`

# test parameters
if ($?HTTP_REFERER && $?db) then
    # get base
    set baseurl = `/bin/echo "$HTTP_REFERER" | sed 's/\([^?]*\).*/\1/'`
    if ($?class) then
      set referer = "$baseurl?db=$db&class=$class"
    endif
    if ($?match) then
	set referer = "$referer&match=$match"
    endif
    if ($?limit) then
	set referer = "$referer&limit=$limit"
    endif
    if ($?slave) then
	set slave = "$referer&slave=$slave"
    if ($?add) then
	set referer = "$referer&add=$add"
    endif
    set referer = "$referer&assign=$old/$image"
    /bin/echo "Location: $referer"
    unset noglob
else
    if ($?DEBUG) /bin/echo `date` "$0 $$ -- no HTTP_REFERER" >>&! $LOGTO
endif

/bin/echo ""
/bin/echo "$OUTPUT"


done:

/bin/echo `date` "$0 $$ -- FINISH" >>&! $LOGTO
