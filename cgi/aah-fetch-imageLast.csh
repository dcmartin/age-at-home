#!/bin/tcsh -b
setenv APP "aah"
setenv API "imageLast"

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

if ($#argv == 3) then
  set db = "$argv[1]"
  set ext = "$argv[2]"
  set jpg = "$argv[3]"
else
  /bin/echo "$0:t <db> <ext> <jpg>" >>! "$LOGTO"
  exit
endif

set inprogress = ( `/bin/echo "$jpg".*` )
if ($?inprogress) then
  if ($#inprogress) then
    set pid = ( `/bin/ps auxc | /usr/bin/awk '{ print $2,$11 }' | /usr/bin/grep " $0:t" | /usr/bin/awk '{ print $1 }'`  )
    if ($#pid) then
      # /bin/echo `/bin/date` "$0 $$ -- INPROGRESS ($pid)" >>! $LOGTO
      exit
    endif
  endif
endif
       
set time = 5
set url = "http://$WWW/CGI/$APP-images.cgi?db=$db&ext=$ext&limit=1"

curl -s -q -f -k -m $time -L0 "$url" -o "$jpg.$$"
set code = $status
if ($code != 22 && $code != 28 && -s "$jpg.$$") then
  /bin/mv "$jpg.$$" "$jpg"
else
  /bin/rm -f "$jpg.$$"
  exit $code
endif
# /bin/echo `/bin/date` "$0 $$ -- COMPLETE $url ($code)" >>! $LOGTO
