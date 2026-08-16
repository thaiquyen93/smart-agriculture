# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Scope of this file

This file governs work inside `services/agent-core/` only — the Multi-Agent AI service for SMURF (SEAL Hackathon Summer 2026, Track B: Smart Agriculture). SMURF is a 5-person hackathon monorepo; the other services (`services/ai-agent/`, `services/ingestion-stream-engine/`, `services/web-backend/`, `services/web-frontend/`, `services/database-saver/`) belong to other teammates and are developed in parallel on `main` / `ai-fuzzy-branch`.

**Stay in scope: only edit files under `services/agent-core/` and `docs/agent-core/`.** Do not modify the other services' code — coordinate through the Kafka topics, REST/SSE endpoints, and schemas defined in the contracts doc instead. If a change to another service is genuinely required (e.g. the `topic_p`/`topic_h` bug noted below), document the need rather than fixing it directly, unless the user explicitly asks you to cross that boundary.

## Current state

**M0 (Nền tảng) và M1 (Mặt phẳng tri giác) đã xong** (`docs/agent-core/07-roadmap.md`).

M0: `main.py`, `agent_core/config.py` (`Settings`, `LLM_PROFILE` switch), `agent_core/schema_lint.py` (intersection-rule linter), `agent_core/llm/` (`LLMClient`, `OpenAICompatClient`, `structured_output.py`).

M1 (mới): `agent_core/devices.py` (registry 6 thiết bị × metric × đơn vị — nguồn sự thật duy nhất cho tên/enum thiết bị). `agent_core/state/` — `store.py` (`FarmStateStore`: dict in-memory + SQLite ghi-kèm tại `data/farm_state.db`, `topic_raw` quyết định "giá trị mới nhất", `topic_p`/`topic_h` chỉ nuôi chuỗi thời gian + anomaly buffer), `freshness.py` (`classify`, `data_completeness`, `clamp_age`), `models.py`. `agent_core/kafka/` — `parser.py` (chịu lỗi, bỏ qua thiết bị lạ/field thiếu, không throw), `consumer.py` (`AgentCoreConsumer`: daemon thread, tự retry, không chặn boot nếu Redpanda chết — cùng triết lý với LLM client ở M0). `agent_core/evidence/ledger.py` (`EvidenceLedger`, in-memory, `EV-n`). `agent_core/tools/field_iot.py` — 4 tool đọc của Field IoT Agent (`get_device_snapshot`, `get_metric_series`, `get_freshness_report`, `get_anomaly_report`): hàm Python thuần, gọi trực tiếp bằng test, **chưa** bọc thành LLM tool-calling (đó là M2). `api/state.py` (`GET /api/v1/state/farm`). `api/health.py`/`main.py` đã sửa để báo `kafka_connected`/`devices_fresh` thật thay vì hardcode.

**65 test xanh** (17 M0 + 48 M1), gồm 2 test live có điều kiện (LM Studio, Redpanda — tự skip nếu không reachable). Đã verify thật 1 lần bằng Docker full stack thật (`stream-engine` + `farm_simulator.py` qua MQTT công khai + `agent-core`): 6/6 thiết bị FRESH, dữ liệu thật (kể cả 1 anomaly thật) chảy tới `GET /api/v1/state/farm`. **Không cần rebuild/redeploy Docker mỗi bước nhỏ** — `pytest` cục bộ (+ `docker compose up -d redpanda` cho live Kafka test) là đủ tín hiệu cho hầu hết công việc trong các milestone sau; chỉ làm 1 vòng Docker E2E đầy đủ khi cần xác nhận thứ gì đó mà unit test không chạm tới được (vd. network thật, clock thật).

Chưa làm (M2): Router/Coordinator/Workers/Action/Verifier/Narrative (agent roster thật, có gọi LLM), Policy Gate, bọc 4 tool Field IoT thành LLM tool-calling, `topic_agent_events`/`topic_plans`/`topic_tasks` production, SSE endpoint.

**M0.3 measured, not guessed:** qwen2.5-3b-instruct via LM Studio hit **100% structured-output success (10/10, 0 retries)** — see `tests/test_llm_client_live.py`. Re-run it after any schema/prompt change.

**M1.1 measured, not guessed:** `topic_raw` → `FarmStateStore` latency ≈0.03–1s against real Redpanda — see `tests/test_kafka_consumer_live.py -s`.

## Where to read before coding

