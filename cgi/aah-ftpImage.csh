#!/bin/csh -fb
setenv APP "aah"
setenv API "ftpImage"
setenv LAN "192.168.1"
setenv WWW "$LAN".32
setenv DIGITS "$LAN".30
setenv WAN "www.dcmartin.com"
setenv TMP "/var/lib/age-at-home"

if ($?DEBUG) echo `/bin/date` "$0 $$ -- START $*"  >>! $TMP/LOG

set id = "$argv[1]"
set ext = "$argv[2]"
set ipaddr = "$argv[3]"
set image = "$argv[4]"

if ($?DEBUG) echo `/bin/date` "$0 $$ -- GOT $id $ext $ipaddr $image" >>! $TMP/LOG

set ftp = "ftp://ftp:ftp@$ipaddr/$id.$ext"
/usr/bin/curl -s -q -L "$ftp" -o "/tmp/$$.$ext"
if (! -s "/tmp/$$.$ext") then
  /bin/rm -f "/tmp/$$.$ext"
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- WARNING -- FTP FAILURE ($ftp)" >>! $TMP/LOG
else
  /bin/mv -f "/tmp/$$.$ext" "$image"
endif
if (-s "$image") then
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- GET image SUCCESS ($image) ($ftp)" >>! $TMP/LOG
else
  if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- GET image FAILURE ($ftp) ($image)" >>! $TMP/LOG
endif
# optionally delete the source
if ($?FTP_DELETE) then
    if ($?DEBUG) /bin/echo `/bin/date` "$0 $$ -- deleting ($id.$ext)" >>! $TMP/LOG
    /usr/bin/curl -s -q -L "ftp://$ipaddr/" -Q "-DELE $id.$ext"
endif

done:
  if ($?DEBUG) echo `/bin/date` "$0 $$ -- FINISH $*"  >>! $TMP/LOG
