#!/bin/bash
# FreeSWITCH setup for WhatsApp SIP calling on Lightsail
# Meta requires: SIP over TLS (5061), Opus codec, DTLS-SRTP, ICE

set -e

PUBLIC_IP=$(curl -s ifconfig.me)
echo "Public IP: $PUBLIC_IP"

# Create config directory
sudo mkdir -p /opt/freeswitch/config
sudo mkdir -p /opt/freeswitch/scripts
sudo mkdir -p /opt/freeswitch/sounds
sudo mkdir -p /opt/freeswitch/certs
sudo chown -R ec2-user:ec2-user /opt/freeswitch

# Copy TLS certs (FreeSWITCH needs combined format)
sudo cp /etc/letsencrypt/live/sip.wecare.digital/fullchain.pem /opt/freeswitch/certs/wss.pem
sudo cp /etc/letsencrypt/live/sip.wecare.digital/privkey.pem /opt/freeswitch/certs/wss.key
# FreeSWITCH also wants agent.pem = cert + key combined
sudo bash -c 'cat /etc/letsencrypt/live/sip.wecare.digital/fullchain.pem /etc/letsencrypt/live/sip.wecare.digital/privkey.pem > /opt/freeswitch/certs/agent.pem'
# CA bundle
sudo cp /etc/letsencrypt/live/sip.wecare.digital/chain.pem /opt/freeswitch/certs/cafile.pem
sudo chown -R ec2-user:ec2-user /opt/freeswitch/certs
sudo chmod 600 /opt/freeswitch/certs/*.pem /opt/freeswitch/certs/*.key

echo "Certs ready:"
ls -la /opt/freeswitch/certs/

echo "Setup complete!"
