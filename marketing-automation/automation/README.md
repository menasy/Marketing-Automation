# 🚀 Marketing Automation & Orchestration Runbook (n8n & FastAPI)

## 📌 Executive Summary & Architectural Overview

This directory contains the production-grade **n8n automation workflow** (`automation/workflow.json`) and technical architecture runbook for the agentic marketing anomaly pipeline.

### 🏗️ Architecture & Flow Diagram

```text
               +----------------------------------------+
               |        AUTOMATION TRIGGER              |
               |  - Cron Trigger: 0 8 * * *             |
               |    (Daily 08:00 AM Europe/Istanbul)    |
               |  - Manual / Webhook Trigger            |
               +-------------------+--------------------+
                                   |
                                   v
               +----------------------------------------+
               |         HTTP REQUEST NODE              |
               |  POST http://api:8000/api/v1/pipeline/run |
               |  Payload: {"target_date": "D-1", ...}  |
               |  Timeout: 120s (LLM reasoning window)  |
               +-------------------+--------------------+
                                   |
                                   v
               +----------------------------------------+
               |       IF CONDITION STATUS GATE         |
               |    Is status == 'success' / 200 OK?    |
               +---------+--------------------+---------+
                         |                    |
             [TRUE / SUCCESS]         [FALSE / FAILURE]
                         |                    |
                         v                    v
+----------------------------------+ +----------------------------------+
|  FORMAT SLACK SUCCESS BRIEFING   | |  FORMAT SLACK EMERGENCY ALERT    |
|  - Renders Slack Block Kit UI    | |  - Extracts execution error      |
|  - Formats Top 3 Findings &      | |  - Formats alert payload         |
|    Executive Narrative           | |  - Channel:                      |
|                                  | |    #marketing-alerts-critical    |
+----------------+-----------------+ +----------------+-----------------+
                 |                                    |
                 v                                    v
+----------------------------------+ +----------------------------------+
|   SEND SLACK BRIEFING DISPATCH   | |   SEND EMERGENCY ALERT DISPATCH  |
|   (POST ${SLACK_WEBHOOK_URL})    | |   (POST ${SLACK_WEBHOOK_URL})    |
+----------------------------------+ +----------------------------------+
```

---

### 🛡️ Strict Statement of Architectural Separation

To enforce Clean Architecture and SOLID design principles, **n8n operates strictly as an orchestration, scheduling, and delivery transport layer**.

- **What Python / FastAPI Engine Handles (Business & Reasoning Core):**
  - Raw ad data parsing (Google Ads & Meta Ads CSVs) and currency normalization to reporting currency (USD/TRY/EUR).
  - Deterministic statistical baseline computations (14-day sliding window, rolling Z-score statistical tests, % metric change calculation).
  - Anomaly detection guards ($|Z| \ge 2.0$, $|\Delta| \ge 20\%$, spend thresholds).
  - Structured evidence dossier compilation and multi-metric signal extraction (`ZERO_CONVERSIONS_WITH_ACTIVE_SPEND`, `COST_SPIKE_VOLUME_DROP`).
  - Gemini LLM multi-hypothesis root cause analysis (Data Quality vs Real Performance drop) and operational action planning.
  - Guardrail verification (Verifier Engine) and fallback generation.

- **What n8n Handles (Orchestration & Notification Layer ONLY):**
  - Time-based cron scheduling (`0 8 * * *` Europe/Istanbul).
  - Invoking the containerized Python pipeline endpoint via REST HTTP POST (`http://api:8000/api/v1/pipeline/run`).
  - Inspecting HTTP status codes and response health state.
  - Routing formatted Slack Block Kit payloads to marketing channels or dispatching failure alerts to `#marketing-alerts-critical`.

> **Architectural Boundary Rule:** ZERO business logic, metric calculations, anomaly filtering, or AI prompt construction exist inside n8n. If business rules change, only the core Python codebase is updated.

---

## ⚙️ Node-by-Node Specification

The n8n workflow (`automation/workflow.json`) consists of 8 interconnected nodes:

1. **Schedule Trigger (`n8n-nodes-base.scheduleTrigger`)**
   - **Cron Expression:** `0 8 * * *`
   - **Timezone:** `Europe/Istanbul`
   - **Purpose:** Automatically triggers daily execution every morning at 08:00 AM Europe/Istanbul time.

2. **Manual Trigger (`n8n-nodes-base.manualTrigger`)**
   - **Purpose:** Enables on-demand execution, manual backfill runs, and evaluator testing directly from n8n UI or CLI.

