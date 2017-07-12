#!/bin/csh -fb
set path = $1
set class = $2
set crop = $3

switch ($path:e)
    case "jpeg": # 224x224 image
	set csize = "200x20"
	set psize = "18"
      breaksw
    case "jpg": # 640x480 image
    default:
      set csize = "600x40"
      set psize = "48"
      breaksw
endsw

set out = "$path:r.$$.$path:e"
set x = ( `/bin/echo "$crop" | /usr/bin/sed "s/\(.*\)x\(.*\)\([+-]\)\(.*\)\([+-]\)\(.*\)/\3\4 \5\6 \1 \2/"` )

/usr/local/bin/convert \
    -pointsize "$psize" -size "$csize" \
    xc:none -gravity center -stroke black -strokewidth 2 -annotate 0 \
    "$class" \
    -background none -shadow "100x3+0+0" +repage -stroke none -fill white -annotate 0 \
    "$class" \
    "$path" \
    +swap -gravity south -geometry +0-3 -composite \
    -fill none \
    -stroke white \
    -strokewidth 3 \
    -draw "rectangle $x[1],$x[2] $x[3],$x[4]" "$out"

if (-s "$out") then
  /bin/dd if="$out"
  /bin/rm -f "$out"
else
  /bin/dd if="$path"
endif
