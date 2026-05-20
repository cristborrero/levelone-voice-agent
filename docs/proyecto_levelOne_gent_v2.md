# Proyecto

# LevelOne Agent

“ruta” completa para que Claude Code vaya construyendo tu agente paso a paso sin perderse.

Perfecto, vamos a convertir todo esto en un “playbook de prompts” para Claude Code, pensado para que construya el agente inbound (prioridad) sobre tu VPS Contabo con LiveKit \+ Telnyx, LLM router flexible, Cal.com y CRM, dejando la puerta abierta a outbound y más LLMs más adelante.

Te devuelvo un documento en formato markdown con TODOS los prompts, en orden. La idea es que copies cada bloque y se lo des a Claude Code, uno detrás de otro.

---

## Prompt 0 — Contexto Maestro para Claude Code (Arquitecto Senior)

Usa este prompt una sola vez al inicio, para poner a Claude Code en modo “arquitecto \+ implementador” y fijar reglas (como lo del .env.example).

Quiero que actúes como un ARQUITECTO DE SOFTWARE SENIOR \+ IMPLEMENTADOR en modo código (Claude Code) para construir un agente de voz AI inbound/outbound para mi agencia LevelOne.

Contexto general:

\- Objetivo principal ahora: llamadas INBOUND (entrantes) desde teléfono clásico (PSTN) en UK.

\- OUTBOUND (llamadas salientes a leads calificados con consentimiento) lo dejamos previsto, pero no es prioridad inmediata.

\- Infraestructura:

\- VPS Contabo (6 vCPU, 12 GB RAM) con Ubuntu \+ CyberPanel.

\- LiveKit SERVER self-hosted en ese VPS, manejando WebRTC/SIP y rooms.

\- Telefonía con Telnyx: número UK \+ SIP Trunk Telnyx ↔ LiveKit (inbound y luego outbound).

\- Agente de voz:

\- Framework de orquestación: LiveKit Agents en Python (worker pool \+ jobs por llamada).

\- Para llamadas de producción usaremos STT/TTS de terceros (Deepgram, Cartesia, Retell, etc.) pero queremos una capa de abstracción.

\- LLM:

\- Debe haber un “LLM router” configurable.

\- Debemos poder elegir distintos LLMs según la tarea:

    \- LLM principal para la conversación de la llamada (OpenAI GPT‑4o / Groq Llama / OpenRouter / Ollama).

    \- LLMs baratos/gratis para tareas auxiliares: resúmenes, clasificación, etiquetado, etc.

\- Desde un panel o archivo de configuración se debe poder asignar: “task → proveedor/modelo”.

\- Automatización:

\- Cal.com para agendar llamadas de discovery/demo (Google Meet/Zoom).

\- CRM (HubSpot o algo propio) para guardar leads, stage del pipeline y resúmenes de llamada.

\- Enviar correos / enlaces de pago / follow-ups (Resend/email API).

\- Vendedor virtual “ALEX”:

\- ALEX es el agente de voz: británico, empático, cálido, simpático, pero muy fuerte en ventas B2B digitales (servicios de LevelOne).

\- Debe seguir guiones, cualificar leads, manejar objeciones, cerrar citas y dejar todo documentado.

Reglas de trabajo importantes:

