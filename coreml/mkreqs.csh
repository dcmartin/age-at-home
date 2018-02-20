#!/bin/csh -fb

# uncomment for production
setenv DEBUG true
# setenv DELETE true
setenv VERBOSE "--verbose"

## HOMEBREW (http://brew.sh)
command -v brew >& /dev/null
if ($status != 0) then
  echo "$0:t $$ -- [WARN] HomeBrew not installed; trying " `bash /usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"` >& /dev/stderr
  rehash
endif

## JQ
command -v jq >& /dev/null
if ($status != 0) then
  echo "$0:t $$ -- [WARN] jq not found; trying `brew install jq`" >& /dev/stderr
  rehash
endif

## PYTHON3
command -v python3 >& /dev/null
if ($status != 0) then
  echo "$0:t $$ -- [WARN] python3 not found; trying `brew install python3`" >& /dev/stderr
  rehash
endif

## CURL
command -v curl >& /dev/null
if ($status != 0) then
  echo "$0:t $$ -- [WARN] curl not found; trying `brew install curl`" >& /dev/stderr
  rehash
endif

## CAFFE
if ($?CAFFE == 0) setenv CAFFE "$0:h/caffe"
if ($?DEBUG) echo '[ENV] CAFFE (' "$CAFFE" ')' >& /dev/stderr
if (! -e "$CAFFE") then
  echo "$0:t $$ -- [ERROR] please install BLVC Caffe in ($CAFFE); trying" `$0:h/mkcaffe.csh` >& /dev/stderr
  exit 1
endif
