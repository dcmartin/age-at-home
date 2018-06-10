#!/bin/tcsh -b
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
set xywh = ( `/bin/echo "$crop" | sed "s/\(.*\)x\(.*\)\([+-]\)\(.*\)\([+-]\)\(.*\)/\3\4 \5\6 \1 \2/"` )

if ($path:e == "jpg") then
  @ w = $xywh[3] / 2
  @ h = $xywh[4] / 2
  @ x = `/bin/echo "$w $xywh[1] - 112" | /usr/bin/bc`
  @ y = `/bin/echo "$h $xywh[2] - 112" | /usr/bin/bc`

  if ($x < 0) set x = 0
  if ($y < 0) set y = 0
  set w = `/bin/echo "$x + 224" | /usr/bin/bc`
  set h = `/bin/echo "$y + 224" | /usr/bin/bc`
  if ($w > 640) then
    @ x -= ( $w - 640 )
    @ w = 640
  endif
  if ($h > 480) then
    @ y -= ( $h - 480 )
    @ h = 480
  endif
  set rect = ( $x $y $w $h )
else
  set rect = ( 0 0 224 224 )
endif

convert \
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
    -draw "rectangle $rect" "$out"

if (-e "$out") then
  /bin/dd if="$out"
  /bin/rm -f "$out"
else
  /bin/dd if="$path"
endif
