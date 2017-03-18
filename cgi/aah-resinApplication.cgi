#!/bin/csh -fb
setenv RESIN_AUTH_TOKEN `cat ~/.resin_auth`
curl -s -q -f -L "https://api.resin.io/v1/application" -H "Content-Type: application/json" -H "Authorization: Bearer $RESIN_AUTH_TOKEN" | jq '.d[]|{"name":.app_name,"id":.id}'
