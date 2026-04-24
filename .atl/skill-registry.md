# Skill Registry — 07-voice-agent-v2

## Project Context

**Stack**: Python 3.11+, FastAPI, LiveKit Agents, Telnyx, OpenAI/Groq, Deepgram, Cartesia, HubSpot, Cal.com, SQLAlchemy async
**Domain**: Voice AI / telephony / B2B sales automation
**Agent**: ALEX — inbound/outbound voice agent for LevelOne Agency UK

---

## SDD Model Assignments

| Phase | Model | Alias |
|-------|-------|-------|
| orchestrator | claude-opus-4-7 | `opus` |
| sdd-explore | claude-sonnet-4-6 | `sonnet` |
| sdd-propose | claude-opus-4-7 | `opus` |
| sdd-spec | claude-sonnet-4-6 | `sonnet` |
| sdd-design | claude-opus-4-7 | `opus` |
| sdd-tasks | claude-sonnet-4-6 | `sonnet` |
| sdd-apply | claude-sonnet-4-6 | `sonnet` |
| sdd-verify | claude-sonnet-4-6 | `sonnet` |
| sdd-archive | claude-haiku-4-5-20251001 | `haiku` |
| default | claude-sonnet-4-6 | `sonnet` |

---

## SDD Skills (Global)

| Skill | Trigger |
|-------|---------|
| `sdd-explore` | Investigate a feature or idea before committing |
| `sdd-propose` | Create a change proposal with intent + scope |
| `sdd-spec` | Write requirements and scenarios |
| `sdd-design` | Technical design + architecture decisions |
| `sdd-tasks` | Break change into implementation checklist |
| `sdd-apply` | Implement tasks from the change |
| `sdd-verify` | Validate implementation against specs |
| `sdd-archive` | Close change, persist final state |

---

## Team Agents (Global — `~/.claude/agents/`)

### Engineering Division

| Alias | Agent File | Use When |
|-------|-----------|----------|
| `backend` | `engineering-backend-architect.md` | FastAPI endpoints, service architecture |
| `ai-engineer` | `engineering-ai-engineer.md` | LLM router, STT/TTS pipeline, agent logic |
| `devops` | `engineering-devops-automator.md` | systemd, VPS deploy, CI/CD |
| `security` | `engineering-security-engineer.md` | Webhook validation, secret handling |
| `code-review` | `engineering-code-reviewer.md` | PR reviews, code quality |
| `db` | `engineering-database-optimizer.md` | SQLAlchemy models, query optimization |
| `sre` | `engineering-sre.md` | Uptime, observability, alerts |
| `writer` | `engineering-technical-writer.md` | Docs, runbooks, API references |

### Testing Division

| Alias | Agent File | Use When |
|-------|-----------|----------|
| `api-tester` | `testing-api-tester.md` | Webhook validation, Cal.com/HubSpot API tests |
| `perf` | `testing-performance-benchmarker.md` | Latency profiling, call pipeline benchmarks |

### Product & Strategy

| Alias | Agent File | Use When |
|-------|-----------|----------|
| `pm` | `product-manager.md` | Feature prioritization, ALEX capabilities roadmap |

### Design Division

| Alias | Skill/Agent | Use When |
|-------|-----------|----------|
| `design` | `ui-ux-pro-max` (global skill) | Admin dashboard UI, config panel |

---

## User Skills (Global — `~/.claude/skills/`)

| Skill | Trigger |
|-------|---------|
| `branch-pr` | Creating pull requests |
| `issue-creation` | Creating GitHub issues |
| `judgment-day` | Adversarial parallel review |
| `skill-creator` | Creating new agent skills |
| `go-testing` | Go test patterns (not applicable here) |
| `ui-ux-pro-max` | UI/UX design work |

---

## Compact Rules

### Agent Selection

```
Task Type                        → Agent
────────────────────────────────────────────────
FastAPI endpoints / webhooks     → backend
LLM router / STT / TTS pipeline  → ai-engineer
LiveKit agent logic / ALEX brain → ai-engineer
VPS deploy / systemd services    → devops
HubSpot / Cal.com / Resend APIs  → backend
DB models / SQLAlchemy           → db
Security / webhook auth          → security
PR review                        → code-review
SLOs / health / monitoring       → sre
API testing                      → api-tester
Latency / performance            → perf
Admin dashboard UI               → design
Documentation / runbooks         → writer
Roadmap / features               → pm
```

### SDD Phase in Apply/Verify

- **Strict TDD Mode**: ENABLED
- **Test runner**: `pytest` (asyncio_mode=auto)
- **Type check**: `mypy app/` (strict)
- **Lint**: `ruff check .`
- Any new module MUST have corresponding tests in `tests/unit/` or `tests/integration/`

---

## Notes

- 167 agents available globally in `~/.claude/agents/`
- Agents are global — no local copy needed
- This registry is local to 07-voice-agent-v2
- Update when adding new integrations or changing stack
