#!/bin/bash

# INITIATE DEVICE
IPADDR=$(/bin/hostname -I | /usr/bin/awk '{ print $1 }')

JSON='{"name":"'"${DEVICE_NAME}"'","date":'$(/bin/date +%s)',"location":"'"${AAH_LOCATION}"'","ip_address":"'"${IPADDR}"'"'

if [ -n "${DIGITS_JOB_ID}" ] && [ -n "${DIGITS_SERVER_URL}" ]; then
  JOBIDS=$(echo "${DIGITS_JOB_ID}" | sed 's/\([^,]*\)\([,]*\)/"\1"\2/g')
  echo "Using DIGITS ${JOBIDS}"
  JSON="${JSON}"',"digits":{"host":"'"${DIGITS_SERVER_URL}"'","models":['"${JOBIDS}"']}'
fi

if [ -n "${VR_URL}" ] && [ -n "${VR_APIKEY}" ]; then
  echo "Using Watson Visual Recognition at ${VR_URL} with ${VR_DATE} and {$VR_VERSION}"
  JSON="${JSON}"',"watson":{"release":"'"${VR_DATE}"'","version":"'"${VR_VERSION}"'","models":["default"'
  if [ -n "${VR_CLASSIFIER}" ]; then
    # quote the model names
    CLASSIFIERS=$(echo "${VR_CLASSIFIER}" | sed 's/\([^,]*\)\([,]*\)/"\1"\2/g')
    echo 'Using custom classifiers(s):'"${CLASSIFIERS}"
    JSON="${JSON}"','"${CLASSIFIERS}"
  fi
  JSON="${JSON}"']}'
fi

if [ -n "${URL_LAUNCHER_URL}" ]; then
  echo "Using ELECTRON for ${URL_LAUNCHER_URL}"
  JSON="${JSON}"',"electron":"'"${URL_LAUNCHER_URL}"'"'
fi

if [ -n "${MQTT_ON}" ] && [ -n "${MQTT_HOST}" ]; then
  echo "Using MQTT on ${MQTT_HOST}"
  JSON="${JSON}"',"mqtt":"'"${MQTT_HOST}"'"'
fi

if [ -n "${EMAILME_ON}" ] && [ -n "${EMAIL_ADDRESS}" ]; then
  echo "Sending email to ${EMAIL_ADDRESS}"
  JSON="${JSON}"',"email":"'"${EMAIL_ADDRESS}"'"'
fi

# Set the correct timezone
if [ -n "${TIMEZONE}" ]; then
    echo "Setting TIMEZONE ${TIMEZONE}"
    cp /usr/share/zoneinfo/${TIMEZONE} /etc/localtime
    JSON="${JSON}"',"timezone":"'"${TIMEZONE}"'"'
fi

# Override capture size for Motion
if [ -n "${MOTION_PIXELS}" ]; then
    echo "Set capture size to ${MOTION_PIXELS}"
    IFS='x' read -a wxh<<< "${MOTION_PIXELS}"
    WIDTH=${wxh[0]}
    HEIGHT=${wxh[1]}
    sed -i "s/^width\s[0-9]\+/width ${WIDTH}/g" /etc/motion/motion.conf
    sed -i "s/^height\s[0-9]\+/height ${HEIGHT}/g" /etc/motion/motion.conf
else
    WIDTH=640
    HEIGHT=480
fi
JSON="${JSON}"',"image":{"width":'"${WIDTH}"',"height":'"${HEIGHT}"'}'

#
# override motion 
#

# Override locate_motion_mode
if [ -n "${MOTION_LOCATE_MODE}" ]; then
    echo "Set locate_motion_mode (on/off/preview) to ${MOTION_LOCATE_MODE}"
    sed -i "s/^locate_motion_mode\s.*/locate_motion_mode ${MOTION_LOCATE_MODE}/g" /etc/motion/motion.conf
    JSON="${JSON}"',"locate_mode":"'"${MOTION_LOCATE_MODE}"'"'
fi

# Override control and video ports
if [ -n "${WEBCONTROL_PORT}" ]; then
    echo "Set webcontrol_port to ${WEBCONTROL_PORT}"
    sed -i "s/^webcontrol_port\s[0-9]\+/webcontrol_port ${WEBCONTROL_PORT}/g" /etc/motion/motion.conf
    JSON="${JSON}"',"webcontrol_port":'"${WEBCONTROL_PORT}"
fi
if [ -n "${STREAM_PORT}" ]; then
    echo "Set stream_port to ${STREAM_PORT}"
    sed -i "s/^stream_port\s[0-9]\+/stream_port ${STREAM_PORT}/g" /etc/motion/motion.conf
    JSON="${JSON}"',"stream_port":'"${STREAM_PORT}"
fi
if [ -n "${MOTION_IMAGE_ROTATE}" ]; then
    echo "Set image rotation to ${MOTION_IMAGE_ROTATE} degrees"
    sed -i "s/^rotate\s[0-9]\+/rotate ${MOTION_IMAGE_ROTATE}/g" /etc/motion/motion.conf
    JSON="${JSON}"',"image_rotate":'"${MOTION_IMAGE_ROTATE}"
fi

# Override THRESHOLD_TUNE (which pictures selected; on, off, first, best, center); default "center"
if [ -n "${MOTION_OUTPUT_PICTURES}" ]; then
    echo "Set output pictures to ${MOTION_OUTPUT_PICTURES}"
    sed -i "s/^output_pictures\s.*/output_pictures ${MOTION_OUTPUT_PICTURES}/g" /etc/motion/motion.conf
    JSON="${JSON}"',"output_pictures":"'"${MOTION_OUTPUT_PICTURES}"'"'
