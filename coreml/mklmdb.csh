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

echo "$0:t $$ -- [debug] $0 $argv ($#argv)" >& /dev/stderr

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

if ($?total) then
  if ($total != 100) then
    echo "$0:t $$ -- [ERROR] set breakdown ($percentages) across $#percentages does not total 100%" >& /dev/stderr
    exit
  endif
endif
if ($?percentages == 0) then
  set percentages = ( 50 50 )
endif

echo "$0:t $$ -- [ARGS] --percentages ($percentages)" >& /dev/stderr

if ($?device == 0) set device = "rough-fog"
echo "$0:t $$ -- [ARGS] device ($device)" >& /dev/stderr

set rootdir = "$ROOTDIR/$device"

if (-d "$rootdir") then
  set stat = ( `stat -r "$rootdir" | awk '{ print $10 }'` )
else
  echo "$0:t $$ -- [ERROR] cannot locate $rootdir" >& /dev/stderr
  exit 1
endif

if ($?ARRAY_SIZE == 0) setenv ARRAY_SIZE 100
echo "$0:t $$ -- [ENV] ARRAY_SIZE ($ARRAY_SIZE)" >& /dev/stderr

###
### TEST IF WE'VE BUILT THE CLASS FILES
###


set json = '{"rootdir":"'"$rootdir"'","thisdir":"'"$cwd"'","device":"'$device'","date":'$stat

