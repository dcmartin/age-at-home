#!/bin/csh -fb

onintr cleanup

pip install -U sklearn scipy pandas

if ($?data == 0) set data = "houses.csv"
if ($?samplesize == 0) set samplesize = 100

# try getting from HUD
if (! -e "$data") then
  set file = "thads2013n.txt"

  if (! -e "$file") then
    echo "Trying to get HUD housing data"
    set url = "https://www.huduser.gov/portal/datasets/hads/hads2013n_ASCII.zip"
    curl -s -q -L "$url" -o "$file.zip"
    if (-e "$file.zip") then
      unzip "$file.zip"
    endif
  endif
  # check cleanliness
  if (! -e "$file:r.csv") then
    set out = "stdin_out.csv"
    head -"$samplesize" "$file" | csvclean -v
    if ($status != 0 || ! -e "$out") then
      echo "Bad data $out"
      # rm -f "$out"
      exit
    endif
    mv -f "$out" "$file:r.csv"
  endif
  set out = "$file:r.csv"
  # data of interest
  set fields = "METRO3,FMR,ROOMS,VALUE,BEDRMS,FMTBEDRMS,FMTMETRO3"
  # get a sample
  echo "Cutting $fields from $data and cleaning VALUE to non-negative"
  csvcut -c "$fields" "$out" \
    | csvgrep -c VALUE -i -m - \
    >! "$data.$$"
  if ($status != 0 || ! -e "$data.$$") then
    echo "Failed"
    rm -f "$data.$$"
    exit
  endif
  echo "Parsing FMTBEDRMS into BDRMS,BTRMS,EXTRA and cleaning BTRMS to [0-9]"
  cat "$data.$$" | sed "s/'\([0-9]*\) \([0-9]*\)[BRStudio]*\([+]*\)'/\1,\2,'\3'/" | sed 's/FMTBEDRMS/BDRMS,BTRMS,EXTRA/' | csvgrep -c BTRMS -r "[0-9]" | csvclean -v
  if ($status != 0 || ! -e "stdin_out.csv") then
    echo "Failed"
    rm -f "$data.$$" "stdin_out.csv"
    exit
  endif
  rm -f "$data.$$"
  mv -f stdin_out.csv "$data"
endif

csvstat "$data"

python convert.py

file "houses.mlmodel"

cleanup:
  rm -f "*$$*"
