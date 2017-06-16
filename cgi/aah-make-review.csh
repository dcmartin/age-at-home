#!/bin/csh -fb
setenv APP "aah"
setenv API "review"
setenv LAN "192.168.1"
setenv WWW "www.dcmartin.com"
setenv TMP "/var/lib/age-at-home"

if ($?TTL == 0) set TTL = 2700
if ($?SECONDS == 0) set SECONDS = `/bin/date "+%s"`
if ($?DATE == 0) set DATE = `/bin/echo $SECONDS \/ $TTL \* $TTL | /usr/bin/bc`

setenv DEBUG true
setenv NOFORCE true

if ($?QUERY_STRING) then
    set db = `/bin/echo "$QUERY_STRING" | sed 's/.*db=\([^&]*\).*/\1/'`
    if ($db == "$QUERY_STRING") unset db
    set class = `/bin/echo "$QUERY_STRING" | sed 's/.*class=\([^&]*\).*/\1/'`
    if ($class == "$QUERY_STRING") unset class
endif

# DEFAULTS to rough-fog (kitchen) and all classes
if ($?db == 0) set db = rough-fog
if ($?class == 0) set class = all

# standardize QUERY_STRING # maybe by "&class=$class"
setenv QUERY_STRING "db=$db&class=$class"

/bin/echo `/bin/date` "$0 $$ -- START ($QUERY_STRING)"  >>&! $TMP/LOG

#
# OUTPUT target
#
set OUTPUT = "$TMP/$APP-$API-$QUERY_STRING.$DATE.json"
#
# check output
#

if (-s "$OUTPUT") then
  goto done
endif

