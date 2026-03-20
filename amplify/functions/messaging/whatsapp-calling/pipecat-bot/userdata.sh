#!/bin/bash
set -e

# Add 1GB swap to help with pip compilation
dd if=/dev/zero of=/swapfile bs=1M count=1024
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile swap swap defaults 0 0' >> /etc/fstab

# Install Python 3.11 and dependencies
dnf install -y python3.11 python3.11-pip

# Create app directory
mkdir -p /opt/wecare-bot
cd /opt/wecare-bot

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install "pipecat-ai[aws,webrtc]==0.0.105" aiohttp fastapi "uvicorn[standard]" python-dotenv boto3 openai

# Create systemd service
cat > /etc/systemd/system/wecare-bot.service << 'EOF'
[Unit]
Description=WeCare WhatsApp Voice Bot
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/opt/wecare-bot
ExecStart=/opt/wecare-bot/venv/bin/python bot.py
Restart=always
RestartSec=5
EnvironmentFile=/opt/wecare-bot/.env

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable wecare-bot

# Signal setup complete
touch /opt/wecare-bot/.setup-complete
echo "Setup complete at $(date)" >> /opt/wecare-bot/setup.log
