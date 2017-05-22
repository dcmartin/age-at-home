#!/bin/csh -fb
setenv DEBUG true
setenv APP "aah"
setenv API "label"
setenv WWW "www.dcmartin.com"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

# don't update statistics more than once per (in seconds)
set TTL = 15
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo `date` "$0 $$ -- START ($QUERY_STRING) from $HTTP_REFERER" >>! $TMP/LOG

if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($DB == "$QUERY_STRING") unset DB
    set id = `echo "$QUERY_STRING" | sed 's/.*id=\([^&]*\).*/\1/'`
    if ($id == "$QUERY_STRING") unset id
    set image = `echo "$QUERY_STRING" | sed 's/.*image=\([^&]*\).*/\1/'`
    if ($image == "$QUERY_STRING") unset image
    set old = `echo "$QUERY_STRING" | sed 's/.*old=\([^&]*\).*/\1/'`
    if ($old == "$QUERY_STRING") unset old
    set new = `echo "$QUERY_STRING" | sed 's/.*new=\([^&]*\).*/\1/'`
    if ($new == "$QUERY_STRING") unset new
    set add = `echo "$QUERY_STRING" | sed 's/.*add=\([^&]*\).*/\1/'`
    if ($add == "$QUERY_STRING" || $add == "") unset add
    set skip = `echo "$QUERY_STRING" | sed 's/.*skip=\([^&]*\).*/\1/'`
    if ($skip == "$QUERY_STRING") unset skip
    set limit = `echo "$QUERY_STRING" | sed 's/.*limit=\([^&]*\).*/\1/'`
    if ($limit == "$QUERY_STRING") unset limit
    set match = `echo "$QUERY_STRING" | sed 's/.*match=\([^&]*\).*/\1/'`
    if ($match == "$QUERY_STRING") unset match
endif

if ($?DEBUG) echo `date` "$0 $$ -- $?DB $?id $?image $?old $?new $?add $?skip" >>! $TMP/LOG

#
# handle skipping an image
#
if ($?DB && $?id && $?old && $?skip) then
    set image = "$skip"
    set jpg = "$TMP/$DB/$old/$image"
    set dest = "$TMP/$API/$DB/.skipped"

    mkdir -p "$dest"
    if (-s "$jpg") then
	# remove any transformed image
	if (-s "$jpg:r.jpeg") rm -f "$jpg:r.jpeg"
	# destination is "label/<device>/.skipped"
	set dest = "$dest/$jpg:t"
	mv -n "$jpg" "$dest" >>& $TMP/LOG
	if (-s "$dest" && ! -e "$jpg") then
	    if ($?DEBUG) echo `date` "$0 $$ -- moved $jpg -> $dest" >>! $TMP/LOG
	    ln -s "$dest" "$jpg"
	    set OUTPUT = '{"result":"success","image":"'"$jpg"'","skip":"'"$skip"'"}'
	else if (-e "$jpg") then
	    ls -al "$jpg" >>! $TMP/LOG
	    rm -f "$jpg"
	    if (! -e "$jpg") then
		ln -s "$dest" "$jpg"
	    endif
	    if (-e "$jpg" && -e "$dest") then
		set OUTPUT = '{"result":"success","image":"'"$jpg"'","skip":"'"$skip"'"}'
	    else
		if ($?DEBUG) echo `date` "$0 $$ -- FAIL to move $jpg -> $dest" >>! $TMP/LOG
		set OUTPUT = '{"result":"fail-move","image":"'"$jpg"'","skip":"'"$skip"'"}'
	    endif
	endif
    endif
    # all done
    goto output

#
# handle labeling an image
#
if ($?DB && $?id && $?image && $?old && ($?new || $?add)) then
    if ($?add) then
	set new = "$add"
    endif

    set jpg = "$TMP/$DB/$old/$image"
    set link = "$TMP/$API/$DB/$new/$image"

    if (! -d "$TMP/$API/$DB/$new") then
        if ($?DEBUG) echo `date` "$0 $$ -- making directory $TMP/$API/$DB/$new" >>! $TMP/LOG
	mkdir -p "$TMP/$API/$DB/$new"
    endif

    if (-s "$jpg") then
	if ($?DEBUG) echo `date` "$0 $$ -- old image exists ($jpg)" `ls -l "$jpg"` >>! $TMP/LOG
	if (-e "$link") then
	    if ($?DEBUG) echo `date` "$0 $$ -- labeled image exists ($link)" `ls -l "$link"` >>! $TMP/LOG
	    set OUTPUT = '{"result":"fail-exists","image":"'"$old/$image"'","link":"'"$new/$image"'"}'
	else 
	    if ($?DEBUG) echo `date` "$0 $$ -- moving and linking $jpg -> $link" >>! $TMP/LOG
	    mv -n "$jpg" "$link" >>& $TMP/LOG
	    mv -n "$jpg:r.jpeg" "$link:r.jpeg" >>& $TMP/LOG
	    if (-s "$link") then
		if ($?DEBUG) echo `date` "$0 $$ -- move succeeded" `ls -l "$link"` >>! $TMP/LOG
		ln -s "$link" "$jpg" >>& $TMP/LOG
		ln -s "$link:r.jpeg" "$jpg:r.jpeg"
	    endif
	    if (-e "$jpg") then
		if ($?DEBUG) echo `date` "$0 $$ -- link succeeded" `ls -al "$jpg"` >>! $TMP/LOG
		set OUTPUT = '{"result":"success","image":"'"$old/$image"'","link":"'"$new/$image"'"}'
	    else
		if ($?DEBUG) echo `date` "$0 $$ -- link failed ($link)" >>! $TMP/LOG
		set OUTPUT = '{"result":"fail-link","image":"'"$old/$image"'","link":"'"$new/$image"'"}'
	    endif
	endif
    else
	if ($?DEBUG) echo `date` "$0 $$ -- DNE or zero ($jpg)" >>! $TMP/LOG
	set OUTPUT = '{"result":"fail-invalid","image":"'"$old/$image"'","link":"'"$new/$image"'"}'
    endif
else
    if ($?DEBUG) echo `date` "$0 $$ -- insufficient arguments" >>! $TMP/LOG
    set OUTPUT = '{"result":"badargs"}'
endif

output:

#
# prepare for output
#
echo "Content-Type: application/json; charset=utf-8"
echo "Cache-Control: no-cache"
echo "Last-Modified:" `date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`

# test parameters
if ($?HTTP_REFERER && $?DB && $?id) then
    # get base
    set baseurl = `echo "$HTTP_REFERER" | sed 's/\([^?]*\).*/\1/'`
    set referer = "$baseurl?db=$DB&id=$id"
    if ($?match) then
	set referer = "$referer&match=$match"
    endif
    if ($?limit) then
	set referer = "$referer&limit=$limit"
    endif
    if ($?add) then
	set referer = "$referer&add=$add"
    endif
    set referer = "$referer&assign=$old/$image"
    echo "Location: $referer"
    unset noglob
endif

echo ""
echo "$OUTPUT"


done:

echo `date` "$0 $$ -- FINISH" >>! $TMP/LOG
