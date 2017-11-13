#!/bin/csh -fb

if ($?TMP == 0) setenv TMP "/tmp/$0:t.$$"
if (! -e "$TMP" || ! -d "$TMP") mkdir -p "$TMP"

if ($?CAFFE == 0) setenv CAFFE "$0:h/caffe"
echo "$0:t $$ -- [ENV] CAFFE ($CAFFE)" >& /dev/stderr

if (! -e "$CAFFE") then
  echo "$0:t $$ -- [ERROR] please install BLVC Caffe in ($CAFFE)" >& /dev/stderr
  exit 1
endif

# path to source directory
if ($?ROOTDIR == 0) setenv ROOTDIR /var/lib/age-at-home/label
echo "$0:t $$ -- [ENV] ROOTDIR ($ROOTDIR)" >& /dev/stderr
if (! -e "$ROOTDIR" || ! -d "$ROOTDIR") then
  echo "$0:t $$ -- [ERROR] directory $ROOTDIR is not available" >& /dev/stderr
  exit 1
endif

if ($?DEBUG) echo "$0:t $$ -- [debug] $0 $argv ($#argv)" >& /dev/stderr

# get source
if ($#argv > 0) then
  set device = "$argv[1]"
endif

if ($#argv > 1) then
  @ i = 2
  set total = 0
  set percentages = ()
  while ($i <= $#argv)
    @ t = $argv[$i]
    @ total += $t
    set percentages = ( $percentages $t )
    @ i++
  end
else
  set total = 100
endif

if ($#percentages < 2) then
  echo "$0:t $$ -- [ERROR] too few bins ($#percentages)" >& /dev/stderr
  exit 1
endif

if ($?total) then
  if ($total != 100) then
    echo "$0:t $$ -- [ERROR] set breakdown ($percentages) across $#percentages does not total 100%" >& /dev/stderr
    exit
  endif
endif

###
### DEFAULTS
###

if ($?percentages == 0) set percentages = ( 50 50 )
if ($?regexp == 0) set regexp = "[0-9]*.jpg"
if ($?device == 0) set device = "rough-fog"
if ($?ARRAY_SIZE == 0) setenv ARRAY_SIZE 100
if ($?MINIMUM_CLASS_COUNT == 0) setenv MINIMUM_CLASS_COUNT 5

echo "$0:t $$ -- [ENV] ARRAY_SIZE ($ARRAY_SIZE)" >& /dev/stderr
echo "$0:t $$ -- [ENV] MINIMUM_CLASS_COUNT ($MINIMUM_CLASS_COUNT)" >& /dev/stderr
echo "$0:t $$ -- [ARGS] $device $percentages $regexp" >& /dev/stderr

###
### TEST IF WE'VE BUILT THE CLASS FILES
###

set config = ( `echo "$device.$percentages.json" | sed 's/ /:/g'` )
if (-e "$config") then
  set rootdir = ( `jq '.rootdir' "$config"` )
  set thisdir = ( `jq '.thisdir' "$config"` )
  set date = ( `jq '.date' "$config"` )


  if ($#rootdir && $#thisdir) then
    if ($?DEBUG) echo "$0:t $$ -- [debug] using configuration $config" >& /dev/stderr
    set json = ( `jq '.' "$config"` )
    if ($?DEBUG) echo "$0:t $$ -- [debug] json = $json" >& /dev/stderr
  else
    echo "$0:t $$ -- [ERROR] failed to parse $config" >& /dev/stderr
    exit 1
  endif
else
  set rootdir = "$ROOTDIR/$device"
  set thisdir = "$cwd"
endif

##
## LOOK FOR EXISTING MAPS AND DATA
##

if ($?json) then
  set maps = ( `echo "$json" | jq -r '.sample.maps[].file'` )
  if ($#maps == 0 || "$maps" == "null") then
    if ($?DEBUG) echo "$0:t $$ -- [debug] no defined maps" >& /dev/stderr
    set maps = ()
  else
    if ($?DEBUG) echo "$0:t $$ -- [debug] existing maps $maps" >& /dev/stderr
  endif
  set data = ( `echo "$json" | jq -r '.sample.data[].file'` )
  if ($#data == 0 || "$data" == "null") then
    if ($?DEBUG) echo "$0:t $$ -- [debug] no defined data" >& /dev/stderr
    set data = ()
  else
    if ($?DEBUG) echo "$0:t $$ -- [debug] existing data $data" >& /dev/stderr
  endif
else
  set json = '{"rootdir":"'"$rootdir"'","thisdir":"'"$thisdir"'","device":"'$device'","date":'$?date'}'
  set maps = ()
  set data = ()
endif

##
## TEST MAPS AND DATA AND ROOTDIR
##

# DETERMINE SOURCE DATE
if ($?date == 0 && ! -d "$rootdir") then
  echo "$0:t $$ -- [ERROR] cannot locate $rootdir" >& /dev/stderr
  exit 1
else 
  if (-e "$rootdir") then
    set stat = ( `stat -r "$rootdir" | awk '{ print $10 }'` )
  endif
  if ($?stat && $?date) then
    if ($stat > $date) then
      set maps = ()
      set data = ()
    else
      foreach f ( $maps $data )
        if (! -e "$thisdir/$f") then
          set maps = ()
          set data = ()
          break
        endif
      end
    endif
  else if ($?stat) then
    set date = $stat
  endif
  if (($#maps == 0 || $#data == 0) && $?date == 0) then
    echo "$0:t $$ -- [ERROR] cannot locate $rootdir" >& /dev/stderr
    exit 1
  endif
endif 

## TEST IF MAPS AND DATA ARE COMPLETE
if ($#maps && $#data) then
  echo "$0:t $$ -- [WARN] $device ($date) -- existing MAPS ($maps) and DATA ($data)" >& /dev/stderr
  goto next
endif

###
### BUILD MAPS AND DATA
### 

## COUNT / VALIDATE CLASSES
set dirs = ( "$rootdir"/* )
if ($?dirs == 0) set dirs = ()
if ($#dirs == 0) then
  echo "$0:t $$ -- [ERROR] cannot locate subdirectories in $rootdir" >& /dev/stderr
  exit 1
endif

foreach d ( $dirs )
  set t = "$d:t"
  if (-d "$rootdir/$t") then
    echo "$0:t $$ -- [debug] adding $t ($d)" >& /dev/stderr
    if ($?classes) then
      set classes = ( $classes "$t" )
    else
      set classes = ( "$t" )
    endif
  endif
end
# test class count
if ($#classes < $MINIMUM_CLASS_COUNT) then
  echo "$0:t $$ -- [ERROR] too few classes ($#classes); minimum = $MINIMUM_CLASS_COUNT" >& /dev/stderr
  exit 1
else if ($#classes > $ARRAY_SIZE) then
  echo "$0:t $$ -- [ERROR] too many classes ($#classes); increase ARRAY_SIZE" >& /dev/stderr
  exit 1
else
  echo "$0:t $$ -- [INFO] found $#classes classes (subdirectories) in $rootdir" >& /dev/stderr
endif

## BUILD RANDOM MAPPING by sets (percentages)
rm -f "$TMP/$0:t.$$.buckets.map" "$TMP/$0:t.$$.classes.map"
@ i = 1
while ( $i <= $#percentages )
  set pct = $percentages[$i]

  set nb = `echo "$pct / 100.0 * $ARRAY_SIZE" | bc -l`; set nb = "$nb:r"
  # create buckets equivalent to percentage of array
  if ($?DEBUG) echo "$0:t $$ -- [debug] set ($i) has ($nb) buckets" >& /dev/stderr
  jot $nb $i $i >>! "$TMP/$0:t.$$.buckets.map"
  @ i++
end
# create random distribution of classses across buckets & join maps
jot -r $ARRAY_SIZE 1 $#classes >! "$TMP/$0:t.$$.classes.map"
set assign = ( `paste  "$TMP/$0:t.$$.classes.map" "$TMP/$0:t.$$.buckets.map" | sort -n | awk '{ print $2 }'` )
rm -f "$TMP/$0:t.$$.buckets.map" "$TMP/$0:t.$$.classes.map"

if ($?DEBUG) echo "$0:t $$ -- [debug] total ($#assign) buckets ($assign)" >& /dev/stderr

##
## PROCESS ALL IMAGES IN CLASS
##

## PROCESS ALL CLASS IMAGES
if ($?DEBUG) echo -n "$0:t $$ -- [debug] CLASSES " >& /dev/stderr

@ min = 100000
@ max = 0
@ cid = 0
@ total = 0
set class_counts = ()
set bucket_counts = ( `jot $ARRAY_SIZE 0 0` )

## BUILD RANDOM MAPPINGS FOR IMAGES ACROSS CLASSES
foreach c ( $classes )
  # find all the images matching the expression
  find "$rootdir/$c" -type f -name "$regexp" -print >! "$TMP/$0:t.path"
  if (! -e "$TMP/$0:t.path") then
    echo "$0:t $$ -- [ERROR] cannot find ($regexp) at $rootdir/$c" >& /dev/stderr
    exit 1
  endif
  # count lines
  set cc = `wc -l "$TMP/$0:t.path" | awk '{ print $1 }'`
  if ($?cc == 0) then
    echo "$0:t $$ -- [ERROR] no lines in $TMP/$0:t.path" >& /dev/stderr
    exit 1
  endif
  # increment total and keep track of counts
  @ cid++
  @ total += $cc
  set class_counts = ( $class_counts $cc )
  # keep track of smallest and largest
  if ($cc < $min) then
    set min = $cc
    set smallest = "$c"
  endif
  if ($class_counts[$#class_counts] > $max) then
    set max = $cc
    set largest = "$c"
  endif
  # create buckets for distribution
  set buckets = ( `jot -r $cc 1 $ARRAY_SIZE` )
  # loop over all images
  @ i = 1
  foreach e ( `cat "$TMP/$0:t.path"` )
    set tid = `echo "$e" | sed "s|$rootdir/||"`
    set bid = $buckets[$i]
    set mid = $assign[$bid]
    # keep track of counts of buckers per classes
    @ bucket_counts[$bid]++
    # build map file for consumption below (MAP)
    echo "$tid $cid" >>! "$TMP/$0:t.$mid.map"
    @ i++
  end
  rm -f "$TMP/$0:t.path"
  if ($?DEBUG) echo -n "$c " >& /dev/stderr
end

## UPDATE JSON
set json = ( `echo "$json" | jq '.source.count='"$total"` )

if ($?DEBUG) echo "$0:t $$ -- [debug] classes: $#classes; records: $total; smallest class $smallest ($min) largest class $largest ($max)" >& /dev/stderr

## BUILD CLASS DETAILS (name, count, buckets)
@ c = 1
set class_percentages = ()
while ($c <= $#classes)
  set cc = $class_counts[$c]

  if ($?cs == 0) then
    set cs = '{"class":"'"$classes[$c]"'","count":'"$cc"'}'
  else
    set cs = "$cs",'{"class":"'"$classes[$c]"'","count":'"$cc"'}'
  endif
  set class_percentages = ( $class_percentages `echo "$cc / $total * 100.0" | bc -l` )
  echo "$0:t $$ -- [INFO] class $classes[$c] ($cc):" `echo "$class_percentages[$#class_percentages]" | awk '{ printf("%.2f%%\n", $1) }'`  >& /dev/stderr
  @ c++
end
# update JSON 
if ($?cs) then
  set json = ( `echo "$json" | jq '.source.classes=['"$cs"']'` )
  unset cs
endif

## BUILD MAPS for percentages
set good = ()
@ i = 1
while ($i <= $#percentages)
  # find the prior MAP 
  set bfile = "$TMP/$0:t.$i.map"
  # sanity check
  if (! -e "$bfile") then
    echo "$0:t $$ -- [ERROR] no file $bfile" >& /dev/stderr
    exit
  endif  
  # count lines
  set nl = `wc -l "$bfile" | awk '{ print $1 }'`
  # record map (1,2,..)
  if ($?cs == 0) then
    set cs = '{"id":'$i',"percent":'$percentages[$i]',"count":'$nl',"classes":['
  else
    set cs = "$cs",'{"id":'$i',"percent":'$percentages[$i]',"count":'$nl',"classes":['
  endif
  # loop over all classes
  @ j = 1
  while ($j <= $#classes )
    set cp = $class_percentages[$j]
    set cn = "$classes[$j]"
    set cl = `egrep "$cn/" "$bfile" | wc -l | awk '{ print $1 }'`
    set pc = `echo "$cl / $nl * 100.0" | bc -l`
    set dp = `echo "$cp - $pc" | bc -l | awk '{ printf("%0.4f\n", $1) }'`
    set av = `echo "$dp" | awk '{ v = ( $1 < 0 ? -$1 : $1 ); printf("%d\n", v) }'`

    if ($?DEBUG) echo "$0:t $$ -- [debug] set ($i); class ($cn; $pc:r%); " `echo "$cp,$dp" | awk -F, '{ printf("population (%.2f%%) delta (%.2f%%)\n", $1, $2) }'` >& /dev/stderr
    # build class set statistics
    if ($?css) then
      set css = "$css",'{"name":"'"$cn"'","count":'$cl'}'
    else
      set css = '{"name":"'"$cn"'","count":'$cl'}'
    endif
    @ j++
  end
  if ($?css) then
    set cs = "$cs""$css"']'
    unset css
  else
    set cs = "$cs"']'
  endif
  set dfile = "$device.$i.$percentages[$i].map"
  echo "$0:t $$ -- [INFO] $dfile " `echo "$nl" | awk '{ printf("%d, %.2f%%\n", $1, $1 / '"$total"' * 100.0) }'` >& /dev/stderr
  mv -f "$bfile" "$dfile"
  set cs = "$cs"',"file":"'$dfile'"}'
  @ i++
end
# update JSON
if ($?cs) then
  set json = ( `echo "$json" | jq '.sample.maps=['"$cs"']'` )
  unset cs
endif

##
## STORE CONFIGURATION (JSON)
##

set json = ( `echo "$json" | jq '.name="'"$config:r"'"' ` )
set date = ( `date +%s` )
set json = ( `echo "$json" | jq '.date='"$date"` )

echo "$json" | jq '.' >! "$config"

###
### PROCESS DATA
###

next:

# sanity check
if (! -e "$config") then
  echo "$0:t $$ -- [ERROR] cannot find parameters: $config"
  exit 1
else
  # get some JSON
  set json = `jq '.' "$config"`
endif
# one last check
if ($?json == 0) then
  echo "$0:t $$ -- [ERROR] no parameters"
  exit 1
endif 

## DEFINE STANDARDS
if ($?MODEL_IMAGE_HEIGHT == 0) setenv MODEL_IMAGE_HEIGHT 224
if ($?MODEL_IMAGE_WIDTH == 0) setenv MODEL_IMAGE_WIDTH 224
if ($?SAMPLE_SET_FORMAT == 0) setenv SAMPLE_SET_FORMAT lmdb
if ($?SAMPLE_DATA_FORMAT == 0) setenv SAMPLE_DATA_FORMAT png

echo "$0:t $$ -- [ENV] MODEL_IMAGE_WIDTH $MODEL_IMAGE_WIDTH" >& /dev/stderr
echo "$0:t $$ -- [ENV] MODEL_IMAGE_HEIGHT $MODEL_IMAGE_HEIGHT" >& /dev/stderr

## ENVIRONMENT FOR CAFFE EXECUTION
if ($?GLOG_logtostderr == 0) setenv GLOG_logtostderr 1
if ($?DEBUG) echo "$0:t $$ -- [ENV] GLOG_logtostderr $GLOG_logtostderr" >& /dev/stderr

##
## CONVERT SELECTED DATA (IMAGES) INTO DISTINCT SETS (by MAP) using CAFFE (convert_imageset)
## 
set counts = ()
set entries = ()
@ total_entries = 0
@ r = 1
while ($r <= $#percentages)
  set sfile = "$device.$r.$percentages[$r].map"
  set lfile = "$device.$r.$percentages[$r].lmdb"

  @ b = $r - 1
  set counts = ( $counts `wc -l "$sfile" | awk '{ print $1 }'` )

  if ($?DEBUG) echo "$0:t $$ -- [debug] SET: $sfile ( $counts[$#counts] )" >& /dev/stderr

  # should really check modification time 
  if (-e "$lfile") then
    echo "$0:t $$ -- [INFO] existing $lfile; skipping convert_imageset command" >& /dev/stderr
  else if (! -e "$CAFFE/build/tools/convert_imageset") then
    echo "$0:t $$ -- [ERROR] BLVC Caffe is not installed" >& /dev/stderr
    exit 1
  else
    # create an imageset using CAFFE tooling
    $CAFFE/build/tools/convert_imageset \
      --resize_height $MODEL_IMAGE_HEIGHT \
      --resize_width $MODEL_IMAGE_WIDTH \
      --shuffle \
      --backend lmdb \
      "$rootdir"/ \
      "$sfile" \
      "$lfile"
#    --check_size \
#    --encode_type jpg \
  endif

  if (-e "$lfile" && -d "$lfile") then
    echo "$0:t $$ -- [INFO] SUCCESS: $lfile" >& /dev/stderr
    set entries = ( $entries `mdb_stat "$lfile" | egrep "Entries: " | awk -F: '{ print $2 }'` )
    if ($entries[$#entries] != $counts[$#counts]) then
      echo "$0:t $$ -- [WARN] set $r; count ($counts[$#counts]); entries ($entries[$#entries])" >& /dev/stderr
    endif
    @ total_entries += $entries[$#entries]
 
    if ($?cs == 0) then
      set cs = '{"id":'$r',"file":"'$lfile'","count":'$entries[$#entries]'}'
    else
      set cs = "$cs",'{"id":'$r',"file":"'$lfile'","count":'$entries[$#entries]'}'
    endif
  else
    echo "$0:t $$ -- [ERROR] FAILURE - $lfile does not exist or is not a directory" >& /dev/stderr
    exit 1
  endif
  @ r++
end
if ($?cs) then
  ## UPDATE JSON
  set convert = '{"width":'$MODEL_IMAGE_WIDTH',"height":'$MODEL_IMAGE_WIDTH',"shuffle":true,"format":"'$SAMPLE_DATA_FORMAT'","backend":"'$SAMPLE_SET_FORMAT'"}'
  set json = ( `echo "$json" | jq '.sample.convert='"$convert"` )
  set json = `echo "$json" | jq '.sample.data=['"$cs"']'`
  unset cs
else
  echo "$0:t $$ -- [ERROR] FAILURE - no data" >& /dev/stderr
  exit 1
endif

if ($#entries) then
  @ i = 1
  while ($i <= $#entries)
    echo "$0:t $$ -- [INFO] set $i; entries ($entries[$i]; " `echo "$entries[$i] / $total_entries * 100.0" | bc -l` "%" >& /dev/stderr
    @ i++ 
  end
else
  echo "$0:t $$ -- [ERROR] no entries ???" >& /dev/stderr
  exit 1
endif

output:

echo "$json" | jq -c '.' | tee "$config"
