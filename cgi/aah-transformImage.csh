#!/bin/csh -fb
setenv APP "aah"
setenv API "transformImage"
setenv LAN "192.168.1"
setenv WWW "$LAN".32
setenv DIGITS "$LAN".30
setenv WAN "www.dcmartin.com"
setenv TMP "/var/lib/age-at-home"

# CAMERA & TRANSFORMATION INFORMATION (should be a configuration read from device corresponding to device and model)
if ($?CAMERA_IMAGE_WIDTH == 0) setenv CAMERA_IMAGE_WIDTH 640
if ($?CAMERA_IMAGE_HEIGHT == 0) setenv CAMERA_IMAGE_HEIGHT 480
if ($?MODEL_IMAGE_WIDTH == 0) setenv MODEL_IMAGE_WIDTH 224
if ($?MODEL_IMAGE_HEIGHT == 0) setenv MODEL_IMAGE_HEIGHT 224

if ($?VERBOSE) echo `/bin/date` "$0 $$ -- START $*"  >>! $TMP/LOG

set image = "$argv[1]"
set crop = "$argv[2]"

if ($?VERBOSE) echo `/bin/date` "$0 $$ -- GOT $image $image:e $CAMERA_MODEL_TRANSFORM" >>! $TMP/LOG

# process crop
if (-s "$image" && "$image:e" != "jpeg" && $?CAMERA_MODEL_TRANSFORM) then
  set c = `/bin/echo "$crop" | /usr/bin/sed "s/\([0-9]*\)x\([0-9]*\)\([+-]*[0-9]*\)\([+-]*[0-9]*\)/\1 \2 \3 \4/"`
  set w = $c[1]
  set h = $c[2]
  set x = `/bin/echo "0 $c[3]" | /usr/bin/bc`
  set y = `/bin/echo "0 $c[4]" | /usr/bin/bc`

  if ($?VERBOSE) echo `/bin/date` "$0 $$ -- IMAGE $image CROP $c $w $h $x $y"  >>! $TMP/LOG

  switch ($CAMERA_MODEL_TRANSFORM)
    case "RESIZE":
      if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- resizing $image ($MODEL_IMAGE_WIDTH,$MODEL_IMAGE_HEIGHT)" 
      /usr/local/bin/convert \
	  -resize "$MODEL_IMAGE_WIDTH"x"$MODEL_IMAGE_HEIGHT" "$image" \
	  -gravity center \
	  -background gray \
	  "$image:r.jpeg"
      breakw
    case "CROP":
      # calculate centroid-based extant ($MODEL_IMAGE_WIDTHx$MODEL_IMAGE_WIDTH image)
      @ cx = $x + ( $w / 2 ) - ( $MODEL_IMAGE_WIDTH / 2 )
      @ cy = $y + ( $h / 2 ) - ( $MODEL_IMAGE_HEIGHT / 2 )
      if ($cx < 0) @ cx = 0
      if ($cy < 0) @ cy = 0
      if ($cx + $MODEL_IMAGE_WIDTH > $CAMERA_IMAGE_WIDTH) @ cx = $CAMERA_IMAGE_WIDTH - $MODEL_IMAGE_WIDTH
      if ($cy + $MODEL_IMAGE_HEIGHT > $CAMERA_IMAGE_HEIGHT) @ cy = $CAMERA_IMAGE_HEIGHT - $MODEL_IMAGE_HEIGHT
      set crop = "$MODEL_IMAGE_WIDTH"x"$MODEL_IMAGE_HEIGHT"+"$cx"+"$cy"

      if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- cropping $image $crop" 
      /usr/local/bin/convert \
	  -crop "$crop" "$image" \
	  -gravity center \
	  -background gray \
	  "$image:r.jpeg"
      breaksw
    default:
      if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- unknown transformation ($CAMERA_MODEL_TRANSFORM)" 
      breaksw
  endsw
else	
  if ($?VERBOSE) /bin/echo `/bin/date` "$0 $$ -- NO TRANSFORM APPLIED ($image, $crop, $CAMERA_MODEL_TRANSFORM)" 
endif

done:
  if ($?VERBOSE) echo `/bin/date` "$0 $$ -- FINISH $*"  >>! $TMP/LOG
