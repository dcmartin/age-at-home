#!/bin/tcsh
setenv APP "aah"
setenv API "allstats"
setenv WWW "http://www.dcmartin.com/CGI"
setenv LAN "192.168.1"
if ($?TMP == 0) setenv TMP "/tmp"
# don't update statistics more than once per 15 minutes
set TTL = `echo "30 * 60" | bc`
set SECONDS = `date "+%s"`
set DATE = `echo $SECONDS \/ $TTL \* $TTL | bc`

echo "$APP-$API ($0 $$) -- $SECONDS" >>! $TMP/LOG

if (-e ~$USER/.cloudant_url) then
    echo "$APP-$API ($0 $$) - ~$USER/.cloudant_url" >>! $TMP/LOG
    set cc = ( `cat ~$USER/.cloudant_url` )
    if ($#cc > 0) set CU = $cc[1]
    if ($#cc > 1) set CN = $cc[2]
endif

if ($?CLOUDANT_URL) then
    set CU = $CLOUDANT_URL
else if ($?CN) then
    set CU = "$CN.cloudant.com"
else
    echo "$APP-$API ($0 $$) -- No Cloudant URL" >>! $TMP/LOG
    exit
endif


if ($?QUERY_STRING) then
    set DB = `echo "$QUERY_STRING" | sed "s/.*db=\([^&]*\).*/\1/"`
    set class = `echo "$QUERY_STRING" | sed "s/.*id=\([^&]*\).*/\1/"`
else
    set DB = rough-fog
    set class = person
endif
setenv QUERY_STRING "db=$DB&id=$class"

echo "$APP-$API ($0 $$) - $QUERY_STRING" >>! $TMP/LOG

echo "Content-Type: application/json"
echo "Refresh: $TTL"
set AGE = `echo "$SECONDS - $DATE" | bc`
echo "Age: $AGE"
echo "Cache-Control: max-age=$TTL"
echo -n "Last-Modified: "
date -r "$DATE"
echo ""
curl -s -L "$WWW/aah-stats.cgi?$QUERY_STRING" | \
	/usr/local/bin/jq -c '.days[].intervals[].count' | \
	sed 's/"//g' | \
	/usr/local/bin/gawk 'BEGIN { c = 0; s = 0 } { if ($1 > 0) { c++; s += $1; m = s/c; vs += ($1 - m)^2; v=vs/c} } END { sd = sqrt(v/c); printf "{\"count\":%d,\"sum\":%d,\"mean\":%f,\"stdev\":%f}\n", c, s, m, sd  }'