| Need | Read |
|---|---|
| Why this architecture, agent roster, the two-plane design | `docs/agent-core/01-architecture.md` |
| Exact agent specs, full tool catalog (18 tools, ACI-style docs) | `docs/agent-core/02-agents-and-tools.md` |
| JSON Schema for every event/API, Kafka topics, REST/SSE endpoints | `docs/agent-core/03-contracts.md` |
| What other services expect from you, LM Studio setup, Gemini switch-over | `docs/agent-core/04-integration-guide.md` |
| ML model interfaces + baselines (ET0, gradient boosting, Isolation Forest) | `docs/agent-core/05-ml-interfaces.md` |
| The 3 BTC scenarios and the acceptance checklist to self-grade against | `docs/agent-core/06-scenarios-and-acceptance.md` |
| What to build next, in what order | `docs/agent-core/07-roadmap.md` |
| How to score local-vs-Gemini quality objectively | `docs/agent-core/08-eval-harness.md` |
| Why a decision was made a specific way | `docs/agent-core/adr/ADR-00{1,2,3}-*.md` |

## Non-negotiable design rules

These are architectural decisions (see the ADRs for full reasoning), not style preferences. Violating them silently reintroduces the exact failure modes this service was designed to avoid — rule-based decision-making and fabricated verification, both explicit disqualifiers per the contest brief.

1. **"LLM proposes, code decides."** The LLM classifies requests, picks which worker to consult, weighs agronomic tradeoffs, and writes the Vietnamese narrative. Code owns every numeric computation, the safety Policy Gate, tool execution, and verification. Never let an LLM call directly gate an irrigation action — it must pass through the deterministic Policy Gate (`docs/agent-core/02-agents-and-tools.md` §B.7) first.
2. **Evidence-refs only, never raw sensor numbers from the LLM.** Every agent output schema carries `evidence_refs: string[]` instead of numeric sensor fields; code resolves `evidence_id → value` at render time. See `adr/ADR-003-evidence-refs-only.md`. If you add a new agent output schema with a bare numeric field for a sensor reading, that's a bug.
3. **Schema intersection rule for `response_format` / structured-output schemas.** Any JSON Schema passed to the LLM must work on both LM Studio's GBNF constraint and Gemini's `responseSchema`: flat objects, `additionalProperties: false`, explicit `required`, closed `enum`s for variants — **no** `$ref`, `$defs`, `anyOf`, `oneOf`, `allOf`, `patternProperties`, or type unions. Full rule: `docs/agent-core/03-contracts.md` §1. This does not apply to Kafka event schemas documented for humans, only to schemas fed to the LLM.
4. **Provider switch is config, not code.** LLM access goes through a single `LLMClient` protocol with one `OpenAICompatClient` implementation; provider-specific behavior (dispatch round limits, native tool-calling on/off) is selected via `LLM_PROFILE=local|gemini`, not branched in agent code. See `adr/ADR-001-llm-provider-strategy.md`.
5. **Verification must read from the store, never from in-memory session state.** The bug this service replaces (`services/ai-agent/src/agents/farm_action_agent.py` on `main`) hardcodes `"verified": True` without reading anything back — do not reproduce that pattern. `read_back()` must hit the actual persistence layer.
6. **Bounded orchestration, not a free agent loop.** `AGENT_MAX_DISPATCH_ROUNDS` (2 for local, 4 for gemini profile) and per-agent tool menus (≤4 tools) are hard caps, not suggestions — see `adr/ADR-002-workflow-over-agent.md` for why the 3B local model requires this.

## Stack & commands

Python 3.11, FastAPI, `openai` SDK **pinned `<2.0.0`** (see Gotchas below), `kafka-python-ng`, `pydantic`, `python-dotenv`. `scikit-learn`/`pandas`/`numpy` land in M3 (`05-ml-interfaces.md`), not yet in `requirements.txt`. No agent framework (LangChain etc.) — deliberate, see `01-architecture.md` §6. Service listens on port `8100` (`AGENT_CORE_PORT` in `.env.example`).

```bash
cd services/agent-core
python -m pytest tests/ -v              # 65 tests; live-LM-Studio + live-Redpanda suites auto-skip if unreachable
python -m pytest tests/ -v -s -k live   # just the live tests, prints measured success rate / latency
docker compose up -d redpanda           # from repo root — only dependency the live Kafka test needs
python main.py                          # run locally (reads services/agent-core/.env if present)
docker compose build agent-core && docker compose up agent-core   # from repo root, full Docker E2E
curl http://localhost:8100/health
curl http://localhost:8100/api/v1/state/farm
```

