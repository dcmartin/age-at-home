#!/bin/csh -fb
setenv TMPDIR "/tmp"
setenv CU "https://538e7925-b7f5-478b-bf75-2f292dcf642a-bluemix:d2eae1e230e961e2f1b0c6dc25e00a643d4b8a483f48468ca66466c0b4360c5f@538e7925-b7f5-478b-bf75-2f292dcf642a-bluemix.cloudant.com"
if (! -e "changes.json") then
    curl -s -q "$CU/rough-fog/_changes?descending=true&include_docs=true" > ! changes.json
endif
if ((-e "changes.json") && (! -e "results.json")) then
    jq -c '[.results[].doc|.alchemy,.visual.image]' changes.json >! results.json
endif
set i = 1
while (1)
  set file = `jq '.['"$i"']' results.json | sed 's/"//g'`
  if ($file == "null") break
  @ i++
  set score = `jq '.['"$i"']|.text,.score' results.json`
  @ i++
  set text = `echo $score[1] | sed 's/"//g'`
  set score = `echo $score[2] | sed 's/"//g'`
  if ($text == "NO_TAGS") then
    echo "$file,$text,$score"
    curl -s -q "ftp://192.168.1.34/$file" -o "$TMPDIR/$file"
    open "$TMPDIR/$file"
  endif
end

    
