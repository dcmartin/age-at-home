#!/bin/bash

inotifywait -m /usr/share/hassio/homeassistant/ -e close_write |
while read path action file; do
    if [[ "$file" == "automations.yaml" ]]; then
    	echo "$file"
       	curl -X POST -H "x-ha-access: yourpass" -H "Content-Type: application/json" http://hassbian.local:8123/api/services/automation/reload
    fi
    if [[ "$file" == "groups.yaml" ]]; then
    	echo "$file"
		curl -X POST -H "x-ha-access: yourpass" -H "Content-Type: application/json" http://hassbian.local:8123/api/services/group/reload
    fi
    if [[ "$file" == "core.yaml" ]]; then
    	echo "$file"
       	curl -X POST -H "x-ha-access: yourpass" -H "Content-Type: application/json" http://hassbian.local:8123/api/services/homeassistant/reload_core_config
    fi
done
