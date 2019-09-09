#!/usr/bin/env bash

# this script updates the repo and dependencies, to don't forget.

git pull
pip install -U -r requirements/daemons/btc.txt
pip install -U -r requirements/daemons/ltc.txt