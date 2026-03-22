#!/bin/bash
set -euxo pipefail

dnf update -y
dnf install -y git python3 python3-pip

mkdir -p /opt
if [ ! -d /opt/unievent ]; then
  git clone ${app_repo_url} /opt/unievent
else
  cd /opt/unievent
  git pull
fi

cd /opt/unievent/app
pip3 install -r requirements.txt

cat > /etc/systemd/system/unievent.service << 'SERVICEEOF'
[Unit]
Description=UniEvent Flask App
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/unievent/app
Environment=AWS_REGION=${aws_region}
Environment=EVENTS_BUCKET=${events_bucket}
Environment=TICKETMASTER_API_KEY=${ticketmaster_api_key}
Environment=FETCH_INTERVAL_SECONDS=900
ExecStart=/usr/local/bin/gunicorn --workers 3 --bind 0.0.0.0:8000 wsgi:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload
systemctl enable unievent
systemctl start unievent
