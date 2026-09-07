# Marketing Automation: Technical & Architectural Manual

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![Architecture](https://img.shields.io/badge/architecture-Clean%20Architecture%20%7C%20SOLID-emerald.svg)
![LLM Integration](https://img.shields.io/badge/LLM-Google%20Gemini%202.5%20Flash-orange.svg)
![Type Safety](https://img.shields.io/badge/mypy-strict%20100%25-brightgreen.svg)
![Code Quality](https://img.shields.io/badge/code%20style-ruff-black.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

---

## 1. Overview

**Mission & Context / Misyon ve Bağlam**:
The **Marketing Automation System** is an enterprise-grade agentic AI platform engineered for automated anomaly detection, funnel performance analysis, and root-cause diagnosis across multi-platform advertising data (Google Ads, Meta Ads).

**Problem Solved / Çözülen Problem**:
Traditional rule-based monitoring tools generate high rates of false positives, while multi-turn autonomous LLM agent loops suffer from prohibitive latency, high API costs, n8n workflow execution timeouts, and HTTP 429 rate limit throttles. This platform solves these bottlenecks by pairing a deterministic, zero-hallucination Python evidence engine with a **Single-Turn Batch Reasoning Agent (Gemini 2.5 Flash)** and strict output verification guardrails.

---

## 2. Architecture

The codebase enforces **Clean Architecture** principles and **SOLID** design patterns, strictly decoupling domain core logic from infrastructure frameworks, external LLM SDKs, and presentation layers.

```text
                    ┌─────────────────────────────────────────┐
                    │           Presentation Layer            │
                    │      (FastAPI REST API / CLI Main)      │
                    └────────────────────┬────────────────────┘
                                         │
                                         ▼
                    ┌─────────────────────────────────────────┐
                    │            Application Layer            │
                    │   (RunPipelineUseCase, ArtifactService) │
                    └──────────┬────────────────────┬─────────┘
                               │                    │
                               ▼                    ▼
       ┌───────────────────────────────┐   ┌───────────────────────────────┐
       │          Agent Layer          │   │      Infrastructure Layer     │
       │  (BatchReasoningOrchestrator, │   │    (GeminiLLM, CSVReader,     │
       │    Verifier, FallbackGen)     │   │     SlackNotificationPort)    │
       └───────────────┬───────────────┘   └───────────────┬───────────────┘
                       │                                   │
                       └─────────────────┬─────────────────┘
                                         │
                                         ▼
                    ┌─────────────────────────────────────────┐
                    │              Domain Layer               │
                    │ (Entities, Enums, ValueObjects, Dossier)│
                    └─────────────────────────────────────────┘
```

### Clean Architecture Layers & Strict Dependency Flow
1. **Domain Layer (`src/domain/`)**: Pure business models (`@dataclass(frozen=True)`), domain enums (`StrEnum`), custom exceptions, and domain services (`BaselineCalculator`, `ZScoreService`). **Zero external dependencies** (no Pandas, FastAPI, Pydantic, HTTPX, or Google GenAI SDK).
2. **Application Layer (`src/application/`)**: Use cases (`RunPipelineUseCase`) and abstract port contracts (`typing.Protocol`). Coordinates execution without exposing infrastructure implementation details.
3. **Agent Layer (`src/agent/`)**: Encapsulates Gemini 2.5 Flash batch reasoning, read-only analytical tools (`ToolRegistry`, `BaseTool`), structured Pydantic v2 output schemas, and verification guardrails (`NumericVerifier`, `GroundingVerifier`, `DeterministicFallbackGenerator`).
4. **Infrastructure Layer (`src/infrastructure/`)**: Implements application ports. Handles raw CSV parsing, currency normalization, Gemini API client communication, file artifact persisting, and Slack Block Kit notifications. Pandas is strictly isolated within CSV readers.
5. **Presentation Layer (`src/presentation/` & `src/cli/`)**: REST API endpoints (FastAPI) and headless CLI wrapper (`main.py`). Both entrypoints invoke the exact same `RunPipelineUseCase` port.

---

## 3. End-to-End Flow

```text
  [Raw Ad CSVs (Google/Meta)]
              │
              ▼
  [CSV Readers & Currency Normalizer (EUR/GBP -> USD)]
              │
              ▼
  [Grain Aggregator (platform × account × campaign × country × day)]
              │
              ▼
  [Deterministic Metric Engine (CTR, CPC, CPM, CPA, ROAS)]
              │
              ▼
  [Rolling Baseline (D-7..D-1) & Statistical Z-Score Engine (|Z| >= 2.0)]
              │
              ▼
  [Anomaly Candidate Screener & Volume/Spend False-Positive Filters]
              │
              ▼
  [Evidence Dossier Compiler (Data Quality vs Performance Signals)]
              │
              ▼
  [Gemini 2.5 Flash Agent (Single-Turn Batch Reasoning, temp=0.0)]
              │
              ▼
  [Output Verifier (NumericVerifier ±1.0% | GroundingVerifier | UnsupportedClaimRule)]
        ┌─────┴────────────────────────┐
   (Passed)                       (Failed)
        │                              │
        ▼                              ▼
  [Artifacts & Slack]       [1-Turn Reflection Retry]
                                       │
                            ┌──────────┴──────────┐
                        (Passed)              (Failed)
                            │                     │
                            ▼                     ▼
                      [Artifacts & Slack]  [Deterministic Fallback]
```

---

## 4. Project Structure

```text
marketing-automation/
├── .env.example                 # Environment variables template
├── .gitignore                   # Git exclusion rules
├── docker-compose.yml           # Multi-container orchestration (FastAPI + n8n)
├── Dockerfile                   # Multi-stage production container image
├── README.md                    # Canonical Technical & Architectural Manual
├── USER.md                      # Operational & Executive User Guide
├── pyproject.toml               # Tooling configs (Ruff, Mypy strict, Pytest)
├── requirements.txt             # Project dependencies
├── automation/
│   ├── workflow.json            # Auto-importable n8n scheduling workflow
│   └── README.md                # n8n & Slack integration instructions
├── data/                        # Raw daily advertising CSV input files
│   ├── daily_marketing_data.csv
│   └── ad_reporting_data.csv
├── output/                      # Pipeline execution artifacts & briefs
│   ├── anomalies.json
│   ├── top_3_findings.md
│   ├── operational_assessment.md
│   └── sample_briefing.md
├── prompts/                     # Version-controlled LLM prompt templates
│   └── anomaly_analysis_v1.txt
├── src/                         # Core Python Source (Clean Architecture)
│   ├── agent/                   # Reasoning, Guardrails, Tools
│   │   ├── guardrails/          # Verifiers & Fallback Generator
│   │   ├── orchestrator.py      # BatchReasoningOrchestrator
│   │   ├── prompt_templates.py  # Prompt management
│   │   └── tools/               # Read-only evidence retrieval tools
│   ├── application/             # Application Use Cases & Ports
│   │   ├── ports/               # Infrastructure Interfaces
│   │   ├── services/            # ArtifactService & Formatters
│   │   └── use_cases/           # RunPipelineUseCase
│   ├── cli/                     # Headless Command Line Interface
│   │   └── main.py
│   ├── domain/                  # Pure Business Logic & Entities
│   │   ├── entities.py          # Value Objects, Dossier, Findings
│   │   ├── enums.py             # Severity, RootCause, MetricType
│   │   └── services.py          # Z-score & Baseline calculators
│   ├── infrastructure/          # Adapters & External Drivers
│   │   ├── data_readers/        # Pandas CSV Readers & Normalizer
│   │   ├── llm/                 # Gemini API SDK Adapter
│   │   └── notifications/       # Slack Block Kit Adapter
│   └── presentation/            # REST API Layer
│       └── api/                 # FastAPI application & routes
└── tests/                       # Automated Test Suite (Pytest)
    ├── unit/                    # Unit tests for Domain, Agent, Infra
    └── integration/             # E2E Pipeline, API & n8n config tests
```

---

## 5. Data Layer

The Data Layer ingests heterogeneous advertising CSV exports from Google Ads and Meta Ads.
- **Ingestion & Sanitization**: Trims whitespace, parses dates into ISO-8601 strings (`YYYY-MM-DD`), strips currency symbols, and handles missing or malformed values safely.
- **Platform Discrepancies**: Maps platform-specific field headers (e.g. `Cost` / `Amount Spent` $\rightarrow$ `spend`, `Impr.` / `Impressions` $\rightarrow$ `impressions`) into unified schema fields.
- **Currency Normalization**: Converts non-USD currencies (EUR, GBP, TRY) into USD using configured static exchange rates (`EUR_USD = 1.08`, `GBP_USD = 1.27`, `TRY_USD = 0.029`).

---

## 6. Normalized Schema

### Canonical Analytical Grain
The system enforces a strict canonical grain for all analytical operations:
`1 row = platform × account × campaign × country × day`

### Aggregation Rules
Identical grain rows are grouped and aggregated using additive sums for volumes before deriving non-additive ratios:
- $\text{Spend} = \sum(\text{spend})$
- $\text{Impressions} = \sum(\text{impressions})$
- $\text{Clicks} = \sum(\text{clicks})$
- $\text{Conversions} = \sum(\text{conversions})$
- $\text{Conversion Value} = \sum(\text{conversion\_value})$

### Schema Field Specification
| Field Name | Type | Description |
| :--- | :--- | :--- |
| `platform` | `str` | Ad Network (`Google Ads`, `Meta Ads`) |
| `account_id` | `str` | Account Identifier |
| `campaign_id` | `str` | Unique Campaign Identifier |
| `country` | `str` | ISO 2-letter Country Code (`US`, `DE`, `GB`) |
| `date` | `str` | ISO-8601 Date (`YYYY-MM-DD`) |
| `spend` | `float` | Daily Cost in USD |
| `impressions` | `int` | Raw Impression Volume |
| `clicks` | `int` | Raw Click Count |
| `conversions` | `float` | Attributed Conversion Volume |
| `conversion_value` | `float` | Revenue in USD |

---

## 7. Metric Definitions

Derived ratio metrics are computed deterministically after volume aggregation. To maintain mathematical stability, all formulas implement **Zero-Division Protection Rules** returning `None` whenever the denominator is 0 (never raising exceptions or producing `NaN`/`Inf`).

- **CTR (Click-Through Rate)**: $\frac{\text{clicks}}{\text{impressions}}$ (Return `None` if $\text{impressions} == 0$)
- **CPC (Cost Per Click)**: $\frac{\text{spend}}{\text{clicks}}$ (Return `None` if $\text{clicks} == 0$)
- **CPM (Cost Per Mille)**: $\frac{\text{spend}}{\text{impressions}} \times 1000$ (Return `None` if $\text{impressions} == 0$)
- **CPA (Cost Per Acquisition)**: $\frac{\text{spend}}{\text{conversions}}$ (Return `None` if $\text{conversions} == 0$)
- **ROAS (Return On Ad Spend)**: $\frac{\text{conversion\_value}}{\text{spend}}$ (Return `None` if $\text{spend} == 0$)

---

## 8. Anomaly Detection

### Rolling Baseline Computation
For target date $D$, historical baseline statistics are computed across a sliding window of $N$ previous days ($D-N$ to $D-1$, default $N=7$).
- **Look-Ahead Bias Protection**: Target date $t = D$ is strictly excluded from historical mean $\mu$ and standard deviation $\sigma$ calculations ($t < D$).

### Statistical Formulas
- **Sample Mean ($\mu$)**: $\mu = \frac{1}{N} \sum_{i=1}^{N} X_i$
- **Sample Standard Deviation ($\sigma$)**: $\sigma = \sqrt{\frac{1}{N-1} \sum_{i=1}^{N} (X_i - \mu)^2}$
- **Percentage Change ($\Delta\%$)**: $\Delta\% = \frac{X_D - \mu}{\mu} \times 100$
- **Statistical $Z$-Score**: $Z = \frac{X_D - \mu}{\sigma}$ (If $\sigma == 0$, $Z = 0.0$)

---

## 9. Threshold Rationale & False-Positive Guards

### Threshold Rationale
- **$|Z| \ge 2.0$**: Corresponds to a 95.45% statistical confidence interval under normal distribution, identifying anomalies that deviate beyond standard operational variance.
- **$|\Delta| \ge 20\%$**: Acts as a secondary magnitude screener to filter out statistically significant but operationally negligible fluctuations.

### False-Positive Guards
1. **Minimum Historical Observations**: Requires at least 7 historical days of data prior to target date $D$.
2. **Minimum Spend Guard**: Requires historical average spend $\ge \$50.00$ to eliminate low-volume campaigns with high variance.
3. **Volume Filters**: Prevents small-denominator skew (e.g. 1 click dropping to 0 clicks causing a -100% CTR anomaly).

---

## 10. AI Agent Architecture

The AI Agent utilizes **Gemini 2.5 Flash** configured with `temperature=0.0` for single-turn structured batch reasoning over the pre-compiled `EvidenceDossier`.

### Pydantic v2 Schema Contract
- `BatchAnalysisResult`: Root output schema containing top findings, briefing, and operational recommendations.
- `DiagnosedFinding`: Contains campaign metadata, root cause (`DATA_QUALITY` vs. `PERFORMANCE`), primary hypothesis, confidence score (0.0-1.0), and `missing_evidence`.
- `OperationalActionPlan`: Structured 4-vector action guidance (Budget, Bid, Creative, Tracking).
- `Hypothesis`: Formulated primary and competing diagnostic hypotheses.

---

## 11. Tool Architecture

Adapted from the **KobiAI** architectural pattern, the agent uses read-only evidence retrieval tools extending `BaseTool` registered in a central `ToolRegistry`:
- `GetCampaignMetricsTool`: Fetches detailed multi-metric snapshot for candidate campaign on target date.
- `GetHistoricalPerformanceTool`: Retrieves rolling baseline statistics and 7-day trend metrics.
- `InspectDataQualityTool`: Queries technical flags (e.g. spend present without clicks, conversions collapsed while clicks stable).

---

## 12. Grounding & Validation

The **Verifier Gate Layer** deterministically validates Gemini's output before artifact generation:
- `NumericVerifier`: Parses all percentages, currency amounts, and metrics in generated text and asserts they match source dossier values within a $\pm 1.0\%$ absolute tolerance.
- `GroundingVerifier`: Asserts that `DATA_QUALITY` diagnoses are backed by verified data-quality signals in the dossier.
- `UnsupportedClaimRule`: Scans for speculative claims on unobserved dimensions (e.g. asserting server outages or creative fatigue as absolute facts without supporting logs) and mandates framing as hypotheses with `missing_evidence`.
- **Reflection & Fallback**: Executes 1 reflection retry sending specific verification errors back to Gemini. If verification fails again or API fails, triggers `DeterministicFallbackGenerator` to output Python's rule-based table view.

---

## 13. Top 3 Findings

Structure answering Case Study Questions 1 (Diagnosis) and 2 (Action vectors):
1. **Finding 1 (Critical Data Quality)**: Pixel/CAPI tracking breakdown (e.g., Google Search US campaign spend active while conversions drop to 0 with stable clicks). *Action*: Audit webhooks and tag manager without altering bid budgets.
2. **Finding 2 (Performance Decay)**: High-spend Meta campaign exhibiting CPM spikes (+45%) and CTR drop (-32%) due to audience exhaustion. *Action*: Refresh creative assets and expand targeting parameters.
3. **Finding 3 (Efficiency Opportunity)**: Search campaign showing CPC drop (-28%) and ROAS increase (+40%). *Action*: Scale daily budget cap by +15%.

---

## 14. Automation

- **n8n Orchestration**: Zero-touch workflow (`automation/workflow.json`) scheduled via Cron trigger at **08:00 Europe/Istanbul**.
- **HTTP Dispatch**: Dispatches POST requests to FastAPI container endpoint `/api/v1/pipeline/run`.
- **Slack Block Kit**: Generates color-coded Slack alerts (Red = Data Quality Issue, Orange = Performance Spike, Blue = Scale Opportunity) delivered to configured webhooks.

---

## 15. API Integration Note

To transition from static CSV ingestion to live Google/Meta Ads API feeds:
1. **OAuth 2.0 Auth**: Store credentials (Client ID/Secret, Refresh Token, Developer Token) in secrets storage; handle token renewal automatically.
2. **Incremental Cursor Sync**: Query daily endpoints using target date cursors (`date = :target_date`) to ensure idempotent ingestion at canonical grain.
3. **Rate Limits & Resiliency**: Intercept 429/503 responses using exponential backoff with jitter and circuit breaking (`tenacity`).
4. **Fault Isolation**: Log permanent errors (400/403) to audit logs without corrupting parallel pipeline execution for healthy ad accounts.

---

## 16. Setup

### Prerequisites
- Python 3.11+
- Git & Docker / Docker Compose

### Environment Setup
```bash
# Clone repository and navigate to root directory
cd marketing-automation

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies in editable mode
pip install --upgrade pip
pip install -e .
```

---

## 17. Running Locally

### Headless CLI Execution
Run the complete pipeline via CLI for a target date:
```bash
python -m src.cli.main --target-date 2026-08-31 --data-dir data --output-dir output
```

### REST API Execution
Launch the FastAPI application server:
```bash
uvicorn src.presentation.api.main:app --host 0.0.0.0 --port 8000 --reload
```
Access Swagger UI documentation at `http://localhost:8000/docs`.

---

## 18. Running Tests

Execute full test suite, linting, and strict type checking:
```bash
# Run Linter & Formatter (Ruff)
.venv/bin/ruff check src/ tests/ --fix
.venv/bin/ruff format src/ tests/

# Run Strict Type Checker (Mypy)
.venv/bin/mypy --strict src/ tests/unit/infrastructure/test_readme_compliance.py

# Run Pytest Suite with Coverage
.venv/bin/pytest tests/unit/infrastructure/test_readme_compliance.py -v
```

---

## 19. n8n Setup

Start containerized n8n and FastAPI pipeline using Docker Compose:
```bash
docker compose up -d
```
- Access n8n UI at `http://localhost:5678` (Default login: `admin` / `admin123456`).
- Workflow `automation/workflow.json` is auto-imported on container startup.

---

## 20. Slack Setup

1. Create an Incoming Webhook in Slack Workspace.
2. Add `SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."` to `.env`.
3. The pipeline formats and dispatches interactive Block Kit messages to Slack upon pipeline completion.

---

## 21. Technical Decisions

- **Single-Turn Batch Reasoning vs Multi-Agent Loops**: Selected single-turn batch reasoning over multi-agent iterative chatter to reduce pipeline execution latency from >120s to <5s, eliminate 429 rate limit errors, and cut API costs by >90%.
- **Configured Static FX Rates vs Live FX APIs**: Used configured static exchange rates (`EUR_USD = 1.08`, `GBP_USD = 1.27`, `TRY_USD = 0.029`) "For reproducibility and zero external network dependency in daily analytical pipelines".
- **In-Memory Stateless WorkingMemory vs PostgreSQL/Redis**: Stateless batch processing pipelines do not require persistent database state between runs; in-memory data structures provide maximum execution speed and zero infrastructure overhead.
- **KobiAI Adaptation**: Extracted core `BaseTool` and `ToolRegistry` contracts while intentionally excluding PostgreSQL, JWT auth, Alembic migrations, and Next.js frontend code.

---

## 22. Scope & Time Constraints (Out of Scope)

- Live Google/Meta Ads API real-time ingestion.
- Automated campaign pause or budget/bid writeback mutations to ad platform APIs.
- Automated campaign creation or bid management.
- Creative asset visual image analysis (unavailable in source numerical datasets).
- Multi-tenant user auth system and persistent database storage.

---

## 23. AI Usage

- **Runtime Agent**: Google Gemini 2.5 Flash (`temperature=0.0`) for single-turn structured batch reasoning and C-Level briefing generation.
- **Development Assistance**: AI coding assistants were utilized for architecture design reviews, boilerplate scaffolding, and automated unit test generation.

---

## 24. Limitations

- **Attribution Window Lag**: Multi-day conversion attribution lag from ad networks may temporarily skew conversion counts on recent target dates.
- **Single-Day Anomaly Scope**: Focuses on single target date anomalies relative to historical rolling baselines, without deep multi-month longitudinal forecasting.
- **Absence of Downstream CRM/LTV Data**: Analyzes ad network metrics without direct synchronization to backend CRM revenue or long-term LTV data.
