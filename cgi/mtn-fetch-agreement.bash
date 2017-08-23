#!/bin/bash
APP="mtn"
API="agreement"

./$APP-fetch-$API.csh $* &

exec 0>&- # close stdin
exec 1>&- # close stdout
exec 2>&- # close stderr
