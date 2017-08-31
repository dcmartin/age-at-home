#!/bin/bash
APP="aah"
API="imageLast"

exec 0>&- # close stdin
exec 1>&- # close stdout
exec 2>&- # close stderr

./$APP-fetch-$API.csh $* &
