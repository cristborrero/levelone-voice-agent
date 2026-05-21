# LevelOne Voice Agent v2 — Project Status

> Última actualización: 2026-05-21

---

## Estado general

**ALEX** (AI inbound voice agent para LevelOne UK) tiene el core implementado y en VPS.
La arquitectura completa está construida; lo que queda es hardening, integración end-to-end verificada, y features de producción.

---

## Lo que está hecho ✅

### Infraestructura y deploy
- [x] VPS Contabo — LiveKit self-hosted + systemd services (`voice-agent.service`, `voice-webhook.service`)
- [x] Deploy script (`deploy_vps.py`) — lee creds de `.env`, arma zip en runtime, rsync + reload
- [x] Telnyx SIP Trunk → LiveKit SIP → LiveKit Room (plumbing configurado)
- [x] `.env.example` completo con todos los secrets

### Agent runtime (`app/agent/`)
- [x] Worker pool (LiveKit Agents Python) — `worker.py`
- [x] `CallSession` persistida en DB al inicio de cada llamada
- [x] `AgentContext` / `CallContext` — estado de la llamada en memoria
- [x] Prompt builder (`prompt.py`)
- [x] STT factory (Deepgram nova-3)
- [x] TTS factory (Cartesia sonic-english)

### LLM Router (`app/llm/`)
- [x] OpenAI + Groq detrás de interfaz única
- [x] Config por tarea (`config/llm_config.yaml`) — task → provider/model
- [x] Persona injection por tarea (`config/agent_personas/`)
  - `summary.txt` → Sales Coach (JSON debrief)
  - `follow_up.txt` → Follow-up specialist
- [x] 15 tests unitarios pasando (`tests/unit/test_llm_router.py`)

### Orquestador de llamada (`app/core/call_orchestrator.py`)
- [x] Flujo BANT-light en 6 etapas (CallStage enum)
- [x] Flush final a DB al terminar la llamada (`_persist_session`)
  - `ended_at`, `duration_seconds`, `caller_name`, `lead_score`, `hubspot_contact_id`, `calcom_booking_uid`, `stage`

### Base de datos (`app/db/`)
- [x] Modelos SQLAlchemy async: `CallSession`, `CallMessage`
- [x] `caller_name` agregado al modelo (additive migration en `init_db`)
- [x] `get_session_factory()` — factory pattern para tests y prod

### Integraciones
- [x] **Cal.com** — slots disponibles + bookings (`app/booking/calcom.py`)
- [x] **HubSpot** — upsert contact, add note, log call activity (`app/crm/hubspot.py`)
- [x] **Resend** — email de confirmación + follow-up (`app/email/resend_client.py`)
- [x] **Telnyx webhook** — handler + verificación de firma (`app/webhook/router.py`)

### Admin API (`app/api/admin.py`)
- [x] `GET /api/livekit/rooms` — salas activas
- [x] `GET /api/livekit/workers` — workers registrados
- [x] `GET /api/stats` — stats generales desde DB real
- [x] `GET /api/config/llm` — config LLM actual
- [x] `PUT /api/config/llm/{task_name}` — cambiar provider por tarea
- [x] `GET /api/providers/status` — health de OpenAI + Groq
- [x] `POST /api/providers/{provider_name}/test` — test provider
- [x] `GET /api/config/agent` — config de ALEX
- [x] `GET /api/analytics/overview` — métricas desde DB real
- [x] `GET /api/analytics/calls` — listado de llamadas con filtros

### Tests
- [x] 30 tests pasando (0 failing)
- [x] `test_llm_router.py` — 15 tests (persona injection, load persona, routing)
- [x] `test_analytics.py` — 15 tests (overview stats, calls list, filtros, edge cases)
- [x] SQLite in-memory para analytics tests (no deps externas)

### Admin dashboard frontend
- [x] Admin dashboard frontend con diseño pro max lime/dark y iconos Lucide
- [x] Autenticación JWT en dashboard y endpoints protegidos
- [x] Sandbox de pruebas de voz (`/dashboard/playground`) integrado con livekit-client y generación automática de tokens

### Base de datos e Infraestructura
- [x] Migraciones reales y versionadas con Alembic (`alembic upgrade head` al iniciar la app)
- [x] Persistencia real de mensajes (`CallMessage`) asíncrona en el worker (`on_user_speech_committed`, `on_agent_speech_committed`)
- [x] Migración de FastAPI `on_event` a `@asynccontextmanager lifespan` (limpieza de deprecaciones)

### Integraciones y Optimización de Audio
- [x] Webhook real de Telnyx integrado con verificación Ed25519 y actualización de estado en DB (`ringing -> active -> ended`)
- [x] Corrección de audio entrecortado (choppy audio) utilizando OpenAI Realtime STT (`use_realtime=True`) con VAD en el servidor de OpenAI para evitar la sobrecarga de CPU local de Silero VAD en el VPS.

---

## Lo que falta ⏳

### Alta prioridad (bloqueante para producción)

- [ ] **Test de integración end-to-end**: llamada simulada Telnyx → LiveKit → Agent → HubSpot → Cal.com → Resend (sin mocks)

### Media prioridad

- [ ] **Outbound calls**: arquitectura prevista pero no implementada (Telnyx SIP originate)
- [ ] **HubSpot deals**: el scope `crm.objects.deals.write` no está en el plan free actual — hay un skip graceful, pero si se upgradea el plan hay que activarlo
- [ ] **Retry / circuit breaker en integraciones**: Cal.com y HubSpot tienen `tenacity` básico, pero no hay circuit breaker ni dead letter


### Baja prioridad / backlog

- [ ] **Config de ALEX desde `.env`**: `AGENT_NAME`, `AGENT_COMPANY`, `AGENT_LANGUAGE` están en Settings pero no todos están siendo inyectados en el prompt de ALEX
- [ ] **Métricas de LLM**: tokens usados, latencia, cost per call
- [ ] **Grabación de llamada**: LiveKit soporta egress/recording, no configurado
- [ ] **Multi-idioma**: arquitectura prevé `agent_language`, ALEX solo habla en-GB hoy
- [ ] **Tests para Cal.com + HubSpot + Resend**: no hay tests de integración para estas capas

---

## Archivos con cambios sin commitear

Ninguno (todo commiteado y al día al cierre de la sesión).

---

## Arquitectura en una línea

```
PSTN / Web Sandbox → Telnyx / LiveKit Client → LiveKit Room
                                                    │
                                           Agent Worker (Python)
                                     STT(OpenAI Realtime VAD) + TTS(Cartesia)
                                                    │
                                         LLM Router (OpenAI/Groq)
                                                    │
                                      Cal.com + HubSpot + Resend + DB(SQLite)
                                                    │
                                          Admin API (FastAPI /api/*)
```

---

## Próximos pasos sugeridos

1. **Probar el Sandbox de Pruebas**: El socio del negocio debe acceder a `https://agent.leveloneagency.co.uk/dashboard/playground` (o localmente), loguearse y clickear "Start Voice Session" para validar la conversación con ALEX.
2. **Validar la corrección del audio entrecortado**: Verificar que `use_realtime=True` haya resuelto los cortes de audio causados por la CPU del VPS al quitar Silero VAD del camino crítico.
3. **Prueba de integración end-to-end**: Realizar una simulación completa (PSTN/SIP -> LiveKit -> Agent -> CRM/Email).
4. **Outbound calls**: Diseñar la arquitectura/flujo para originar llamadas desde Telnyx.
