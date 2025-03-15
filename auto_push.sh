#!/bin/bash
# Change directory to your repository folder
cd /home/dimitris/weather_station || exit 1

git add .
git commit -a -m "automatic push git" || true
git push heroku master
