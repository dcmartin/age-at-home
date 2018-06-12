#!/bin/tcsh -b
setenv APP "aah"
setenv API "ftpImage"

# debug on/off
setenv DEBUG true
setenv VERBOSE true

# environment
if ($?LAN == 0) setenv LAN "192.168.1"
if ($?DIGITS == 0) setenv DIGITS "$LAN".30
if ($?TMP == 0) setenv TMP "/tmp"
if ($?AAHDIR == 0) setenv AAHDIR "/var/lib/age-at-home"
if ($?CREDENTIALS == 0) setenv CREDENTIALS /usr/local/etc
if ($?LOGTO == 0) setenv LOGTO $TMP/$APP.log

if ($?DEBUG) echo `/bin/date` "$0 $$ -- START $*"  >>! $LOGTO

set id = "$argv[1]"
set ext = "$argv[2]"
set ipaddr = "$argv[3]"
set image = "$argv[4]"

if ($?DEBUG) echo `/bin/date` "$0 $$ -- GOT $id $ext $ipaddr $image" >>! $LOGTO

set ftp = "ftp://ftp:ftp@$ipaddr/$id.$ext"
curl -s -q -L "$ftp" -o "/tmp/$$.$ext"
if (! -s "/tmp/$$.$ext") then
  /bin/rm -f "/tmp/$$.$ext"
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- WARNING -- FTP FAILURE ($ftp)" >>! $LOGTO
else
  /bin/mv -f "/tmp/$$.$ext" "$image"
endif
if (-s "$image") then
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- GET image SUCCESS ($image) ($ftp)" >>! $LOGTO
else
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- GET image FAILURE ($ftp) ($image)" >>! $LOGTO
endif
# optionally delete the source
if ($?FTP_DELETE) then
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- deleting ($id.$ext)" >>! $LOGTO
    curl -s -q -L "ftp://$ipaddr/" -Q "-DELE $id.$ext"
endif

done:
  if ($?DEBUG) echo `/bin/date` "$0 $$ -- FINISH $*"  >>! $LOGTO
