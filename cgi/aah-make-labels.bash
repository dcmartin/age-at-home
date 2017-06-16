#!/bin/bash
APP="aah"
API="labels"

exec 0>&- # close stdin
exec 1>&- # close stdout
exec 2>&- # close stderr
./$APP-make-$API.csh $* &
