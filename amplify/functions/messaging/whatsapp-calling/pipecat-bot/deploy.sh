#!/bin/bash
# Deploy WeCare WhatsApp Voice Bot to AWS Lightsail
# Cost: $3.50/month (512MB RAM, 2 vCPU burst)
#
# Prerequisites:
#   1. AWS CLI configured with appropriate permissions
#   2. .env file with all required variables
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh

set -e

INSTANCE_NAME="wecare-voice-bot"
REGION="us-east-1"
BLUEPRINT="amazon_linux_2023"
BUNDLE="nano_3_0"  # $3.50/mo, 512MB RAM, 2 vCPU burst

echo "=== WeCare WhatsApp Voice Bot Deployment ==="

# Check if instance exists
if aws lightsail get-instance --instance-name "$INSTANCE_NAME" --region "$REGION" 2>/dev/null; then
    echo "Instance $INSTANCE_NAME already exists. Updating..."
    # SSH and update
    PUBLIC_IP=$(aws lightsail get-instance --instance-name "$INSTANCE_NAME" --region "$REGION" \
        --query 'instance.publicIpAddress' --output text)
    echo "Instance IP: $PUBLIC_IP"
    echo "SSH in and run: cd /opt/wecare-bot && git pull && sudo systemctl restart wecare-bot"
    exit 0
fi

echo "Creating Lightsail instance: $INSTANCE_NAME ($BUNDLE)"

# User data script to set up the instance on first boot
USER_DATA=$(cat <<'USERDATA'
#!/bin/bash
set -e

# Install Python 3.11 and dependencies
dnf install -y python3.11 python3.11-pip git

# Create app directory
mkdir -p /opt/wecare-bot
cd /opt/wecare-bot

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies (will be copied later via SCP)
cat > requirements.txt << 'EOF'
pipecat-ai[aws,webrtc]==0.0.55
aiohttp>=3.9.0
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
python-dotenv>=1.0.0
boto3>=1.34.0
EOF

pip install -r requirements.txt

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

echo "Setup complete. Copy bot.py and .env, then: sudo systemctl start wecare-bot"
USERDATA
)

# Create the instance
aws lightsail create-instances \
    --instance-names "$INSTANCE_NAME" \
    --availability-zone "${REGION}a" \
    --blueprint-id "$BLUEPRINT" \
    --bundle-id "$BUNDLE" \
    --user-data "$USER_DATA" \
    --region "$REGION"

echo "Instance creating... waiting for it to be running"
aws lightsail wait instance-running --instance-name "$INSTANCE_NAME" --region "$REGION" 2>/dev/null || sleep 60

# Get public IP
PUBLIC_IP=$(aws lightsail get-instance --instance-name "$INSTANCE_NAME" --region "$REGION" \
    --query 'instance.publicIpAddress' --output text)

echo ""
echo "=== Instance Ready ==="
echo "IP: $PUBLIC_IP"
echo ""
echo "Next steps:"
echo "  1. Open port 8765: aws lightsail open-instance-public-ports --instance-name $INSTANCE_NAME --port-info fromPort=8765,toPort=8765,protocol=tcp --region $REGION"
echo "  2. SCP files: scp -i ~/.ssh/lightsail.pem bot.py .env ec2-user@$PUBLIC_IP:/opt/wecare-bot/"
echo "  3. SSH in: ssh -i ~/.ssh/lightsail.pem ec2-user@$PUBLIC_IP"
echo "  4. Start: sudo systemctl start wecare-bot"
echo "  5. Check: curl http://$PUBLIC_IP:8765/health"
echo ""
echo "For HTTPS (recommended), set up a reverse proxy with Caddy or nginx + Let's Encrypt"
echo "Or use Lightsail load balancer with free SSL ($18/mo — skip if testing)"
