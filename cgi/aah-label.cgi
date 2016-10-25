#!/bin/csh -fb
set DEBUG = 1
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
    set limit = `echo "$QUERY_STRING" | sed 's/.*limit=\([^&]*\).*/\1/'`
    if ($limit == "$QUERY_STRING") unset limit
    set match = `echo "$QUERY_STRING" | sed 's/.*match=\([^&]*\).*/\1/'`
    if ($match == "$QUERY_STRING") unset match
endif

if ($?DEBUG) echo `date` "$0 $$ -- $?DB $?id $?image $?old $?new" >>! $TMP/LOG

if ($?DB && $?id && $?image && $?old && $?new) then
    set jpg = "$TMP/$DB/$old/$image"
    set link = "$TMP/$API/$DB/$new/$image"
    if (! -d "$TMP/$API/$new") then
        if ($?DEBUG) echo `date` "$0 $$ -- making directory $TMP/$API/$DB/$new" >>! $TMP/LOG
	mkdir -p "$TMP/$API/$DB/$new"
    endif

    if (-s "$jpg") then
	if (-e "$link") then
	    if ($?DEBUG) echo `date` "$0 $$ -- labeled image exists ($link)" `ls -al "$link"` >>! $TMP/LOG
	    set OUTPUT = '{"result":"fail-exists","image":"'"$old/$image"'","link":"'"$new/$image"'"}'
	else
	    if ($?DEBUG) echo `date` "$0 $$ -- moving and linking $jpg -> $link" >>! $TMP/LOG
	    mv $jpg $link
	    ln -s $link $jpg
	    if (-e "$jpg") then
		if ($?DEBUG) echo `date` "$0 $$ -- link succeeded ($link)" `ls -al "$link"` >>! $TMP/LOG
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
    if ($?DEBUG) echo `date` "$0 $$ -- baseurl ($baseurl)" >>! $TMP/LOG
    set referer = "$baseurl?db=$DB&id=$id"
    if ($?DEBUG) echo `date` "$0 $$ -- referer ($referer)" >>! $TMP/LOG
    if ($?match) then
	set referer = "$referer&match=$match"
    endif
    if ($?DEBUG) echo `date` "$0 $$ -- referer ($referer)" >>! $TMP/LOG
    if ($?limit) then
	set referer = "$referer&limit=$limit"
    endif
    if ($?DEBUG) echo `date` "$0 $$ -- referer ($referer)" >>! $TMP/LOG
    set referer = "$referer&assign=$old/$image"
    if ($?DEBUG) echo `date` "$0 $$ -- referer ($referer)" >>! $TMP/LOG
    echo "Location: $referer"
    unset noglob
endif

echo ""
echo "$OUTPUT"


done:

echo `date` "$0 $$ -- FINISH" >>! $TMP/LOG
