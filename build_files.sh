#!/bin/bash

echo "=== STARTING DEPLOYMENT BUILD SCRIPT ==="

# 1. Update pip and install dependencies from your sanitized requirements file
python3 -m pip install -r requirements.txt

# 2. Compile and package all Django administration and dashboard CSS/JS assets
python3 manage.py collectstatic --noinput --clear

echo "=== BUILD SCRIPT COMPLETION SUCCESSFUL ==="