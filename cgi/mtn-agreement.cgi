#!/bin/csh -fb

# don't update statistics more than once per (in seconds)
set TTL = 1800
set SECONDS = `/bin/date "+%s"`
set DATE = `/bin/echo $SECONDS \/ $TTL \* $TTL | /usr/bin/bc`
set AGE = `/bin/echo "$SECONDS - $DATE" | /usr/bin/bc`

if ($?QUERY_STRING) then
    set ip = `/bin/echo "$QUERY_STRING" | sed 's/.*ip=\([^&]*\).*/\1/'`
    if ($ip == "$QUERY_STRING") unset ip
    set id = `/bin/echo "$QUERY_STRING" | sed 's/.*id=\([^&]*\).*/\1/'`
    if ($id == "$QUERY_STRING") unset id
    set st = `/bin/echo "$QUERY_STRING" | sed 's/.*st=\([^&]*\).*/\1/'`
    if ($st == "$QUERY_STRING") unset st
endif

if ($?ip == 0) then
  set ip = 39
else
  if ($#ip != 1 || ("$ip" != "39" && "$ip" != "40")) then
    set TTL = 0
    set output = '{"agreements":{"active":null,"archived":null},"error":"invalid ip","ip":"'"$ip"'"}'
    goto output
  endif
endif

set json = "/tmp/$0:t.$ip.$DATE.json"

if (! -s "$json") then
  set old = ( `/bin/echo "$json:r:r".*.json` )

  ./mtn-fetch-agreement.bash "$ip" "$json"

  if ($?old) then
    if ($#old) then
      @ nold = $#old
      set json = "$old[$nold]"
      @ nold--
      if ($nold) then
        /bin/rm -f "$old[1-$nold]"
      endif
    endif
  endif
endif

if (! -s "$json") then
  set TTL = 0
  set output = '{"agreements":{"active":null,"archived":null},"error":"no agreements","ip":"'"$ip"'"}'
  goto output
endif

if ($?id) then
  if ($?st == 0) set st = "active"
  set nactive = ( `/usr/local/bin/jq '.agreements.active | length' "$json"` )
  set narchive = ( `/usr/local/bin/jq '.agreements.archive | length' "$json"` )

  switch ($st)
  case "active":
    if ($id < $nactive && $id >= 0) then
      set noglob
      set output = ( `/usr/local/bin/jq '.agreements.active['"$id"']' "$json"` )
      unset noglob
      goto output
    endif
    breaksw
  case "archive":
    if ($id < $nactive && $id >= 0) then
      set noglob
      set output = `/usr/local/bin/jq '.agreements.archive['"$id"']' "$json"` )
      unset noglob
      goto output
    endif
    breaksw
  endsw
  set output = '{"agreements":{"active":null,"archived":null},"error":"invalid agreement","ip":"'"$ip"'","id":"'"$id"'","status":"'"$st"'"}'
endif

output:

@ age = $SECONDS - $DATE

/bin/echo "Age: $age"
@ refresh = $TTL - $age
# check back if using old
if ($refresh < 0) @ refresh = $TTL
/bin/echo "Refresh: $refresh"
/bin/echo "Cache-Control: max-age=$TTL"
/bin/echo "Last-Modified:" `/bin/date -r $DATE '+%a, %d %b %Y %H:%M:%S %Z'`
/bin/echo "Content-type: application/json"
/bin/echo ""
if ($?output) then
  /bin/echo "$output"
else if (-s "$json") then
  /bin/cat "$json"
else
  /bin/echo '{"error":"unknown"}'
endif
