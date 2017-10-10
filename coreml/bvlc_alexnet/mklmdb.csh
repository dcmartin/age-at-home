#!/bin/csh -fb

if ($?TMP == 0) setenv TMP "/tmp/$0:t.$$"
if (! -e "$TMP" || ! -d "$TMP") mkdir -p "$TMP"

# path to caffe clone from github; needs to be built
if ($?CAFFE == 0) setenv CAFFE ~$user/GIT/caffe
echo '[ENV] CAFFE (' "$CAFFE" ')'

# path to source directory
if ($?AAH_HOME == 0) setenv AAH_HOME /var/lib/age-at-home/label
echo '[ENV] AAH_HOME (' "$AAH_HOME" ')'
if (! -e "$AAH_HOME" || ! -d "$AAH_HOME") then
  echo "[ERROR] directory $AAH_HOME is not available"
  exit 1
endif

echo "[debug] $0 $argv ($#argv)"

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
endif

if ($?total) then
  if ($total != 100) then
    echo "[ERROR] set breakdown ($percentages) across $#percentages does not total 100%"
    exit
  endif
endif
if ($?percentages == 0) then
  set percentages = ( 50 50 )
endif

echo '[ARGS] --percentages ('"$percentages"')'

if ($?device == 0) set device = "rough-fog"
echo '[ARGS] device (' "$device" ')'

set rootdir = "$AAH_HOME/$device"

setenv ARRAY_SIZE 100
echo '[ENV] ARRAY_SIZE (' "$ARRAY_SIZE" ')'

###
### TEST IF WE'VE BUILT THE CLASS FILES
###

