#!/bin/bash
if [[ $(whoami) != "root" ]]; then
  echo "Run as root"
fi
curl -sL https://raw.githubusercontent.com/home-assistant/hassio-build/master/install/hassio_install | bash -s

