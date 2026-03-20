FROM safarov/freeswitch:latest

# Copy our minimal config overlay
COPY config/external-override.xml /etc/freeswitch/sip_profiles/external.xml
COPY config/whatsapp-dialplan.xml /etc/freeswitch/dialplan/public/01_whatsapp.xml
COPY config/modules-override.conf.xml /etc/freeswitch/autoload_configs/modules.conf.xml
COPY config/event_socket-override.conf.xml /etc/freeswitch/autoload_configs/event_socket.conf.xml
COPY config/switch-override.conf.xml /etc/freeswitch/autoload_configs/switch.conf.xml

# Create directories for audio exchange
RUN mkdir -p /tmp/wecare-audio /tmp/wecare-recordings
