# API Keys & Credentials You Need to Provision

Copy `.env.example` → `.env` and fill in each value below.

---

## 1. LiveKit (Self-hosted on Contabo VPS)

No external account needed — you run the server yourself.

| Variable | How to get it |
|----------|---------------|
| `LIVEKIT_URL` | Your VPS domain: `wss://your-domain.com` |
| `LIVEKIT_API_KEY` | Generate in `infra/livekit.yaml` → `keys` section |
| `LIVEKIT_API_SECRET` | Same file — the value paired with the key |
| `LIVEKIT_SIP_TRUNK_USERNAME` | From Telnyx SIP credentials (see step 2) |
| `LIVEKIT_SIP_TRUNK_PASSWORD` | Same |

**Install LiveKit on VPS:**
```bash
curl -sSL https://get.livekit.io | bash
# Copy infra/livekit.yaml to /etc/livekit.yaml
livekit-server --config /etc/livekit.yaml
```

---

## 2. Telnyx

Sign up at https://telnyx.com

| Variable | How to get it |
|----------|---------------|
| `TELNYX_API_KEY` | Portal → Auth → API Keys → Create API Key |
| `TELNYX_APP_ID` | Portal → SIP Trunking → Create SIP Connection → copy Connection ID |
| `TELNYX_PHONE_NUMBER` | Portal → Numbers → Buy a UK number (+44) |
| `TELNYX_WEBHOOK_SECRET` | Portal → SIP Connection → Webhooks → set secret |

**SIP Trunk setup:**
1. Create a SIP Connection (Credentials Auth)
2. Set the SIP domain to point to your VPS: `your-vps-ip:5060`
3. Enable call recording if needed
4. Copy SIP username/password → `LIVEKIT_SIP_TRUNK_USERNAME` / `PASSWORD`

**Webhook URL:** `https://your-domain.com/webhook/telnyx`

---

## 3. OpenAI

Sign up at https://platform.openai.com

| Variable | How to get it |
|----------|---------------|
| `OPENAI_API_KEY` | Platform → API Keys → Create new secret key |

**Required models:** `gpt-4o` (conversation) + `whisper-1` (STT)
**Billing:** Enable and add payment method — both models are pay-per-use.

---

## 4. Cartesia (TTS)

Sign up at https://cartesia.ai

| Variable | How to get it |
|----------|---------------|
| `CARTESIA_API_KEY` | Dashboard → API → Create API Key |
| `CARTESIA_VOICE_ID` | Dashboard → Voices → choose a British English voice → copy ID |

**Recommended voice:** Search for "British" in the voice library. For ALEX, look for professional male British voices.

---

## 5. Groq (Free tier)

Sign up at https://console.groq.com

| Variable | How to get it |
|----------|---------------|
| `GROQ_API_KEY` | Console → API Keys → Create API Key |

Free tier includes `llama-3.3-70b-versatile`. No billing needed for MVP.

---

## 6. HubSpot (Free CRM)

Sign up at https://app.hubspot.com (free account)

| Variable | How to get it |
|----------|---------------|
| `HUBSPOT_ACCESS_TOKEN` | Settings → Integrations → Private Apps → Create → Scopes: `crm.objects.contacts.write`, `crm.objects.deals.write`, `crm.objects.notes.write` |
| `HUBSPOT_OWNER_ID` | Settings → Users → your user → copy the numeric ID from the URL |

---

## 7. Cal.com

Sign up at https://cal.com

| Variable | How to get it |
|----------|---------------|
| `CALCOM_API_KEY` | Settings → Developer → API Keys → Add |
| `CALCOM_EVENT_TYPE_ID` | Create a "Discovery Call" event (20 min) → URL contains the ID, e.g. `/event-types/123456` → `123456` |
| `CALCOM_USERNAME` | Your Cal.com username (shown in your profile URL) |

---

## 8. Resend (Email)

Sign up at https://resend.com

| Variable | How to get it |
|----------|---------------|
| `RESEND_API_KEY` | Dashboard → API Keys → Create API Key |
| `RESEND_FROM_EMAIL` | Dashboard → Domains → Add your domain → verify DNS → use `alex@yourdomain.com` |

**Domain verification:** Add the DKIM/SPF/DMARC DNS records Resend provides to your domain registrar.

---

## Checklist

- [ ] LiveKit server running on VPS
- [ ] Telnyx SIP trunk created and pointed at VPS
- [ ] UK phone number purchased on Telnyx
- [ ] Telnyx webhook URL configured
- [ ] OpenAI API key with billing enabled
- [ ] Cartesia API key + British voice ID selected
- [ ] Groq API key (free)
- [ ] HubSpot Private App created with correct scopes
- [ ] Cal.com "Discovery Call" event type created
- [ ] Resend domain verified
- [ ] `.env` file filled in from `.env.example`
- [ ] `data/` directory writable (SQLite)