1\. ANTES de escribir una sola línea de código debes crear un archivo \`.env.example\` completo con TODOS los secrets, claves API, URLs, IDs y configuraciones que vayas a necesitar en cualquier parte del proyecto, incluso aunque no las uses todavía.

\- Si en algún momento detectas que falta una variable de entorno para algo nuevo, primero actualizas \`.env.example\` y solo después usas esa variable en el código.

2\. Todo el proyecto debe estar estructurado en una sola repo, con carpetas claras para:

\- infra/ (scripts de despliegue LiveKit/Telnyx/agent workers)

\- app/ (código del agente, LLM router, integraciones)

\- config/ (config de LLMs, flujos, prompts de sistema)

\- docs/ (README de arquitectura, etc.)

3\. Siempre que tengas dudas de requisitos funcionales o técnicos, hazme PREGUNTAS CLARAS antes de asumir cosas importantes.

4\. Siempre propone una arquitectura primero, luego pide confirmación, y solo después empiezas a implementar módulos.

5\. Usa Python 3.11+ para el backend del agente (LiveKit Agents) y mantén el código modular y testeable.

Si has entendido todo, devuelve:

\- Un resumen de alto nivel de la arquitectura que propones.

\- De 3 a 7 preguntas concretas que necesites aclarar antes de avanzar.

NO escribas aún código ni estructura de carpetas.

## Prompt 1 — Definir Arquitectura y Módulos del Proyecto

Se usa después de que Claude te devuelva sus preguntas y tú las hayas respondido.

Perfecto. Con las aclaraciones que te acabo de dar, quiero que diseñes la arquitectura detallada del proyecto y la dividas en MÓDULOS concretos.

Entregables de este paso:

1\. Diagrama lógico (en texto) de la arquitectura end-to-end para llamadas INBOUND:

\- Cliente llama → Telnyx → LiveKit SIP → LiveKit Room → Agent Worker (Python) → STT → LLM(s) → TTS → LiveKit → Telnyx → Cliente.

2\. Lista de MÓDULOS del proyecto, cada uno con:

\- Nombre (ej: \`llm_router\`, \`telephony\`, \`calendar_integration\`, \`crm_integration\`, \`call_orchestrator\`, \`alex_persona\`, etc.)

\- Responsabilidad clara.

\- Interfaces principales (qué funciones expone y qué datos recibe/devuelve).

3\. Plan de prioridades:

\- Fase 1 (MVP): inbound funcionando con flujo mínimo (saludo, recopilación de datos básicos, agendar cita, resumen simple).

\- Fase 2: mejor LLM routing por tipo de tarea, outbound calls, automatizaciones avanzadas.

4\. Propuesta de stack:

\- Versiones de Python, librerías LiveKit Agents, cliente Telnyx, HTTP client, etc.

\- Decisión sobre dónde irá el LLM router (módulo independiente en app/).

\- Base de datos inicial (puede ser Postgres o SQLite para MVP).

Quiero que devuelvas solo el diseño y el plan. NO escribas código aún.

Cuando termines este diseño, te diré que pases al siguiente paso.

## Prompt 2 — Crear Estructura de Repo \+ .env.example (Obligatorio)

Ahora crea la estructura inicial del repositorio y el archivo \`.env.example\`.

Requisitos:

1\. Estructura base de carpetas (muestra un árbol):

\- \`infra/\` (scripts de despliegue, docker-compose, etc.)

\- \`app/\`

     \- \`agents/\` (LiveKit Agents / entrypoints)

     \- \`llm/\` (router \+ clientes de LLMs)

     \- \`integrations/\` (telnyx, calcom, crm, email, etc.)

     \- \`core/\` (call orchestrator, modelos de dominio, utilidades)

     \- \`config/\` (YAML/JSON de mapeos, prompts, etc.)

\- \`tests/\`

\- \`docs/\`

2\. Crea el contenido del archivo \`.env.example\` con TODAS las variables que vamos a necesitar, incluyendo aunque no las implementes todavía:

\- LiveKit:

     \- \`LIVEKIT\_URL\`

     \- \`LIVEKIT\_API\_KEY\`

     \- \`LIVEKIT\_API\_SECRET\`

\- Telnyx:

     \- \`TELNYX\_API\_KEY\`

     \- \`TELNYX\_INBOUND\_TRUNK\_ID\`

     \- \`TELNYX\_OUTBOUND\_TRUNK\_ID\`

     \- \`TELNYX\_SIP\_USERNAME\`

     \- \`TELNYX\_SIP\_PASSWORD\`

\- LLMs:

     \- \`OPENAI\_API\_KEY\`

     \- \`GROQ\_API\_KEY\`

     \- \`OPENROUTER\_API\_KEY\`

     \- \`OLLAMA\_BASE\_URL\` (para local)

\- STT/TTS:

     \- \`DEEPGRAM\_API\_KEY\`

     \- \`CARTESIA\_API\_KEY\`

     \- (opcional, para pruebas) \`RETELL\_API\_KEY\`

\- Automatización:

     \- \`CALCOM\_API\_KEY\`

     \- \`CALCOM\_BASE\_URL\`

     \- \`CRM\_HUBSPOT\_API\_KEY\` (aunque luego podamos usar CRM propio)

     \- \`CRM\_BASE\_URL\` (para un backend propio futuro)

     \- \`RESEND\_API\_KEY\`

\- Infra y base de datos:

     \- \`DATABASE\_URL\` (Postgres o similar)

     \- \`ENVIRONMENT\` (dev/stage/prod)

3\. Usa nombres claros y añade comentarios dentro del \`.env.example\` explicando qué es cada variable y si es opcional.

4\. Genera también un \`pyproject.toml\` o \`requirements.txt\` inicial con las dependencias mínimas (solo lista, sin versión fija todavía).

IMPORTANTE:

\- Tu respuesta debe incluir todo el contenido inicial de:

\- \`.env.example\`

\- \`pyproject.toml\` o \`requirements.txt\`

\- Estructura de carpetas comentada.

\- NO necesitamos aún Docker ni scripts de despliegue, eso viene después.

##

## Prompt 3 — Diseñar el LLM Router Configurable (multiproveedor)

Ahora quiero que diseñes e implementes el módulo \`app/llm/router.py\` y la configuración asociada, sin aún integrarlo con llamadas reales.

Objetivo:  
\- Poder definir, desde un archivo de configuración, qué modelo se usa para cada “tarea” del sistema, por ejemplo:  
 \- \`call_brain\` → modelo para la conversación en tiempo real de la llamada.  
 \- \`summary\` → modelo barato/gratis para resúmenes.  
 \- \`classification\` → modelo barato para clasificar lead stage.  
 \- \`crm_note_enrichment\` → modelo mediano/barato.

Requisitos:  
1\. Crea un archivo de configuración, por ejemplo \`config/llm_profiles.yaml\` o JSON, que permita definir:  
 \`\`\`yaml  
 tasks:  
 call_brain:  
 provider: openai  
 model: gpt-4o-mini  
 summary:  
 provider: openrouter  
 model: some-free-model  
 classification:  
 provider: groq  
 model: llama-3.1-8b  
 \`\`\`  
2\. Implementa \`router.py\` con:  
 \- Una interfaz \`LLMClient\` base (clase abstracta).  
 \- Implementaciones específicas:  
 \- \`OpenAIClient\`  
 \- \`GroqClient\`  
 \- \`OpenRouterClient\`  
 \- \`OllamaClient\`  
 \- Un \`LLMRouter\` que:  
 \- Carga la config.  
 \- Expone método \`async def run(task: str, messages: list\[dict\], \*\*kwargs)\`.  
 \- En función de \`task\`, elige proveedor \+ modelo y delega la llamada al cliente adecuado.  
3\. Los clientes deben leer claves API y URLs desde \`os.environ\` (es decir, variables que ya pusiste en \`.env.example\`).  
4\. Implementa manejo de errores básico:  
 \- Si la tarea no está configurada → lanza excepción clara.  
 \- Si falla un proveedor, deja una interfaz clara para añadir fallback más adelante (por ejemplo, un \`fallback_task\`).

Devuélveme el código completo de:  
\- \`config/llm_profiles.yaml\` (ejemplo)  
\- \`app/llm/router.py\`  
\- Cualquier helper necesario (por ejemplo \`app/llm/clients.py\` si lo separas).  
Aún NO los uses en el agente de voz; solo define el router y asegúrate que se puede importar y usar desde otros módulos.

## Prompt 4 — STT/TTS Abstraído (con implementación simple inicial)

Ahora diseña una capa de abstracción para STT y TTS (como hiciste con el LLM router), pero implementa una primera versión simple que podamos usar con LiveKit Agents.

Objetivo:  
\- Tener interfaces \`SpeechToText\` y \`TextToSpeech\` en \`app/core/audio.py\`.  
\- Poder enchufar proveedores diferentes más adelante (Deepgram, Cartesia, Retell, etc.) sin tocar el resto del código.

Requisitos:  
1\. Define interfaces:  
 \- \`class SpeechToText(Protocol): async def transcribe_stream(self, audio_stream, \*\*kwargs) \-\> AsyncIterator\[str\]\`  
 \- \`class TextToSpeech(Protocol): async def synthesize_stream(self, text_stream, \*\*kwargs) \-\> AsyncIterator\[bytes\]\`  
2\. Implementa una primera versión “dummy” o minimal:  
 \- Para STT: por ahora puedes simular que devuelve el texto completo a partir de chunks (o deja placeholder documentado).  
 \- Para TTS: igual, placeholder que pueda integrarse luego con Cartesia/Deepgram.  
3\. Prepara la estructura para que, más adelante, podamos crear:  
 \- \`DeepgramSTT(SpeechToText)\`  
 \- \`CartesiaTTS(TextToSpeech)\`  
 \- \`RetellBridge\` si decidimos usar Retell como orquestador parcial.  
4\. Integra la selección de proveedor en un archivo de config, p.ej. \`config/audio.yaml\`, similar al router de LLM:  
 \`\`\`yaml  
 stt:  
 provider: deepgram  
 model: nova-3  
 tts:  
 provider: cartesia  
 model: sonic-turbo  
 \`\`\`  
5\. No necesitamos aún llamadas reales a APIs externas, pero deja las firmas y puntos de extensión claros.

Devuélveme:  
\- Código de \`app/core/audio.py\`  
\- Archivo de ejemplo \`config/audio.yaml\`  
\- Cualquier tipo/enum que consideres necesario.

## Prompt 5 — Integración LiveKit \+ Telnyx (Inbound básico “Hello World”)

Aquí ya empezamos a unir telephony y LiveKit, pero aún sin lógica de ventas.

Ahora quiero que implementes el esqueleto del agente LiveKit para llamadas INBOUND usando Telnyx.

Objetivo:  
\- Cuando alguien llame al número UK de Telnyx:  
 \- Telnyx redirige la llamada vía SIP al LiveKit server (self-hosted).  
 \- LiveKit crea una Room y despacha un Job a un Agent Worker Python.  
 \- El agent se conecta a la room, escucha y devuelve audio (por ahora puede ser algo simple como saludar y colgar).

Requisitos:  
1\. Crea un módulo \`app/agents/voice_agent.py\` que:  
 \- Exponga un \`async def entrypoint(ctx: JobContext)\` compatible con LiveKit Agents.  
 \- Se conecte a la Room (\`await ctx.connect(...)\`).  
 \- Use la capa de audio (aunque sea dummy) para montar un pipeline básico (puede ser: escuchar → responder un mensaje fijo con TTS fake).  
2\. Crea un script simple en \`infra/telephony_setup/\` con instrucciones de cómo configurar el trunk Telnyx ↔ LiveKit:  
 \- Usar LiveKit telephony API para crear inbound trunk con Telnyx (basado en los docs oficiales).  
 \- Incluir ejemplo de JSON o curl para la parte Telnyx y LiveKit.  
3\. Documenta en comentarios cómo:  
 \- Telnyx llama al FQDN de LiveKit (SIP).  
 \- LiveKit crea la Room y dispara el agent job (según sus docs de Agents).  
4\. Por ahora no integres LLMs ni STT/TTS reales: que el agent responda con un mensaje fijo tipo “Hi, this is Alex from LevelOne. This is a test call.” y luego cuelgue.

Devuélveme:  
\- Código de \`app/agents/voice_agent.py\`.  
\- Script de ejemplo o README en \`infra/telephony_setup/README.md\` con pasos concretos para Telnyx \+ LiveKit.

_(Aquí Claude se apoyará en la documentación de LiveKit Agents y Telnyx SIP trunks que ya existen.)_

## Prompt 6 — Orquestador de Llamadas \+ ALEX Persona (sin Cal.com aún)

Ahora quiero que diseñes el “cerebro conversacional” de la llamada y la personalidad de ALEX, pero sin meter todavía Cal.com ni CRM.

Objetivo:  
\- ALEX debe:  
 \- Saludar de forma cálida británica.  
 \- Identificar el motivo de la llamada.  
 \- Hacer algunas preguntas clave (nombre, negocio, qué necesitan).  
 \- Cerrar la llamada con un mini resumen verbal.

Requisitos:  
1\. Crea un módulo \`app/core/call_orchestrator.py\` con:  
 \- Una clase \`CallSession\` que mantenga el estado de la llamada (caller_id, nombre, empresa, pain points, etc.).  
 \- Métodos para:  
 \- \`on_user_utterance(text: str) \-\> AgentAction\` (decide qué hacer).  
 \- \`build_llm_messages()\` (construye el prompt para el LLM router).  
2\. Crea un módulo \`app/config/prompts.py\` o \`config/prompts/alex.yaml\` con:  
 \- El system prompt completo de ALEX:  
 \- Tono: británico, cálido, empático, directo.  
 \- Rol: vendedor senior de servicios digitales en LevelOne.  
 \- Objetivos: cualificar, entender necesidades, proponer next step (cita), no sonar robótico, no sobreprometer.  
3\. Integra el LLM router:  
 \- Para las respuestas de conversación, utiliza la tarea \`call_brain\`.  
 \- Usa el contexto de \`CallSession\` para pasar información relevante.  
4\. Modifica \`app/agents/voice_agent.py\` para:  
 \- En vez de mensaje fijo, usar \`CallSession \+ LLMRouter\` para generar la respuesta textual.  
 \- Luego pasar el texto a la capa TTS (aunque sea dummy por ahora).

Devuélveme:  
\- Código de \`call_orchestrator.py\`.  
\- Contenido del prompt de ALEX.  
\- Adaptación de \`voice_agent.py\` para usar estos componentes.

## Prompt 7 — Integrar Cal.com para Agendar

Ahora añade la integración con Cal.com para que ALEX pueda agendar llamadas de discovery/demo durante la conversación.

Objetivo:  
\- ALEX debe poder:  
 \- Detectar cuando el lead quiere una llamada/reunión.  
 \- Consultar disponibilidad en Cal.com (slots configurados).  
 \- Proponer 2–3 opciones de horario al cliente.  
 \- Confirmar una opción y crear el evento en Cal.com.  
 \- Confirmar verbalmente y dejar nota en el contexto.

Requisitos:  
1\. Crea módulo \`app/integrations/calcom.py\` con funciones:  
 \- \`async def list_availability(preferred_days: Optional\[list\[str\]\] \= None) \-\> list\[Slot\]\`  
 \- \`async def book_slot(slot: Slot, customer_name: str, customer_email: str, notes: str) \-\> BookingResult\`  
2\. Usa la API oficial de Cal.com vía HTTP:  
 \- Lee credenciales de \`CALCOM_API_KEY\` y \`CALCOM_BASE_URL\`.  
3\. En \`call_orchestrator.py\`, añade “acciones” de alto nivel:  
 \- \`AgentAction\` puede ser:  
 \- \`ASK_QUESTION\`  
 \- \`PROVIDE_INFO\`  
 \- \`OFFER_MEETING\`  
 \- \`BOOK_MEETING\`  
 \- Usa function calling vía LLM (si ya lo tienes) o lógica explícita para decidir cuándo llamar a calcom.  
4\. Haz que ALEX:  
 \- Pregunte por email si va a agendar una cita.  
 \- Llame a \`book_slot\` y luego confirme la cita al cliente.

Devuélveme:  
\- Código de \`calcom.py\`.  
\- Cambios en \`call_orchestrator.py\` y en \`voice_agent.py\` necesarios para invocar la calendar API.

## Prompt 8 — Integración CRM (HubSpot o Propio) \+ Resumen de Llamada

Ahora integra un CRM para guardar leads, estado y resumen de cada llamada.

Objetivo:  
\- Al terminar una llamada, el sistema debe:  
 \- Crear/actualizar un lead en CRM con:  
 \- Nombre, email, teléfono, empresa, servicio de interés, presupuesto aproximado.  
 \- Stage del pipeline (ej: \`new_lead\`, \`qualified\`, \`meeting_booked\`, \`proposal_sent\`).  
 \- Guardar un resumen de la llamada generado por un LLM barato (tarea \`summary\` del router).  
 \- Guardar la transcripción (aunque sea parcial al principio).

Requisitos:  
1\. Crea \`app/integrations/crm.py\` con:  
 \- Interfaz genérica \`CRMClient\` con métodos:  
 \- \`create_or_update_lead(...)\`  
 \- \`create_call_log(lead_id, summary, transcript_url_or_text, stage, metadata)\`  
 \- Implementación:  
 \- Opción 1: HubSpot (usa API key de \`CRM_HUBSPOT_API_KEY\`).  
 \- Opción 2: CRM propio (si decides usar \`DATABASE_URL\` \+ ORM simple).  
 \- Para el MVP puedes dejar placeholders con estructura clara \+ TODOs.  
2\. En \`call_orchestrator.py\`:  
 \- Añadir método \`build_call_summary()\` que:  
 \- Llama al router con tarea \`summary\` usando la transcripción completa.  
 \- Determinar el \`lead_stage\` según:  
 \- ¿Se agendó cita? → \`meeting_booked\`.  
 \- ¿Sólo interés vago? → \`new_lead\`.  
3\. En \`voice_agent.py\`:  
 \- Al terminar la llamada (callback de fin de sesión), invocar:  
 \- \`build_call_summary()\`  
 \- \`CRMClient.create_or_update_lead(...)\`  
 \- \`CRMClient.create_call_log(...)\`.

Devuélveme:  
\- Código de \`crm.py\`.  
\- Cambios necesarios en \`call_orchestrator.py\` y \`voice_agent.py\`.  
\- Ejemplo de cómo se estructura el resumen y los campos del lead para LevelOne.

## Prompt 9 — Outbound (Solo Diseño \+ Skeleton, no producción aún)

Ahora quiero que dejes preparada la base para llamadas OUTBOUND (no es prioritario pero debe quedar listo).

Objetivo:  
\- Poder tener una función que, dado un lead calificado, lance una llamada OUTBOUND desde nuestro Telnyx number usando LiveKit.

Requisitos:  
1\. Crea módulo \`app/integrations/outbound_calls.py\` con:  
 \- \`async def call_lead(phone_number: str, lead_id: str, campaign_id: Optional\[str\]) \-\> None\`  
 \- Este módulo debe:  
 \- Usar la API de LiveKit para crear un outbound SIP call (basado en docs).  
 \- Reutilizar la misma lógica de agent/room que usamos para inbound.  
2\. Solo necesitamos el skeleton \+ comentarios claros, NO lo integres aún en ningún scheduler.  
3\. Añade un pequeño README en \`docs/outbound.md\` explicando:  
 \- Flujo lógico.  
 \- Puntos a tener en cuenta para cumplimiento (consentimiento, horario de llamadas, etc.).

Devuélveme:  
\- Código de \`outbound_calls.py\`.  
\- Contenido de \`docs/outbound.md\`.

_(Aquí Claude puede apoyarse en los ejemplos oficiales de LiveKit para outbound SIP trunks.)_

## Prompt 10 — Panel de Configuración de LLMs y Proveedores (Backend)

Quiero ahora que prepares un backend simple para administrar la configuración de LLMs y proveedores desde un “panel” (aunque la UI puede ser mínima o futura).

Objetivo:

\- Poder listar y actualizar, vía HTTP API interna, las asignaciones:

\- \`task → provider → model\`

\- configuración de STT/TTS

\- toggles para activar/desactivar ciertos proveedores (ej: usar solo OpenAI en producción).

Requisitos:

1\. Crea un mini backend con FastAPI en \`app/api/config_api.py\` que exponga endpoints:

\- \`GET /config/llm-tasks\`

\- \`PUT /config/llm-tasks/{task_name}\`

\- \`GET /config/audio\`

\- \`PUT /config/audio\`

2\. El backend debe:

\- Leer/escribir sobre archivos YAML/JSON (\`config/llm_profiles.yaml\`, \`config/audio.yaml\`).

\- Validar que el provider/model existen en una lista blanca definida (OpenAI, Groq, OpenRouter, Ollama).

3\. No hace falta UI web todavía; basta con API \+ documentación de ejemplos de requests curl.

Devuélveme:

\- Código de \`config_api.py\`.

\- Cualquier cambio necesario para recargar config sin reiniciar todo el proceso (por ejemplo, recargar en el router cuando cambian los archivos).

## Prompt 11 — .env y Scripts de Arranque en VPS Contabo (sin LiveKit Server)

Ahora crea scripts y documentación para levantar el stack de la app en el VPS (sin incluir la instalación del LiveKit server en sí, que ya tengo en marcha).

Objetivo:  
\- Tener comandos claros para:  
 \- Crear \`.env\` a partir de \`.env.example\`.  
 \- Instalar dependencias.  
 \- Lanzar el agent worker y el config API backend.

Requisitos:  
1\. En \`infra/\` crea:  
 \- \`Makefile\` o script \`scripts/setup.sh\` que:  
 \- Copie \`.env.example\` → \`.env\` (sin sobrescribir si existe).  
 \- Instale dependencias (\`uv\` o \`pip\`).  
 \- \`scripts/run_agent.sh\` para lanzar el agent LiveKit (con instrucciones).  
 \- \`scripts/run_config_api.sh\` para lanzar la API de configuración.  
2\. Añade un \`docs/deploy_contabo.md\` con:  
 \- Pasos para:  
 \- Clonar repo en VPS.  
 \- Crear \`.env\`.  
 \- Exportar variables necesarias del sistema.  
 \- Lanzar agent y API usando systemd o supervisord (puedes dejar ejemplo de unit file).  
3\. No necesitas tocar la config del LiveKit server en este paso.

Devuélveme:  
\- Contenido de los scripts.  
\- Contenido de \`docs/deploy_contabo.md\`.

## Prompt 12 — Checklist de Tests Manuales (Calidad de ALEX)

Finalmente, genera un checklist de pruebas manuales para validar que ALEX funciona bien para LevelOne antes de pensar en vender el producto.

Objetivo:  
\- Tener una lista de escenarios a probar telefónicamente:  
 \- Llamada simple de información.  
 \- Llamada con intención clara de compra.  
 \- Llamada confusa (lead frío).  
 \- Llamada para soporte / no ventas.  
 \- Llamada donde el cliente pide cita y email.

Requisitos:  
1\. Crea \`docs/manual_testing_scenarios.md\` con:  
 \- Lista de casos de uso.  
 \- Qué debe hacer ALEX en cada caso.  
 \- Qué debería quedar en CRM/Cal.com después de cada caso.  
2\. Añade una sección sobre:  
 \- Cómo evaluar empatía, claridad y “sentimiento británico” del agente.  
 \- Qué métricas mínimas deberíamos observar (ratio de citas, duración media, etc.).

Devuélveme:  
\- Contenido completo de \`manual_testing_scenarios.md\`.