@ i = 1
set existing = ()
while ($i <= $#percentages)
  set mfile = "$device.$stat.$i.$percentages[$i].map"
  if (! -e "$mfile") then
    unset ps
    break
  else
    set existing = ( $existing "$mfile" )
    if ($?ps == 0) then
      set ps = "$percentages[$i]"
    else
      set ps = "$ps,$percentages[$i]"
    endif
  endif
  @ i++
end
if ($?ps) then
  set json = "$json""$ps"']'
  unset ps
endif

if ($#existing == $#percentages && -e `echo "$device.$stat.$percentages.json" | sed 's/ /:/g'`) then
    unset json
    echo "$0:t $$ -- [WARN] using existing $existing" >& /dev/stderr
    goto next
endif

if ($?classes == 0) then
  set classes = ()
  set dirs = ( "$ROOTDIR/$device"/* )
  foreach d ( $dirs )
    set t = "$d:t"
    if (-d "$ROOTDIR/$device/$t") then
      echo "$0:t $$ -- [debug] adding $t ($d)" >& /dev/stderr
      set classes = ( $classes "$t" )
    endif
  end
endif
echo "$0:t $$ -- [INFO] classes ($classes)" >& /dev/stderr

if ($#classes < 5) then
  echo "$0:t $$ -- [ERROR] too few classes ($#classes)" >& /dev/stderr
  exit 1
else if ($#classes > $ARRAY_SIZE) then
  echo "$0:t $$ -- [ERROR] too many classes ($#classes); increase ARRAY_SIZE" >& /dev/stderr
  exit 1
endif

if ($?regexp == 0) set regexp = "[0-9]*.jpg"
echo "$0:t $$ -- [ARGS] regexp ($regexp)" >& /dev/stderr

if ($#percentages < 2) then
  echo "$0:t $$ -- [ERROR] too few bins ($#percentages)" >& /dev/stderr
  exit 1
endif

# build map of set identifiers broken by percentages, i.e. { 1, 2 }
rm -f "$TMP/$0:t.$$.buckets.map" "$TMP/$0:t.$$.classes.map"
@ i = 1
while ( $i <= $#percentages )
  set pct = $percentages[$i]

  set nb = `echo "$pct / 100.0 * $ARRAY_SIZE" | bc -l`; set nb = "$nb:r"
  # create buckets equivalent to percentage of array
  echo "$0:t $$ -- [DEBUG] set ($i) has ($nb) buckets" >& /dev/stderr
  jot $nb $i $i >>! "$TMP/$0:t.$$.buckets.map"
  @ i++
end

# create random distribution of classses across buckets
jot -r $ARRAY_SIZE 1 $#classes >! "$TMP/$0:t.$$.classes.map"

# join maps
set assign = ( `paste  "$TMP/$0:t.$$.classes.map" "$TMP/$0:t.$$.buckets.map" | sort -n | awk '{ print $2 }'` )

echo "$0:t $$ -- [DEBUG] total ($#assign) buckets ($assign)" >& /dev/stderr

# clean-up
rm -f "$TMP/$0:t.$$.buckets.map" "$TMP/$0:t.$$.classes.map"

##
## PROCESS ALL IMAGES IN CLASS
##

@ min = 100000
@ max = 0
@ cid = 0
set bucket_counts = ( `jot $ARRAY_SIZE 0 0` )

echo -n "$0:t $$ -- [debug] CLASSES " >& /dev/stderr
@ total = 0
set class_counts = ()
foreach c ( $classes )
  find "$rootdir/$c" -type f -name "$regexp" -print >! "$TMP/$0:t.path"

  # error if none found
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

  set buckets = ( `jot -r $cc 1 $ARRAY_SIZE` )

  @ i = 1
  foreach e ( `cat "$TMP/$0:t.path"` )
    set tid = `echo "$e" | sed "s|$rootdir/||"`
    set bid = $buckets[$i]
    set mid = $assign[$bid]

    @ bucket_counts[$bid]++

    echo "$tid $cid" >>! "$TMP/$0:t.$mid.map"
    @ i++
  end
  rm -f "$TMP/$0:t.path"
  echo -n "$c " >& /dev/stderr
end

echo "(count: $#classes; records: $total; smallest class $smallest ($min) largest class $largest ($max)" >& /dev/stderr

set json = "$json"',"count":'$total',"classes":['

@ c = 1
set class_percentages = ()
while ($c <= $#classes)
  set cc = $class_counts[$c]

  if ($?cs == 0) then
    set cs = '{"class":"'"$classes[$c]"'","count":'"$cc"',"buckets":'"$bucket_counts[$c]"'}'
  else
    set cs = "$cs",'{"class":"'"$classes[$c]"'","count":'"$cc"',"buckets":'"$bucket_counts[$c]"'}'
  endif

  set class_percentages = ( $class_percentages `echo "$cc / $total * 100.0" | bc -l` )
  echo "$0:t $$ -- [INFO] class $classes[$c] ($cc):" `echo "$class_percentages[$#class_percentages]" | awk '{ printf("%.2f%%\n", $1) }'`  >& /dev/stderr
  @ c++
end

if ($?cs) then
  set json = "$json""$cs"']'
  unset cs
else
  set json = "$json"']'
endif

set json = "$json"',"maps":['

set good = ()
@ i = 1
while ($i <= $#percentages)
  set bfile = "$TMP/$0:t.$i.map"

  if (! -e "$bfile") then
    echo "$0:t $$ -- [ERROR] no file $bfile" >& /dev/stderr
    exit
  endif  
  set nl = `wc -l "$bfile" | awk '{ print $1 }'`

  if ($?cs == 0) then
    set cs = '{"id":'$i',"percent":'$percentages[$i]',"count":'$nl',"classes":['
  else
    set cs = "$cs",'{"id":'$i',"percent":'$percentages[$i]',"count":'$nl',"classes":['
  endif

  @ j = 1
  while ($j <= $#classes )
    set cp = $class_percentages[$j]
    set cn = "$classes[$j]"
    set cl = `egrep "$cn/" "$bfile" | wc -l | awk '{ print $1 }'`
    set pc = `echo "$cl / $nl * 100.0" | bc -l`
    set dp = `echo "$cp - $pc" | bc -l | awk '{ printf("%0.4f\n", $1) }'`
    set av = `echo "$dp" | awk '{ v = ( $1 < 0 ? -$1 : $1 ); printf("%d\n", v) }'`

    echo "$0:t $$ -- [debug] set ($i); class ($cn; $pc:r%); " `echo "$cp,$dp" | awk -F, '{ printf("population (%.2f%%) delta (%.2f%%)\n", $1, $2) }'` >& /dev/stderr
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

  set dfile = "$device.$stat.$i.$percentages[$i].map"
  echo "$0:t $$ -- [INFO] $dfile " `echo "$nl" | awk '{ printf("%d, %.2f%%\n", $1, $1 / '"$total"' * 100.0) }'` >& /dev/stderr
  mv -f "$bfile" "$dfile"
  set cs = "$cs"',"file":"'$dfile'"}'
  @ i++
end

if ($?cs) then
  set json = "$json""$cs"']'
  unset cs
else 
  set json = "$json"']'
endif
set json = "$json"'}'

set percent = `echo "$percentages" | sed "s/ /:/g"`
echo "$json" | jq '.name="'"$device.$stat.$percent"'"' >! `echo "$device.$stat.$percent.json"`

next:

if ($?pfile == 0) then
  set percent = `echo "$percentages" | sed "s/ /:/g"`
  set pfile = `echo "$device.$stat.$percent.json"`
endif

if (! -e "$pfile") then
  echo "$0:t $$ -- [ERROR] cannot find parameters: $pfile"
  exit 1
else
  set json = `jq '.' "$pfile"`
endif

if ($?json == 0) then
  echo "$0:t $$ -- [ERROR] no parameters"
  exit 1
endif 

set json = `echo "$json" | jq '.name="'"$pfile:r"'"'`

if ($?MODEL_IMAGE_HEIGHT == 0) setenv MODEL_IMAGE_HEIGHT 224
if ($?MODEL_IMAGE_WIDTH == 0) setenv MODEL_IMAGE_WIDTH 224

echo "$0:t $$ -- [ENV] MODEL_IMAGE_WIDTH $MODEL_IMAGE_WIDTH" >& /dev/stderr
echo "$0:t $$ -- [ENV] MODEL_IMAGE_HEIGHT $MODEL_IMAGE_HEIGHT" >& /dev/stderr

set json = `echo "$json" | jq '.convert={"width":'$MODEL_IMAGE_WIDTH',"height":'$MODEL_IMAGE_WIDTH',"shuffle":true,"backend":"lmdb"}'`

setenv GLOG_logtostderr 1
echo "$0:t $$ -- [ENV] GLOG_logtostderr $GLOG_logtostderr" >& /dev/stderr

set counts = ()
set entries = ()
@ total_entries = 0

@ r = 1
while ($r <= $#percentages)
  set sfile = "$device.$stat.$r.$percentages[$r].map"
  set lfile = "$device.$stat.$r.$percentages[$r].lmdb"

  @ b = $r - 1
  set counts = ( $counts `wc -l "$sfile" | awk '{ print $1 }'` )

  set json = `echo "$json" | jq '.data['$b']={"count":"'$counts[$#counts]'","file":"'"$sfile"'","data":"'"$lfile"'","shuffle":true,"format":"png"}'`

  echo "$0:t $$ -- [INFO] SET: $sfile ( $counts[$#counts] )" >& /dev/stderr

#    --check_size \
#    --encode_type jpg \

  if (-e "$lfile") then
    echo "$0:t $$ -- [INFO] existing $lfile; skipping convert_imageset command" >& /dev/stderr
  else if (! -e "$CAFFE/build/tools/convert_imageset") then
    echo "$0:t $$ -- [ERROR] BLVC Caffe is not installed; trying `$0:h/mkcaffe.csh`" >& /dev/stderr
  else
    $CAFFE/build/tools/convert_imageset \
      --resize_height $MODEL_IMAGE_HEIGHT \
      --resize_width $MODEL_IMAGE_WIDTH \
      --shuffle \
      --backend lmdb \
      "$rootdir"/ \
      "$sfile" \
      "$lfile"
  endif

  if (-e "$lfile" && -d "$lfile") then
    echo "$0:t $$ -- [INFO] SUCCESS: $lfile" >& /dev/stderr
    set entries = ( $entries `mdb_stat "$lfile" | egrep "Entries: " | awk -F: '{ print $2 }'` )
    if ($entries[$#entries] != $counts[$#counts]) then
      echo "$0:t $$ -- [WARN] set $r; count ($counts[$#counts]); entries ($entries[$#entries])" >& /dev/stderr
    endif
    @ total_entries += $entries[$#entries]
 
    if ($?cs == 0) then
      set cs = '{"id":'$r',"file":"'$lfile'","type":"lmdb","count":'$entries[$#entries]'}'
    else
      set cs = "$cs",'{"id":'$r',"file":"'$lfile'","type":"lmdb","count":'$entries[$#entries]'}'
    endif

  else
    echo "$0:t $$ -- [ERROR] FAILURE - $lfile does not exist or is not a directory" >& /dev/stderr
    exit 1
  endif
  @ r++
end
if ($?cs) then
  set json = `echo "$json" | jq '.data=['"$cs"']'`
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

echo "$json" | jq -c '.' | tee "$pfile"
