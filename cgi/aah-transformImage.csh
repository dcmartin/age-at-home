#!/bin/tcsh -b
setenv APP "aah"
setenv API "transformImage"

# debug on/off
# setenv DEBUG true
# setenv VERBOSE true

# environment
if ($?TMP == 0) setenv TMP "/tmp"
if ($?AAHDIR == 0) setenv AAHDIR "/var/lib/age-at-home"
if ($?CREDENTIALS == 0) setenv CREDENTIALS /usr/local/etc
if ($?LOGTO == 0) setenv LOGTO $TMP/$APP.log

# CAMERA & TRANSFORMATION INFORMATION (should be a configuration read from device corresponding to device and model)
if ($?CAMERA_IMAGE_WIDTH == 0) setenv CAMERA_IMAGE_WIDTH 640
if ($?CAMERA_IMAGE_HEIGHT == 0) setenv CAMERA_IMAGE_HEIGHT 480
if ($?MODEL_IMAGE_WIDTH == 0) setenv MODEL_IMAGE_WIDTH 224
if ($?MODEL_IMAGE_HEIGHT == 0) setenv MODEL_IMAGE_HEIGHT 224

if ($?VERBOSE) /bin/echo `/bin/date` "$0:t $$ -- START $*"  >>! $LOGTO

set image = "$argv[1]"
set crop = "$argv[2]"

if ($?VERBOSE) echo `/bin/date` "$0:t $$ -- GOT $image $image:e $CAMERA_MODEL_TRANSFORM" >>! $LOGTO

# process crop
if (-s "$image" && "$image:e" != "jpeg" && $?CAMERA_MODEL_TRANSFORM) then
  set c = `/bin/echo "$crop" | sed "s/\([0-9]*\)x\([0-9]*\)\([+-]*[0-9]*\)\([+-]*[0-9]*\)/\1 \2 \3 \4/"`
  set w = $c[1]
  set h = $c[2]
  set x = `/bin/echo "0 $c[3]" | /usr/bin/bc`
  set y = `/bin/echo "0 $c[4]" | /usr/bin/bc`

  if ($?VERBOSE) /bin/echo `/bin/date` "$0:t $$ -- IMAGE $image CROP $c $w $h $x $y"  >>! $LOGTO

  # the original 
  set xform = `identify "$image" | /usr/bin/awk '{ print $4 }'`

  # switch on transformation requested
  switch ($CAMERA_MODEL_TRANSFORM)
    case "RESIZE":
      set xform = "$MODEL_IMAGE_WIDTH"x"$MODEL_IMAGE_HEIGHT" 
      convert \
	  -resize "$xform" "$image" \
	  -gravity center \
	  -background gray \
	  "$image:r.jpeg"
      breakw
    case "CROP":
      @ cx = $x + ( $w / 2 ) - ( $MODEL_IMAGE_WIDTH / 2 )
      @ cy = $y + ( $h / 2 ) - ( $MODEL_IMAGE_HEIGHT / 2 )
      if ($cx < 0) @ cx = 0
      if ($cy < 0) @ cy = 0
      if ($cx + $MODEL_IMAGE_WIDTH > $CAMERA_IMAGE_WIDTH) @ cx = $CAMERA_IMAGE_WIDTH - $MODEL_IMAGE_WIDTH
      if ($cy + $MODEL_IMAGE_HEIGHT > $CAMERA_IMAGE_HEIGHT) @ cy = $CAMERA_IMAGE_HEIGHT - $MODEL_IMAGE_HEIGHT

      set xform = "$MODEL_IMAGE_WIDTH"x"$MODEL_IMAGE_HEIGHT"+"$cx"+"$cy"
      convert \
	  -crop "$xform" "$image" \
	  -gravity center \
	  -background gray \
	  "$image:r.jpeg"
      breaksw
    default:
      if ($?VERBOSE) /bin/echo `/bin/date` "$0:t $$ -- unknown transformation ($CAMERA_MODEL_TRANSFORM)" >>&! $LOGTO
      breaksw
  endsw
  if (-s "$image:r.jpeg") then
    echo "$CAMERA_MODEL_TRANSFORM" "$xform" "$image:r.jpeg"
  endif
else	
  if ($?VERBOSE) /bin/echo `/bin/date` "$0:t $$ -- NO TRANSFORM APPLIED ($image, $crop, $CAMERA_MODEL_TRANSFORM)" >>&! $LOGTO
endif

done:
  if ($?VERBOSE) echo `/bin/date` "$0:t $$ -- FINISH $*"  >>! $LOGTO
