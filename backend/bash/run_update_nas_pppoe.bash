#!/bin/bash
cd /myfi_repo/myfi_dev/app/
export FLASK_APP=/myfi_repo/myfi_dev/app/main.py
python3.6 -m flask update-nas-pppoe-job