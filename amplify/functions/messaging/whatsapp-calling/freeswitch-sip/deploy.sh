#!/bin/bash
# Deploy FreeSWITCH + AI Bridge to Lightsail
set -e

echo "=== Setting up FreeSWITCH for WhatsApp SIP ==="

# Create directories
sudo mkdir -p /opt/freeswitch/{config,config/sip_profiles,config/dialplan,config/directory,certs,sounds,scripts}
sudo chown -R ec2-user:ec2-user /opt/freeswitch

# Copy TLS certs
echo "Setting up TLS certs..."
sudo cp /etc/letsencrypt/live/sip.wecare.digital/fullchain.pem /opt/freeswitch/certs/wss.pem
sudo cp /etc/letsencrypt/live/sip.wecare.digital/privkey.pem /opt/freeswitch/certs/wss.key
sudo bash -c 'cat /etc/letsencrypt/live/sip.wecare.digital/fullchain.pem /etc/letsencrypt/live/sip.wecare.digital/privkey.pem > /opt/freeswitch/certs/agent.pem'
sudo cp /etc/letsencrypt/live/sip.wecare.digital/chain.pem /opt/freeswitch/certs/cafile.pem
sudo chown -R ec2-user:ec2-user /opt/freeswitch/certs
chmod 644 /opt/freeswitch/certs/*

# Install ffmpeg (for Polly MP3 → WAV conversion)
if ! command -v ffmpeg &>/dev/null; then
    echo "Installing ffmpeg..."
    sudo dnf install -y ffmpeg 2>&1 | tail -3
fi

# Install Python deps for AI bridge
echo "Setting up Python venv..."
if [ ! -d /opt/freeswitch/venv ]; then
    python3 -m venv /opt/freeswitch/venv
fi
/opt/freeswitch/venv/bin/pip install --quiet boto3

# Open firewall ports (Lightsail uses security groups, but also iptables)
echo "Opening ports..."
sudo iptables -I INPUT -p tcp --dport 5061 -j ACCEPT 2>/dev/null || true
sudo iptables -I INPUT -p udp --dport 16384:32768 -j ACCEPT 2>/dev/null || true

echo "=== Starting FreeSWITCH Docker container ==="

# Stop any existing containers
docker stop wecare-freeswitch 2>/dev/null || true
docker rm wecare-freeswitch 2>/dev/null || true

# Run FreeSWITCH with host networking (simplest for SIP/RTP)
docker run -d \
    --name wecare-freeswitch \
    --network host \
    --restart unless-stopped \
    -v /opt/freeswitch/config:/etc/freeswitch \
    -v /opt/freeswitch/certs:/etc/freeswitch/certs \
    -v /opt/freeswitch/sounds:/opt/freeswitch/sounds \
    -v /opt/freeswitch/scripts:/opt/freeswitch/scripts \
    safarov/freeswitch:latest

echo "FreeSWITCH container started"
sleep 3
docker logs --tail 20 wecare-freeswitch

echo ""
echo "=== Setup complete ==="
echo "FreeSWITCH: docker logs -f wecare-freeswitch"
echo "AI Bridge:  systemctl status wecare-ai-bridge"
