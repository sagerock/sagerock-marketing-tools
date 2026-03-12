#!/bin/bash
# Weekly Google Ads Review - Cron wrapper
# Runs every Monday morning via crontab

cd /home/sage/scripts/sagerock-marketing-tools
source venv/bin/activate
python weekly_ads_email.py >> /home/sage/scripts/sagerock-marketing-tools/logs/weekly_ads_email.log 2>&1
