# LevelOne Voice Agent v2 — ALEX

## Purpose

ALEX is the inbound voice AI agent for LevelOne Digital Agency (UK). It handles PSTN calls via Telnyx → LiveKit, qualifies B2B leads in real time, books discovery calls via Cal.com, and logs everything to HubSpot.

## Stack

| Layer | Tool | Role |
|-------|------|------|
| **Telephony** | Telnyx SIP Trunk | UK PSTN number, inbound/outbound |
| **Voice infra** | LiveKit (self-hosted, VPS Contabo) | WebRTC/SIP room management |
| **Agent runtime** | LiveKit Agents (Python) | Worker pool, job dispatch per call |
| **STT** | Deepgram (nova-3) via livekit-plugins | Speech-to-text |
| **TTS** | Cartesia (sonic-english) via livekit-plugins | Text-to-speech |
| **LLM** | OpenAI GPT-4o / Groq Llama (router) | Conversation brain + aux tasks |
| **CRM** | HubSpot Free | Lead upsert, deal, call note |
| **Scheduling** | Cal.com API | Discovery/demo slot booking |
| **Email** | Resend | Booking confirmation + follow-up |
| **DB** | PostgreSQL + SQLAlchemy async | CallSession, CallMessage persistence |
| **API** | FastAPI + uvicorn | Webhook (Telnyx events) + admin |
| **Deploy** | VPS Contabo + systemd | voice-agent.service + voice-webhook.service |

## Architecture

```
PSTN call → Telnyx → LiveKit SIP → LiveKit Room
                                         │
                              Agent Worker (Python)
                                    │        │
                                   STT      TTS
                                (Deepgram) (Cartesia)
                                    │        │
                              LLM Router (OpenAI/Groq)
                                         │
                          ┌──────────────┼──────────────┐
                        Cal.com       HubSpot         Resend
```

## Project Layout

```
app/
├── agent/          # LiveKit VoicePipelineAgent entrypoint, context, prompt builder
├── api/            # FastAPI admin endpoints
├── booking/        # Cal.com integration
├── core/           # CallOrchestrator, config (pydantic-settings), enums, logging
├── crm/            # HubSpot client
├── db/             # SQLAlchemy async models (CallSession, CallMessage)
├── email/          # Resend client
├── llm/            # LLMRouter — OpenAI + Groq behind single interface
├── stt/            # STT factory (Deepgram)
├── tts/            # TTS factory (Cartesia)
├── webhook/        # Telnyx webhook handler + /health
└── main.py         # FastAPI app factory
config/
├── llm_config.yaml         # Task → provider mapping
├── alex_config.yaml        # Agent persona config
└── prompts/alex_system.txt # ALEX system prompt (BANT-light, 6 stages)
infra/
├── livekit.yaml
├── voice-agent.service
└── voice-webhook.service
```

## ALEX Persona

- British, warm, empathetic, B2B sales focus
- Qualification framework: BANT-light (6 stages)
- Objectives: qualify lead → offer meeting → book via Cal.com → log to HubSpot
- Never sounds robotic; never overpromises

## Dev Setup

```bash
cp .env.example .env   # fill in API keys
uv sync                # install deps
python -m app.main     # run FastAPI + webhook
python -m app.agent.worker  # run LiveKit agent worker
```

## Deploy (VPS Contabo)

```bash
python deploy_vps.py   # rsync + systemd reload
systemctl status voice-agent voice-webhook
```

## Rules

- Always update `.env.example` before adding a new env var to code
- LLM task names live in `app/core/enums.py` (TaskType) — never hardcode strings
- New integrations go in their own subpackage under `app/`
- Never run the build after changes (systemd handles the service)
