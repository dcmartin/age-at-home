#!/bin/csh -fb
setenv APP "aah"
setenv API "imageLast"
setenv LAN "192.168.1"
setenv WWW "$LAN".32
setenv DIGITS "$LAN".30
setenv WAN "www.dcmartin.com"
if ($?TMP == 0) setenv TMP "/var/lib/age-at-home"

if ($#argv == 3) then
  set db = "$argv[1]"
  set ext = "$argv[2]"
  set jpg = "$argv[3]"
else
  /bin/echo "$0:t <db> <ext> <jpg>" >>! "$TMP/LOG"
  exit
endif

set inprogress = ( `/bin/echo "$jpg".*` )
if ($?inprogress) then
  if ($#inprogress) then
    set pid = ( `/bin/ps auxc | /usr/bin/awk '{ print $2,$11 }' | /usr/bin/grep " $0:t" | /usr/bin/awk '{ print $1 }'`  )
    if ($#pid) then
      # /bin/echo `/bin/date` "$0 $$ -- INPROGRESS ($pid)" >>! $TMP/LOG
      exit
    endif
  endif
endif
       
set time = 5
set url = "http://$WWW/CGI/$APP-images.cgi?db=$db&ext=$ext&limit=1"

/usr/bin/curl -s -q -f -k -m $time -L0 "$url" -o "$jpg.$$"
set code = $status
if ($code != 22 && $code != 28 && -s "$jpg.$$") then
  /bin/mv "$jpg.$$" "$jpg"
else
  /bin/rm -f "$jpg.$$"
  exit $code
endif
# /bin/echo `/bin/date` "$0 $$ -- COMPLETE $url ($code)" >>! $TMP/LOG