3. **HTTP Request Node (`n8n-nodes-base.httpRequest`)**
   - **HTTP Method:** `POST`
   - **Endpoint URL:** `http://api:8000/api/v1/pipeline/run`
   - **Headers:** `Content-Type: application/json`
   - **Request Payload:**
     ```json
     {
       "target_date": "={{ $now.minus({days: 1}).toFormat('yyyy-MM-dd') }}",
       "data_dir": "data",
       "output_dir": "output"
     }
     ```
   - **Timeout Policy:** 120,000 ms (120 seconds) to accommodate Gemini LLM batch reasoning, self-correction guardrails, and file output rendering.
   - **Retry Policy:** 3 retries with exponential backoff (2,000 ms delay).

4. **IF Condition (Status Gate) (`n8n-nodes-base.if`)**
   - **Condition:** `leftValue: "={{ $json.status }}"`, `operator: "equals"`, `rightValue: "success"` (or status code 200).
   - **True Branch:** Routes to success message formatter.
   - **False Branch:** Routes to emergency error alert formatter.

5. **Format Slack Success Message (`n8n-nodes-base.code`)**
   - **Purpose:** Transforms structured JSON output (`PipelineResult`) into rich Slack Block Kit layout (Header, Executive Narrative, Top 3 Findings Matrix, Operational Actions).

6. **Send Slack Briefing (`n8n-nodes-base.httpRequest`)**
   - **HTTP Method:** `POST`
   - **Target URL:** `={{ $env.SLACK_WEBHOOK_URL }}`
   - **Payload:** `{"blocks": $json.blocks}`
   - **Target Channel:** Primary Marketing Operations Channel.

7. **Format Slack Emergency Alert (`n8n-nodes-base.code`)**
   - **Purpose:** Extracts execution error trace, failed stage identifier (`failed_stage`), execution UUID, and timestamp into a critical alert block format.

8. **Send Emergency Alert to #marketing-alerts-critical (`n8n-nodes-base.httpRequest`)**
   - **HTTP Method:** `POST`
   - **Target URL:** `={{ $env.SLACK_WEBHOOK_URL }}`
   - **Payload:** `{"channel": "#marketing-alerts-critical", "blocks": $json.blocks}`
   - **Target Channel:** `#marketing-alerts-critical`

---

## 🐳 Zero-Touch Auto-Import & Deployment

`docker-compose.yml` automates the complete lifecycle of both the FastAPI backend service and the n8n automation engine without requiring manual UI configuration.

### Auto-Import Mechanism

On container startup, n8n executes the CLI import command defined in `docker-compose.yml`:
```yaml
n8n:
  image: n8nio/n8n:latest
  container_name: marketing_automation_n8n
  command: /bin/sh -c "n8n import:workflow --input=/automation/workflow.json && n8n start"
  environment:
    - GENERIC_TIMEZONE=Europe/Istanbul
    - N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true
    - SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL}
  volumes:
    - ./automation:/automation:ro
  depends_on:
    api:
      condition: service_healthy
```

### Manual Fallback Import Steps (n8n UI)

If evaluating via the n8n web interface (`http://localhost:5678`):
1. Open browser at `http://localhost:5678`.
2. Click **Workflows** -> **Import from File**.
3. Select `automation/workflow.json` from repository directory.
4. Verify all 8 nodes load correctly and click **Activate**.

---

## 🔒 Environment Variables & Security Isolation

All secrets and environment variables are strictly isolated. No credentials, tokens, or webhook URLs are hardcoded in source code or JSON workflows.

| Environment Variable | Description | Example / Location |
|---|---|---|
| `SLACK_WEBHOOK_URL` | Incoming Webhook URL for Slack alerts & briefings | Injected via `.env` file |
| `GEMINI_API_KEY` | Gemini Pro / Flash LLM API authentication key | Injected via `.env` file |
| `GENERIC_TIMEZONE` | Timezone setting for n8n cron scheduler | `Europe/Istanbul` |
| `N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS` | Enforces file permission checks for security | `true` |

---

## 🧪 Testing & Verification Runbook

Follow these step-by-step instructions to verify end-to-end functionality:

### Step 1: Verify FastAPI Service Health
```bash
curl -f http://localhost:8000/health
```
Expected Output: `{"status":"healthy","environment":"production","version":"1.0.0"}`

### Step 2: Trigger Manual Execution via CLI
```bash
python -m src.cli.main --target-date 2026-08-31 --window-days 14 --currency USD
```
Expected Output: Pipeline runs, prints execution summary, and writes artifacts to `output/`.

### Step 3: Trigger Execution via cURL / REST API
```bash
curl -X POST http://localhost:8000/api/v1/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"target_date": "2026-08-31", "data_dir": "data", "output_dir": "output"}'
```
Expected Output: `200 OK` JSON response containing `execution_id`, `status: "success"`, and paths to deliverables.

### Step 4: Verify n8n Execution History
1. Navigate to `http://localhost:5678/executions`.
2. Observe successful execution run triggered by cron or manual trigger.
3. Inspect green execution node logs and verify Slack webhook payload delivery.