## Upstream blocker — resolved

The `temp_avg` bug that blocked `topic_p`/`topic_h` (was: `04-integration-guide.md` §1.1) **was fixed by the stream-engine owner before M0 started** — confirmed via `git diff` on `processor.py`. M1's Farm State Store is not blocked; no stopgap needed.

## Gotchas learned in M0

- **Pin `openai` below 2.0.0.** `openai>=1.30.0` alone resolved to `openai==3.1.0` inside the Docker build (vs `1.109.1` tested on host) — a major-version jump with a different client surface. Verify the *container's* `pip show openai` after touching `requirements.txt`, not just the host's.
- **Set `max_retries=0` on the `OpenAI(...)` client.** Its default retry-on-failure stacks invisibly under `structured_output.py`'s own 1-retry policy, and stalled `GET /health` ~9s when the LLM was down — fights the frontend's 5s poll (`04-integration-guide.md` §3.2d).
- **Repo root is the parent of this `Smurf/` directory**, not `Smurf/` itself — `.git` lives one level up. Use `git -C ..` (or run from repo root) for accurate repo-wide status/diff from inside `Smurf/`.
- **`tests/__init__.py` is required** for `agent_core`/`api` to import cleanly under pytest's default "prepend" import mode.

## Gotchas learned in M1

- **`KafkaConsumer(...).poll()`, not the bare `for message in consumer` iterator.** The iterator only guarantees group-join/partition assignment lazily; combined with `auto_offset_reset="latest"`, a message published right after `consumer.start()` could be silently missed because assignment hadn't happened yet. Fix (`agent_core/kafka/consumer.py`): do one explicit `consumer.poll()` first to force assignment, only *then* signal "connected".
- **Device-level freshness reduction has a seeding trap.** Initializing `worst = Freshness.FRESH` before folding per-metric freshness values means a *uniformly-FRESH* device never satisfies `rank(new) > rank(worst)` (0 > 0 is false), so `worst_age`/`worst_reading` silently stay `None` even though the device is fine. Unit tests with STALE/OFFLINE fixtures didn't catch this — only hitting the real `GET /api/v1/state/farm` with live data did. Fixed by seeding `worst = None` so the first metric always sets it, and centralizing the whole reduction in `FarmStateStore.freshness_summary()` — don't re-derive this pattern anywhere else.
- **Clamp `age_seconds` at the display layer, not the classification layer.** Docker Desktop's Linux VM clock can lag the Windows host's clock by roughly a second; a message timestamped on the host can arrive with `observed_at` slightly ahead of the container's own `time.time()`, producing a confusing `age_seconds: -1`. `classify()` already handles a negative age correctly (still FRESH) — only the number shown to a human needed `agent_core.state.freshness.clamp_age()`.
- **`farm_simulator.py` (repo root) publishes to the *public* `broker.hivemq.com`, topic `hackathon/smurf/test/telemetry`.** That topic is shared across every team in this hackathon — real `SOIL_01` etc. readings from *other people's* simulators can land in `topic_raw` at any moment once `stream-engine` is running. `test_kafka_consumer_live.py` learned this the hard way (flaky failures from real concurrent traffic); fixed by asserting on a physically-impossible sentinel value (`8675.309`) instead of "some recent update" — the store is newest-wins, so a stray real message can overwrite ours between send and poll.
- **`farm_simulator.py` crashes on Windows console output** (`UnicodeEncodeError` on its emoji, cp1252 default) — run it with `PYTHONIOENCODING=utf-8` when testing manually. Not our file to fix (outside `services/agent-core/`).
- **Design decision, not a bug:** `topic_raw` alone drives "current value" (`get_device_snapshot`, `GET /api/v1/state/farm`); `topic_p`/`topic_h` only feed `get_metric_series` and the anomaly buffer. `get_anomaly_report` uses the **real rule-based** `anomalies` array `aggregators.py` already computes (`SOIL_MOISTURE_CRITICAL_LOW` etc.), labeled `model_version: "stream-rules-v1"` — honestly not an ML model, that's M3.
- **Rebuilding/redeploying the `agent-core` Docker image on every small change is not worth it.** `pytest` (+ `docker compose up -d redpanda` for the one live-Kafka test) catches almost everything; do one full Docker E2E pass only at a milestone boundary or to confirm something unit tests structurally can't see (real network, real clock skew — both gotchas above were found that way, not by unit tests).
