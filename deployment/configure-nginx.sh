#!/usr/bin/env bash
set -Eeuo pipefail
: "${SAKAI_PUBLIC_FQDN:?SAKAI_PUBLIC_FQDN is required}"

sudo tee /etc/nginx/sites-available/sakai >/dev/null <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${SAKAI_PUBLIC_FQDN};
    client_max_body_size 25M;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Host \$host;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
EOF
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sfn /etc/nginx/sites-available/sakai /etc/nginx/sites-enabled/sakai
sudo nginx -t
sudo systemctl enable --now nginx
