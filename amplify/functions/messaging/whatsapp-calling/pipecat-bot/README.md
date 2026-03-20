# WeCare WhatsApp AI Voice Bot

Real-time AI voice agent for WhatsApp calls using Pipecat + AWS services.

## Architecture

```
WhatsApp Call → Meta Webhook → Lambda (handler.py)
                                  ↓ (ai mode)
                              Pipecat Bot (this server)
                                  ↓
                              WebRTC SDP answer → Meta → Call connects
                                  ↓
                              Caller audio → AWS Transcribe (STT)
                                  ↓
                              Bedrock Nova Lite (LLM)
                                  ↓
                              AWS Polly Kajal (TTS) → Caller hears response
                                  ↓
                              Auto-hangup after 30s
```

## Cost

- Lightsail: $3.50/month (always-on)
- Per call (~2 min): ~$0.06 (Transcribe + Bedrock + Polly)
- Fallback: voice-note redirect if server is down ($0)

## Setup

```bash
# 1. Copy .env.example to .env and fill in values
cp .env.example .env

# 2. Install dependencies
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Run locally (use ngrok for webhook testing)
python bot.py

# 4. Deploy to Lightsail
chmod +x deploy.sh
./deploy.sh
```

## Configuration

Set `PIPECAT_BOT_URL` in Lambda env vars or SystemConfig table (key: `pipecat_bot_url`).

Both WABA numbers are supported — configure tokens in `.env`.

## Dual WABA

- WABA1: Phone `960395407161423` (+919330994400)
- WABA2: Phone `997428863451102` (+919903300044)

Each uses its own Meta token. The bot auto-selects based on `phone_number_id`.
