#!/bin/bash
# Server en uurlijkse update draaien al via systemd. Dit haalt NU verse data op en opent het dashboard.
systemctl --user start fitness-fetch.service && echo "Data bijgewerkt."
xdg-open http://localhost:8000