fi

# Override THRESHOLD_TUNE (pixels changed) default "off"
if [ -n "${MOTION_THRESHOLD_TUNE}" ]; then
   echo "Set threshold_tune to ${MOTION_THRESHOLD_TUNE}"
   sed -i "s/^threshold_tune\s.*/threshold_tune ${MOTION_THRESHOLD_TUNE}/g" /etc/motion/motion.conf
   JSON="${JSON}"',"threshold_tune":"'"${MOTION_THRESHOLD_TUNE}"'"'
fi
# Override THRESHOLD (pixels changed) default 1500
if [ -n "${MOTION_THRESHOLD}" ]; then
   echo "Set threshold to ${MOTION_THRESHOLD}"
    sed -i "s/^threshold\s[0-9]\+/threshold ${MOTION_THRESHOLD}/g" /etc/motion/motion.conf
    JSON="${JSON}"',"threshold":'"${MOTION_THRESHOLD}"
fi

# Override EVENT_GAP (seconds) default 10
if [ -n "${MOTION_EVENT_GAP}" ]; then
   echo "Set event_gap to ${MOTION_EVENT_GAP}"
   sed -i "s/^event_gap\s[0-9]\+/event_gap ${MOTION_EVENT_GAP}/g" /etc/motion/motion.conf
   JSON="${JSON}"',"event_gap":'"${MOTION_EVENT_GAP}"
fi

#
# setup IBM IOTF
#
if [ -n "${IOTF_ORG_ID}" ]; then
    IOTF_CONFIG_FILE="/etc/iotsample-raspberrypi/device.cfg"
    echo "#Device configuration file" > "${IOTF_CONFIG_FILE}"
    echo "org = ${IOTF_ORG_ID}" >> "${IOTF_CONFIG_FILE}"
    echo "type = ${IOTF_DEVICE_TYPE}" >> "${IOTF_CONFIG_FILE}"
    echo "id = ${IOTF_DEVICE_ID}" >> "${IOTF_CONFIG_FILE}"
    echo "auth-method = ${IOTF_AUTH_METHOD}" >> "${IOTF_CONFIG_FILE}"
    echo "auth-token = ${IOTF_AUTH_TOKEN}" >> "${IOTF_CONFIG_FILE}"
    echo "#End of Configuration file" >> "${IOTF_CONFIG_FILE}"
    JSON="${JSON}"',"iotf":{"org":"'"${IOTF_ORG_ID}"'","type":"'"${IOTF_DEVICE_TYPE}"'","id":"'"${IOTF_DEVICE_ID}"'"}'
fi


JSON="${JSON}"'}'

/bin/echo "${JSON}" | jq '.'

if [ -n "${CLOUDANT_URL}" ] && [ -n "${DEVICE_NAME}" ]; then
  echo "Using CLOUDANT as ${CLOUDANT_USERNAME}"
  URL="${CLOUDANT_URL}/devices"
  DB=$(curl -q -s -X GET "${URL}" | jq '.db_name')
    if [ "${DB}" == "null" ]; then
        # create DB
        DB=$(curl -q -s -X PUT "${CLOUDANT_URL}/devices" | jq '.ok')
        if [ "${DB}" != "true" ]; then
            CLOUDANT_OFF=TRUE
        fi
    fi
    if [ -z "${CLOUDANT_OFF}" ]; then
        URL="${URL}/${DEVICE_NAME}"
        REV=$(curl -s -q "${URL}" | jq -r '._rev')
        if [ -n "${REV}" ]; then
          URL="${URL}?rev=${REV}"
        fi
        echo "Updating ${DEVICE_NAME} with ${URL}"
        curl -q -s -H "Content-type: application/json" -X PUT "${URL}" -d "${JSON}"
    fi
else
    echo "+++ $0 NO CLOUDANT ${JSON}"
fi

# restart, check status, getdeviceid
service iot restart
service iot status
service iot getdeviceid

# VSFTPD
service vsftpd restart
service vsftpd status

# FONTS
mkdir -p ~/.magick
convert -list font \
  | awk -F': ' 'BEGIN { printf("<?xml version=\"1.0\"?>\n<typemap>\n"); } /Font: / { font=$2; getline; family=$2; getline; style=$2; getline; stretch=$2; getline; weight=$2; getline; glyphs=$2; type=substr(glyphs,index(glyphs,".")+1,3); printf("<type format=\"%s\" name=\"%s\" glyphs=\"%s\"\n", type, font, glyphs); } END { printf("</typemap>\n"); }' > ~/.magick/type.xml

if [ -n "${MOTION_DAEMON}" ]; then
   echo "Set daemon to ${MOTION_DAEMON}"
   sed -i "s/^daemon\s.*/daemon ${MOTION_DAEMON}/g" /etc/motion/motion.conf
fi

if [ -n "${URL_LAUNCHER_URL}" ]; then
  # override motion daemon status for electron
  echo 'Overriding MOTION_DAEMON to "on" for ELECTRON'
  sed -i "s/^daemon\s.*/daemon on/g" /etc/motion/motion.conf
  # Run motion (as daemon)
  echo "START MOTION AS DAEMON"
  motion -l /dev/stderr
  # By default docker gives us 64MB of shared memory size but to display heavy pages we need more.
  umount /dev/shm && mount -t tmpfs shm /dev/shm
  # start X
  rm /tmp/.X0-lock &>/dev/null || true
  echo "START ELECTRON"
  startx /usr/src/app/node_modules/electron/dist/electron /usr/src/app --enable-logging
else
  # Run motion (not as daemon)
  echo "START MOTION WITHOUT ELECTRON"
  motion -n -l /dev/stderr
fi