#
# SINGLE THREADED (by QUERY_STRING)
#
set INPROGRESS = ( `/bin/echo "$OUTPUT:r:r".*.json.*` )
if ($#INPROGRESS) then
  foreach ip ( $INPROGRESS )
    set pid = $ip:e
    set eid = `ps axw | awk '{ print $1 }' | egrep "$pid"`
    if ($pid == $eid) then
      if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- in-progress $INPROGRESS:e ($pid)" >>&! $TMP/LOG
      goto done
    endif
    rm -f $ip
  end
endif

# cleanup if interrupted
onintr cleanup
touch "$OUTPUT".$$

#
# GET CLOUDANT CREDENTIALS
#
if (-e ~$USER/.cloudant_url) then
  set cc = ( `cat ~$USER/.cloudant_url` )
  if ($#cc > 0) set CU = $cc[1]
  if ($#cc > 1) set CN = $cc[2]
  if ($#cc > 2) set CP = $cc[3]
  if ($?CN && $?CP) then
    set CU = "$CN":"$CP"@"$CU"
  else
else
  if($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- NO ~$USER/.cloudant_url" >>&! $TMP/LOG
  goto done
endif

#
# determine where we are by sequence #
#
set url = "$db-$API/all"
set out = "$OUTPUT:r"-all.json
set seqid = 0
/usr/bin/curl -q -s -f -L "$CU/$url" -o "$out"
if ($status != 22 && -s "$out") then
  set seqiq = ( `/usr/local/bin/jq -r '.seqid' "$out"` )
  if ($#seqid) then
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- seqid ($seqid)" >>! $TMP/LOG
    if ($seqid == "null") then
       set seqid = 0
    endif
  else
    set seqid = 0
  endif
endif
rm -f "$out"

#
# get CHANGES records
#
set CHANGES = "$TMP/$APP-$API-$db-changes.$DATE.json"
if (! -s "$CHANGES") then
    rm -f "$CHANGES:r:r".*
    set url = "$db/_changes?descending=true&include_docs=true&since=$seqid"
    set out = "$CHANGES".$$
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- get ($url)" >>! $TMP/LOG
    /usr/bin/curl -s -q -f -L "$CU/$url" -o "$out" >>&! $TMP/LOG
    if ($status != 22 && -s "$out") then
      if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- got ($CHANGES)" >>! $TMP/LOG
      mv -f "$out" "$CHANGES"
    else
      if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- no CHANGES ($url)" >>! $TMP/LOG
      rm -f "$out"
    endif
else
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- cache current ($TTL) update in " `echo "$SECONDS - $DATE" | /usr/bin/bc` >>! $TMP/LOG
endif

# get last_seq
if (-s "$CHANGES") then
  set last_seq = ( `/usr/local/bin/jq -r '.last_seq' "$CHANGES"` )
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- last sequence ($last_seq)" >>! $TMP/LOG
else
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- no changes ($CHANGES)" >>! $TMP/LOG
endif

#
# CHECK FOR NEW EVENTS BASED ON SEQUENCE ID
#

if ($?last_seq) then
    if ($#last_seq && $#seqid && $seqid != 0 && $last_seq != 0) then
	if ("$last_seq" == "$seqid") then
	    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ ** NO NEW EVENTS ($seqid)" >>! $TMP/LOG
	endif
    else
      if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- last_seq ($last_seq) seqid ($seqid)" >>! $TMP/LOG
    endif
    set seqid = "$last_seq"
else
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- no last sequence" >>! $TMP/LOG
endif

#
# calculate new results based on changes
#

set RESULTS = "$TMP/$APP-$API-$db-results.$DATE.json"
if (-s "$CHANGES" && (! -s "$RESULTS" || ((-M "$CHANGES") > (-M "$RESULTS")))) then
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- updating $RESULTS from $CHANGES" >>! $TMP/LOG
    # remove old results
    rm -f "$RESULTS:r:r".*.json
    # process changes into results
    /usr/local/bin/jq -c '[.results[].doc|{file:.visual.image,tag:.alchemy.text,score:.alchemy.score,year:.year,month:.month,day:.day,hour:.hour,minute:.minute,second:.second,crop:.imagebox}]' "$CHANGES" \
	| /usr/local/bin/jq -c '{results:.[]|[.file,.tag,.score,.year,.month,.day,.hour,.minute,.second,.crop]}' \
	| sed 's/"//g' \
	| sed 's/{results:\[//' \
	| sed 's/\]}//' \
	| /usr/local/bin/gawk -F, \
	  '{ m=($7*60+$8)/15; \
	     t=mktime(sprintf("%4d %2d %2d %2d %2d %2d",$4,$5,$6,$7,$8,$9)); \
	     printf("{\"file\":\"%s\",\"tag\":\"%s\",\"score\":%f,\"crop\":\"%s\",\"ampm\":\"%s\",\"day\":\"%s\",\"interval\":%d}\n",$1,$2,$3,$10,strftime("%p",t),strftime("%A",t),m); \
	   }' \
	| sort -r >! "$RESULTS"
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- completed new RESULTS ($RESULTS)" >>! $TMP/LOG
else
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- RESULTS are current with CHANGES ($DATE)" >>! $TMP/LOG
  goto done
endif

#
# download images from RESULTS of CHANGES 
#
# { "file": "20160801182222-610-00.jpg", "tag": "NO_TAGS", "score": 0, "crop": "WxH+X+Y", "ampm": "PM", "day": "Monday", "interval": 73 }
#

#
# CAMERA & TRANSFORMATION INFORMATION (should be a configuration read from db corresponding to device and model)
#
if ($?CAMERA_IMAGE_WIDTH == 0) setenv CAMERA_IMAGE_WIDTH 640
if ($?CAMERA_IMAGE_HEIGHT == 0) setenv CAMERA_IMAGE_HEIGHT 480
if ($?MODEL_IMAGE_WIDTH == 0) setenv MODEL_IMAGE_WIDTH 224
if ($?MODEL_IMAGE_HEIGHT == 0) setenv MODEL_IMAGE_HEIGHT 224
if ($?CAMERA_MODEL_TRANSFORM == 0) setenv CAMERA_MODEL_TRANSFORM "CROP"

if ($?FTP_GET == 0) then
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- getting new images" >>! $TMP/LOG
    #
    # get LANIP from aah-devices.cgi service that returns JSON for device
    #
    set lanip = `/usr/bin/curl -s -q -L "http://$WWW/CGI/aah-devices.cgi" | /usr/local/bin/jq -r '.|select(.name=="'"$db"'")|.ip_address'`
    if ($#lanip && $lanip != "") then
	if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- found LANIP ($lanip)" >>! $TMP/LOG
	setenv LANIP "$lanip"
    else
	if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- no LANIP" >>! $TMP/LOG
	goto done
    endif
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- PROCESSING $RESULTS (" `wc -l "$RESULTS" | awk '{ print $1 }'` ") lines" >>! $TMP/LOG
    # create temporary output for processing sequentially; ignore "ampm"
    foreach line ( `/usr/local/bin/jq -c '[.file,.tag,.score,.day,.interval,.crop]' "$RESULTS" | sed 's/\[//' | sed 's/\]//' | sed 's/ /_/g' | awk -F, '{ printf("%s,%s,%f,%s,%d,%s\n", $1,$2,$3,$4,$5,$6) }'` )
	set tuple = ( `/bin/echo "$line" | /usr/bin/sed 's/,/ /g'` )
	if ($#tuple < 2) then
	    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- bad tuple ($tuple) ($line)" >>! $TMP/LOG
	    continue
	endif

	set tag = `echo $tuple[2] | sed 's/"//g'`
	if ($tag != "null") then
	    # get filename
	    set file = `echo $tuple[1] | sed 's/"//g'`
	    # build image fullpath
	    set image = "$TMP/$db/$tag/$file"
	    # ensure directory exists
	    mkdir -p "$image:h"
	    # test if image already exists
	    if (! -s "$image") then
		set ftp = "ftp://ftp:ftp@$LANIP/$file" 
		/usr/bin/curl -s -q -L "$ftp" -o "/tmp/$$.jpg"
		if ($status != 0 || (! -s "/tmp/$$.jpg")) then
		    rm -f /tmp/$$.jpg
		    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- fail ($ftp)" >>! $TMP/LOG
		    break
		else
		    mv -f /tmp/$$.jpg "$image"
		endif
		if (-s "$image") then
		    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- success ($image)" >>! $TMP/LOG
		    set crop = `echo $tuple[6] | sed 's/"//g'`
		    if ($#crop && $?CAMERA_MODEL_TRANSFORM) then
		      set c = `/bin/echo "$crop" | /usr/bin/sed "s/\([0-9]*\)x\([0-9]*\)\([+-]*[0-9]*\)\([+-]*[0-9]*\)/\1 \2 \3 \4/"`
		      set w = $c[1]
		      set h = $c[2]
		      set x = `/bin/echo "0 $c[3]" | /usr/bin/bc`
		      set y = `/bin/echo "0 $c[4]" | /usr/bin/bc`

		      switch ($CAMERA_MODEL_TRANSFORM)
			case "RESIZE":
			  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- resizing $image ($MODEL_IMAGE_WIDTH,$MODEL_IMAGE_HEIGHT)" 
			  /usr/local/bin/convert \
			      -resize "$MODEL_IMAGE_WIDTH"x"$MODEL_IMAGE_HEIGHT" "$image" \
			      -gravity center \
			      -background gray \
			      "$image:r.jpeg"
			  breaksw
			case "CROP":
			  # calculate centroid-based extant ($MODEL_IMAGE_WIDTHx$MODEL_IMAGE_WIDTH image)
			  @ cx = $x + ( $w / 2 ) - ( $MODEL_IMAGE_WIDTH / 2 )
			  @ cy = $y + ( $h / 2 ) - ( $MODEL_IMAGE_HEIGHT / 2 )
			  if ($cx < 0) @ cx = 0
			  if ($cy < 0) @ cy = 0
			  if ($cx + $MODEL_IMAGE_WIDTH > $CAMERA_IMAGE_WIDTH) @ cx = $CAMERA_IMAGE_WIDTH - $MODEL_IMAGE_WIDTH
			  if ($cy + $MODEL_IMAGE_HEIGHT > $CAMERA_IMAGE_HEIGHT) @ cy = $CAMERA_IMAGE_HEIGHT - $MODEL_IMAGE_HEIGHT
			  set crop = "$MODEL_IMAGE_WIDTH"x"$MODEL_IMAGE_HEIGHT"+"$cx"+"$cy"

			  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- cropping $image $crop" 
			  /usr/local/bin/convert \
			      -crop "$crop" "$image" \
			      -gravity center \
			      -background gray \
			      "$image:r.jpeg"
			  breaksw
			default:
			  /bin/echo `/bin/date` "$0 $$ -- unknown transformation ($CAMERA_MODEL_TRANSFORM)" 
			  breaksw
		      endsw
		    else	
		      if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- no transformation defined (CAMERA_MODEL_TRANSFORM)" 
		    endif
		    # optionally delete the source
		    if ($?FTP_DELETE) then
			if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- deleting ($file)" >>! $TMP/LOG
			/usr/bin/curl -s -q -L "ftp://$LANIP/" -Q "-DELE $file"
		    endif
	        else
		    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- did not retrieve ($image)" >>! $TMP/LOG
	        endif
	    else
		if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- done; found existing image ($image)" >>! $TMP/LOG
	        break
	    endif
	endif
    end
else
    if ($?DEBUG) /bin/echo `/bin/date` $0 $$ -- skipping FTP retrieval; FTP_GET environment variable defined ($FTP_GET)" >>! $TMP/LOG
endif

#
# MAKE NEW STATISTICS
#

# only works for limited # and format of class names (no space)
set classes = ( `/bin/ls -1 "$TMP/$db"` )

if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- found $#classes classes" >>! $TMP/LOG

set NEW = "$OUTPUT".$$
echo -n '{ "seqid":"'$seqid'","date":"'$DATE'","device":"'"$db"'","count":'$#classes',"classes":[' >! "$NEW"

if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- iterating over $classes" >>! $TMP/LOG

@ k = 0
# this should really be fed by a find(1) command
foreach i ( $classes )
    if ($k > 0) /bin/echo "," >> "$NEW"
    /bin/echo '{"name":"'"$i"'",' >> "$NEW"
    if ($?LIST_IMAGES) then
      /bin/echo '"images":[' >> "$NEW"
      /usr/bin/find "$TMP/$db/$i" -name "*.jpg" -type f -print -maxdepth 1 \
	| /usr/bin/sed "s@$TMP/$db/$i/\(.*\).jpg@\1@" \
	| /usr/bin/awk 'BEGIN { n = 0; } { if (n) printf(","); n++; printf("\"%s\"",$1) } END { printf("],\"count\":%d}\n",n); }' \
	>> "$NEW"
    else
      /bin/echo '"count":' `ls -1 "$TMP/$db/$i"/*.jpg | wc -l | awk '{ print $1 }'` '}' >> "$NEW"
    endif
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- $i" >>! $TMP/LOG
    @ k++
end
echo -n ']}' >> "$NEW"

/usr/local/bin/jq -c '.' "$NEW" >& /dev/null
if ($status != 0) then
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- malformed JSON:" >>! "$TMP/LOG"
    goto done
else
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- good JSON ($NEW)" >>! $TMP/LOG
endif

# update statistics
mv -f "$NEW" "$OUTPUT"

echo `/bin/date` "$0 $$ -- CREATED $OUTPUT"  >>! $TMP/LOG

#
# update Cloudant
#
if ($?CLOUDANT_OFF == 0 && $?CU && $?db) then
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- test if db exists ($CU/$db-$API)" >>! $TMP/LOG
    set DEVICE_db = `/usr/bin/curl -s -q -L -X GET "$CU/$db-$API" | /usr/local/bin/jq '.db_name'`
    if ( $DEVICE_db == "" || "$DEVICE_db" == "null" ) then
	if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- creating db $CU/$db-$API" >>! $TMP/LOG
        # create db
        set DEVICE_db = `/usr/bin/curl -s -q -L -X PUT "$CU/$db-$API" | /usr/local/bin/jq '.ok'`
        # test for success
        if ( "$DEVICE_db" != "true" ) then
            # failure
	    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- failure creating Cloudant database ($db-$API)" >>! $TMP/LOG
            setenv CLOUDANT_OFF TRUE
	else
	    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- success creating db $CU/$db-$API" >>! $TMP/LOG
        endif
    endif
    if ( $?CLOUDANT_OFF == 0 ) then
	set OLD = "$OUTPUT.$$"
	curl -s -q -L -o "$OLD" "$CU/$db-$API/all" >>&! $TMP/LOG
	if (-s "$OLD") then
	    set doc = ( `cat "$OLD" | /usr/local/bin/jq ._id,._rev | sed 's/"//g'` )
	    if ($#doc == 2 && $doc[1] == "all" && $doc[2] != "") then
		set rev = $doc[2]
		if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- deleting old output ($rev)" >>! $TMP/LOG
		/usr/bin/curl -s -q -L -X DELETE "$CU/$db-$API/all?rev=$rev" >>&! $TMP/LOG
	    endif
	else
            if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- no old output to delete" >>! $TMP/LOG
        endif
        if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- storing new output" >>! $TMP/LOG
        /usr/bin/curl -s -q -L -H "Content-type: application/json" -X PUT "$CU/$db-$API/all" -d "@$OUTPUT" >>&! $TMP/LOG
	if ($status == 0) then
	    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- success storing new output" >>! $TMP/LOG
	else
	    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- failure storing new output" >>! $TMP/LOG
	endif
    else
	if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- Cloudant OFF ($db-$API)" >>! $TMP/LOG
    endif
else
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- no Cloudant update" >>! $TMP/LOG
endif

done:
  echo `/bin/date` "$0 $$ -- FINISH ($QUERY_STRING)"  >>! $TMP/LOG

cleanup:
  rm -f "$OUTPUT".$$

