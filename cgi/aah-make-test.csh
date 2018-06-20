#!/bin/tcsh

set DEBUG = true

@ i = 1
while ($i <= $#argv)
    set t = "$argv[$i]"
    if (($#t == 1) && ($#argv >= $i)) then
        if ("$t" == "-n") then
            @ i++
            set maxfiles = $argv[$i]
        else if ("$t" == "-m") then
            @ i++
            # model by <classifier_id>
            set model = $argv[$i]
        else if ($#argv >= $i) then
           # name of directory in AAHDIR
	   set jpegfiles = ( $argv[$i-] ) 
	   break
        endif
    endif
    @ i++
end

if ($?jpegfiles == 0) then
    if ($?DEBUG) echo `date` "$0:t $$ -- USAGE: $0:t [-m <model>] JPEG(s)" >& /dev/stderr
    goto done
else
endif

set creds = ~$USER/.watson.visual-recognition.json
if (-e $creds) then
    set api_key = ( `jq '.[0]|.credentials.api_key' $creds | sed 's/"//g'` )
    if ($?DEBUG) echo `date` "$0:t $$ -- USING APIKEY $api_key" >& /dev/stderr
    set url = ( `jq '.[0]|.credentials.url' $creds | sed 's/"//g'` )
    if ($?DEBUG) echo `date` "$0:t $$ -- USING URL $url" >& /dev/stderr
    # set base
    set TU = $url
else if ($?TU == 0) then
    echo `date` "$0:t $$ -- NO CREDENTIALS ($creds); create file and copy credentials from visual-recognition service on bluemix.net" >& /dev/stderr
    goto done
endif

if ($?verid == 0) set verid = "v3"
if ($?vdate == 0) set vdate = "2016-05-20"

if ($?model) then
    set classifiers = ( `curl -q -s -L "$TU/$verid/classifiers?api_key=$api_key&version=$vdate" | jq '.classifiers[]|select(.classifier_id=="'"$model"'")'` )
else 
    if ($model != "default") then
      set classifiers = ( `curl -q -s -L "$TU/$verid/classifiers?api_key=$api_key&version=$vdate" | jq '.classifiers[]'` )
    else
      set classifiers = ()
    endif
endif

if ($#classifiers > 0) then
    set classifier = `echo "$classifiers" | jq '.classifier_id' | sed 's/"//g'`
    if ($#classifier > 0) then
	if ($?DEBUG) echo `date` "$0:t $$ -- Using classifiers ($classifier) +++" >& /dev/stderr
    else
	unset classifier
    endif
else
    if ($?DEBUG) echo `date` "$0:t $$ -- no custom classifier (using default) +++" >& /dev/stderr
endif

if ($?classifier) then
    # prepare for URL
    set classifier = `echo "$classifier" | sed "s/ /,/g"`
endif

# The max number of images in a .zip file is limited to 20, and limited to 5 MB.
@ maxfiles = ( `ls -l $jpegfiles | awk '{ n += 1; sum += $5 } END { max = (5000*1024) / (sum / n); if (max > 20) max = 20; printf("%d\n", max) }'` )

@ total = 0 
@ count = 0
@ i = 1
@ z = $maxfiles
@ t = 0
@ n = $#jpegfiles
set zip = /tmp/$0:t.$$.zip
set json = /tmp/$0:t.$$.json

while ($i <= $n) 
    @ t = $t + $z

again:
    set partial = /tmp/$0:t.$$.$i.$t.json
    
    # no idea why I did this
    if (-e "$partial") then
	if ($?DEBUG) echo `date` "$0:t $$ -- PARTIAL EXISTS ($partial)" >& /dev/stderr
	continue
    endif

    if ($t >= $n) @ t = $n
    set ifiles = ( $jpegfiles[$i-$t] )
    set nfiles = $#ifiles
    if ($nfiles > 1) then
	zip -q -j -r -u $zip $ifiles >& /dev/stderr
	if (-s $zip) then
	    if ($?DEBUG) echo `date` "$0:t $$ -- " `ls -al $zip` >& /dev/stderr
	    set ifiles = $zip
	else
	    exit
	endif
    endif

    if ($?DEBUG) echo -n `date` "$0:t $$ -- classify ($i - $t) $nfiles images " >& /dev/stderr
    set start = `date +%s`
    if ($?classifier) then
    	if ($?USE_DEFAULT) then
	    if ($?DEBUG) echo `date` "$0:t $$ -- CLASSIFY $ifiles using (default,$classifier)" >& /dev/stderr
	    curl -f -s -q -L -F "images_file=@$ifiles" -o $partial \
		"$TU/$verid/classify?api_key=$api_key&classifier_ids=default,$classifier&threshold=0.000001&version=$vdate" >& /dev/stderr
	else
	    if ($?DEBUG) echo `date` "$0:t $$ -- CLASSIFY $ifiles using ($classifier)" >& /dev/stderr
	    curl -f -s -q -L -F "images_file=@$ifiles" -o $partial \
		"$TU/$verid/classify?api_key=$api_key&classifier_ids=$classifier&threshold=0.000001&version=$vdate" >& /dev/stderr
	endif
    else
	if ($?DEBUG) echo `date` "$0:t $$ -- CLASSIFY $ifiles using default" >& /dev/stderr
	curl -f -s -q -L -F "images_file=@$ifiles" -o $partial \
	    "$TU/$verid/classify?api_key=$api_key&classifier_ids=default&threshold=0.000001&version=$vdate" >& /dev/stderr
    endif
    # curl failure; assume file size too large
    if ($status == 22 || ! -s $partial) then
        # call failed -- retry
	if ($?DEBUG) echo "FAILED ($t $z) ($ifiles)" >& /dev/stderr
	# try smaller set size
	@ t--
	@ z--
	# remove old
	rm -f $zip $partial
	if ($t <= $n) goto again
	break
    endif
    set error = `jq '.status' "$partial"`
    if ($status == 0 && $error == "ERROR") then
	if ($?DEBUG) echo `date` "$0:t $$ -- $error - " `jq '.' $partial` >& /dev/stderr
        rm -f $zip $partial
	goto done
    endif
    # SUCCESS !
    set end = `date +%s`
    @ elapsed = $end - $start
    if ($?DEBUG) echo `/bin/date` "$0:t $$ - SUCCESS ($elapsed seconds)" >& /dev/stderr
    if (-s "$json") then
	echo ',' >> "$json"
    else
	# start output
        echo '{"results":[' >! "$json"
    endif
    # Sometimes you get elements of the results like the following:
    # { "error": { "description": "An undefined server error occurred.", "error_id": "server_error" }, "id": "20161126155646-11447-01" },
    # We re-write the results to indicate a failure with null for results
    if (-s $zip) then
	# we sent a ZIP file; remove it and elide the ZIP file pre-pended to image name
        jq '.' "$partial" | sed 's/"image": ".*\/\(.*\)\.jpg"/"id": "\1"/' >> "$json"
	rm -f $zip
    else
	# simply append partial to complete
	jq '.' "$partial" >> "$json"
    endif

    # debug top result
    if ($?DEBUG) jq -c '.images[]|{"image":.image,"classes":[.classifiers[]?.classes[]]|sort_by(.score)[-1]}' $partial >& /dev/stderr

    # remove partial
    rm -f $partial
    # total time
    @ total += $elapsed
    @ count += $nfiles

    # increment to next set of images
    @ i = $t + 1
end
# add statistics (count, time, model id)
if (-s "$json") echo '],"count":'$count',"time":'$total',"model":"'"$model"'"}' >> "$json"

output:

# top class (by score) per image for each classifier applied
# jq -c '.images[]|{"image":.image,"classes":[.classifiers[]|{"name":.name,"id":.classifier_id,"classes":.classes|sort_by(.score)[-1]}]}'

# all classes per image for all classifiers applied
# jq -c '.images[]|{"image":.image,"classes":[.classifiers[].classes[]]}' 

# top class (by score) per image for all classifiers applied
# {"image":"20160428095504-749-00.jpg","classes":{"class":"dog","score":0.512194}}
# jq -c '.images[]|{"image":.image,"classes":[.classifiers[].classes[]]|sort_by(.score)[-1]}'

jq '.' "$json"

done:

rm -f /tmp/$0:t.$$.*