@ i = 1
set existing = ()
while ($i <= $#percentages)
  if (! -e "$device.$i.$percentages[$i].txt") then
    break
  else
    set existing = ( $existing "$device.$i.$percentages[$i].txt" )
  endif
  @ i++
end
if ($#existing == $#percentages) then
    echo "[ARGS] using existing $existing"
    goto next
endif

if ($?classes == 0) then
  set classes = ()
  set dirs = ( "$AAH_HOME/$device"/* )
  foreach d ( $dirs )
    set t = "$d:t"
    if (-d "$AAH_HOME/$device/$t") then
      echo "[debug] adding $t ($d)"
      set classes = ( $classes "$t" )
    endif
  end
endif
echo '[INFO] classes (' "$classes" ')'

if ($#classes < 5) then
  echo "[ERROR] too few classes ($#classes)"
  exit 1
endif

if ($?regexp == 0) set regexp = "[0-9]*.jpg"
echo '[ARGS] regexp (' "$regexp" ')'

if ($#percentages < 2) then
  echo "[ERROR] too few set_array ($#percentages)"
  exit 1
endif

# create set for class sizes
@ c = 1
set csizes = ()
while ($c <= $#classes)
  set csizes = ( $csizes 0 )
  @ c++
end

# distribute classes across class_array randomly (1-100)
set class_array = ()
@ r = 1
set time = `date +%s`
set seed = `echo "$time % $$" | bc`

echo -n "[debug] binning: "
while ($r <= $ARRAY_SIZE)
  # RANDOM IS HARD
  set q = ( `awk -v seed="$seed" 'BEGIN{srand(seed); v=rand()*'"$#classes"-1+1'; print int(1+v),v}'` )
  set e = $q[2]:e
  set q = $q[1]
  set c = "$classes[$q]"
  echo -n "$q $c "
  set class_array = ( $class_array "$c" )
  set seed = `echo "$e + $seed" | bc -l`
  @ csizes[$q]++
  @ r++
end
echo ''

set target = `echo "$#classes/$ARRAY_SIZE*100.0" | bc -l`
echo "[debug] total: $total " `echo "$ARRAY_SIZE,$target" | awk -F, '{ printf("%d; target: %.2f%%\n", $1,$2/$1*100.0) }'`

@ c = 1
@ total = 0
@ warn = 0
set ccount = ()
while ($c <= $#classes)
  @ cc = $csizes[$c]
  set tp = `echo "$cc / $ARRAY_SIZE"' * 100.0' | bc -l`
  set av = `echo "$tp,$target" | awk -F, '{ printf("%.2f\n", $1 - $2 ) }'`
  set ap = `echo "$av,$target" | awk -F, '{ printf("%.2f\n", $1/$2*100.0) }'`
  set aa = `echo "$ap" | awk '{ v = ( $1 < 0 ? -$1 : $1 ); print v }'`

  if ("$aa:r" >= 20) then
    echo "[WARN] class $classes[$c] ($cc) @ " `echo "$tp" | awk '{ printf("%.2f%%\n", $1) }'` "; delta $av% ($ap%)"
    @ warn++
  else
    echo "[debug] class $classes[$c] ($cc) @ " `echo "$tp" | awk '{ printf("%.2f%%\n", $1) }'` "; delta $av% ($ap%)"
  endif
  @ total += $cc
  @ c++
  set ccount = ( $ccount 0 )
end

if ($warn) then
  set wp = `echo "$warn / $#classes * 100.0" | bc -l`
  if ("$wp:r" >= 20) then
    echo "[WARN] $warn classes (> $wp:r%) were poorly represented"
  else
    echo "[debug] $warn classes (> $wp:r%) were poorly represented"
  endif
endif

if ($total != $ARRAY_SIZE) then
  echo "[ERROR] invalid distribution; total = $total (should be $ARRAY_SIZE)"
  exit 1
endif

set set_array = ()
@ r = 1
@ s = 1
@ t = $percentages[$s]
set scount = ( 0 )
while ($r <= $ARRAY_SIZE)
  if ($r <= $t) then
    set set_array = ( $set_array $s )
  else
    @ s++
    set set_array = ( $set_array $s )
    set scount = ( $scount 0 )
    @ t += $percentages[$s]
  endif
  @ r ++
end

rm -f "$TMP/$$.txt"
@ g = 1
while ($g <= $#set_array)
  set sid = $set_array[$g] 
  set cid = $class_array[$g]
  echo "$cid $sid" >>! "$TMP/$$.txt"
  @ g++
end
set assign = ( `sort "$TMP/$$.txt" | awk '{ print $2 }'` )


# TESTING

@ g = 1
while ($g <= $#assign)
  set sid = $assign[$g] 
  set cid = $class_array[$g]

  @ sn = 1
  while ( $sn <= $#percentages )
    if ($sid == $sn) then
       @ scount[$sn]++
       break
    endif
    @ sn++
  end
  @ cn = 0
  foreach c ( $classes )
    @ cn++
    if ("$c" == "$cid") then
       @ ccount[$cn]++
       break
    endif
  end
  @ g++
end

#  @ sn = 1
#  while ( $sn <= $#percentages )
#    echo "[debug] SET $sn ( $scount[$sn] $percentages[$sn] )"
#    @ sn++
#  end

#  @ cn = 1
#  foreach c ( $classes )
#    echo "[debug] CLASS $c ( $ccount[$cn] $csizes[$cn] )"
#    @ cn++
#  end

@ min = 100000
@ max = 0
@ cno = 0

@ total = 0
set class_counts = ()
foreach c ( $classes )
  find "$rootdir/$c" -type f -name "$regexp" -print >! "$TMP/$0:t.path"
  if (-e "$TMP/$0:t.path") then
    set cc = `wc -l "$TMP/$0:t.path" | awk '{ print $1 }'`
    if ($?cc == 0) then
      echo "[ERROR] no lines in $TMP/$0:t.path"
      exit 1
    endif
    @ cno++
    @ total += $cc
    set class_counts = ( $class_counts $cc )
    if ($cc < $min) then
      set min = $cc
      set smallest = "$c"
    endif
    if ($class_counts[$#class_counts] > $max) then
      set max = $cc
      set largest = "$c"
    endif
    foreach i ( `cat "$TMP/$0:t.path"` )
      set tid = `echo "$i" | sed "s|$rootdir/||"`
      set time = `date +%s`
      set seed = `stat -r "$i" | awk '{ print $2 }'`
      set seed = `echo "$seed" + "$time" | bc`

      set q = `awk -v seed="$seed" 'BEGIN{srand(seed);print int(1.0+rand()*'"$ARRAY_SIZE"'-1+1)}'`
      echo -n "$assign[$q] "
      echo "$tid $cno" >>! "$TMP/$0:t.$assign[$q].txt"
    end
    echo ''
    rm -f "$TMP/$0:t.path"
  else
    echo "[ERROR] cannot find ($regexp) at $rootdir/$c"
    exit 1
  endif
end

echo "[INFO] CLASSES ($#classes; $total); smallest $smallest ($min) largest $largest ($max)"

@ c = 1
set class_percentages = ()
foreach i ( $class_counts )
  set class_percentages = ( $class_percentages `echo "$i / $total * 100.0" | bc -l` )
  echo "[INFO] class $classes[$c] ($i):" `echo "$class_percentages[$#class_percentages]" | awk '{ printf("%.2f%%\n", $1) }'` 
  @ c++
end

@ i = 1
while ($i <= $#percentages)
  set bfile = "$TMP/$0:t.$i.txt"

  if (! -e "$bfile") then
    echo "[ERROR] no file $bfile"
    exit
  endif  
  set nl = `wc -l "$bfile" | awk '{ print $1 }'`
  @ j = 1
  while ($j <= $#classes )
    set cp = $class_percentages[$j]
    set cn = "$classes[$j]"
    set cl = `egrep "$cn/" "$bfile" | wc -l | awk '{ print $1 }'`
    set pc = `echo "$cl / $nl * 100.0" | bc -l`
    set dp = `echo "$cp - $pc" | bc -l | awk '{ printf("%0.4f\n", $1) }'`
    set av = `echo "$dp" | awk '{ v = ( $1 < 0 ? -$1 : $1 ); printf("%d\n", v) }'`

    if ("$av" >= 5) then
      echo "[WARN] set ($i); class ($cn; $pc:r%); " `echo "$cp,$dp" | awk -F, '{ printf("population (%.2f%%) delta (%.2f%%)\n", $1, $2) }'`
    else
      echo "[debug] set ($i); class ($cn; $pc:r%); " `echo "$cp,$dp" | awk -F, '{ printf("population (%.2f%%) delta (%.2f%%)\n", $1, $2) }'`
    endif
    @ j++
  end
  set dfile = "$device.$i.$percentages[$i].txt"
  echo "[INFO] $dfile " `echo "$nl" | awk '{ printf("%d, %.2f%%\n", $1, $1 / '"$total"' * 100.0) }'`
  mv -f "$bfile" "$dfile"
  @ i++
end

next:

if ($?MODEL_IMAGE_HEIGHT == 0) setenv MODEL_IMAGE_HEIGHT 224
if ($?MODEL_IMAGE_WIDTH == 0) setenv MODEL_IMAGE_WIDTH 224

echo "[ENV] MODEL_IMAGE_WIDTH $MODEL_IMAGE_WIDTH"
echo "[ENV] MODEL_IMAGE_HEIGHT $MODEL_IMAGE_HEIGHT"

setenv GLOG_logtostderr 1
echo "[ENV] GLOG_logtostderr $GLOG_logtostderr"

set counts = ()
set entries = ()
@ total_entries = 0

@ r = 1
while ($r <= $#percentages)
  set sfile = "$device.$r.$percentages[$r].txt"
  set lfile = "$device.$r.$percentages[$r].lmdb"

  set counts = ( $counts `wc -l "$sfile" | awk '{ print $1 }'` )
  echo '[INFO] SET: '"$sfile ( $counts[$#counts] )"

#    --check_size \
#    --encode_type jpg \

  if (-e "$lfile") then
    echo "[INFO] existing $lfile; skipping convert_imageset command"
  else
    $CAFFE/tools/convert_imageset \
      --resize_height $MODEL_IMAGE_HEIGHT \
      --resize_width $MODEL_IMAGE_WIDTH \
      --shuffle \
      --backend lmdb \
      "$rootdir"/ \
      "$sfile" \
      "$lfile"
  endif

  if (-e "$lfile" && -d "$lfile") then
    echo "[INFO] SUCCESS: $lfile"
    set entries = ( $entries `mdb_stat "$lfile" | egrep "Entries: " | awk -F: '{ print $2 }'` )
    if ($entries[$#entries] != $counts[$#counts]) then
      echo "[WARN] set $r; count ($counts[$#counts]); entries ($entries[$#entries])"
    endif
    @ total_entries += $entries[$#entries]
  else
    echo "[ERROR] FAILURE - $lfile does not exist or is not a directory"
    exit 1
  endif
  @ r++
end

if ($#entries) then
  @ i = 1
  while ($i <= $#entries)
    echo "[INFO] set $i; entries ($entries[$i]; " `echo "$entries[$i] / $total_entries * 100.0" | bc -l` "%"
    @ i++ 
  end
else
  echo "[ERROR] no entries ???"
  exit 1
endif

