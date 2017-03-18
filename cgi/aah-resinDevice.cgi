#!/bin/csh -fb
setenv RESIN_AUTH_TOKEN `cat ~/.resin_auth`
curl -s -q -f -L "https://api.resin.io/v1/device" -H "Content-Type: application/json" -H "Authorization: Bearer $RESIN_AUTH_TOKEN" | jq '.d[]|{"app_id":.application.__id,"id":.id,"name":.name,"is_online":.is_online,"ip_address":.ip_address,"lastseen":.last_seen_time}'
