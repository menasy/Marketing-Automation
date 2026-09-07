# Marketing Automation: Gemini Agentic Anomaly Detection System

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![Architecture](https://img.shields.io/badge/architecture-Clean%20Architecture%20%7C%20SOLID-emerald.svg)
![LLM Integration](https://img.shields.io/badge/LLM-Google%20Gemini%202.5%20Flash-orange.svg)
![Type Safety](https://img.shields.io/badge/mypy-strict%20100%25-brightgreen.svg)
![Code Quality](https://img.shields.io/badge/code%20style-ruff-black.svg)
![License](https://img.shields.io/badge/license-MIT-blue.svg)

**Marketing Automation**, dijital pazarlama kanallarındaki (Google Ads, Meta Ads, TikTok Ads vb.) huni (funnel) metrik sapmalarını, performans düşüşlerini ve veri kalitesi anomalilerini tespit etmek üzere geliştirilmiş **Agentic AI & Clean Architecture** tabanlı bir otonom analiz platformudur.

Sistem, geleneksel kurallı uyarı sistemlerinin ürettiği yanlış alarmları (false positives) ve yüksek LLM maliyetlerini/zaman aşımı (timeout) sorunlarını ortadan kaldırmak için **Tek Turlu Toplu Muhakeme (Single-Turn Batch Reasoning)** mimarisini kullanır.

---

## 🏗️ 1. Temel Mimari İlkeler (Clean Architecture & SOLID)

Proje, yazılımın sürdürülebilirliğini, test edilebilirliğini ve LLM/veritabanı bağımlılıklarından izole edilmesini sağlamak amacıyla **Clean Architecture (Temiz Mimari)** ve **SOLID** ilkelerine %100 uyumlu olarak tasarlanmıştır.

```
                  ┌─────────────────────────────────────────┐
                  │           Presentation Layer            │
                  │     (FastAPI REST API / CLI Main)       │
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

### Katman Sorumlulukları ve Bağımlılık Yönü

1. **Domain Katmanı (`src/domain/`)**: Projenin çekirdeğidir. Dış dünyadan (FastAPI, Gemini, Pandas) tamamen izoledir. Saf Python `@dataclass` yapıları (`Anomaly`, `EvidenceDossier`, `DataQualitySignal`, `MetricBaseline`) içerir. İş kuralları ve veri modelleri burada tanımlanır.
2. **Application Katmanı (`src/application/`)**: Kullanım senaryolarını (`RunPipelineUseCase`) ve servis arayüzlerini (ports) yönetir. İş akışını orkestre eder.
3. **Agent Katmanı (`src/agent/`)**: Gemini tabanlı toplu muhakeme orkestratörünü (`BatchReasoningOrchestrator`), doğrulama kapılarını (`NumericVerifier`, `GroundingVerifier`) ve deterministik düşüş mekanizmasını (`DeterministicFallbackGenerator`) barındırır.
4. **Infrastructure Katmanı (`src/infrastructure/`)**: Veri okuyucuları (`CSVDataReader`), LLM adaptörleri (`GeminiLLMClient`), bildirim servisleri (`SlackNotificationAdapter`) ve dosya yazıcılarını barındırır.
5. **Presentation Katmanı (`src/presentation/` & `src/cli/`)**: Dış dünya ile etkileşim noktalarıdır (FastAPI endpoint'leri ve CLI argüman ayrıştırıcısı).

### Strict Data Boundary Rule (İzolasyon Kuralı)
- **Pandas DataFrame İzolasyonu**: Pandas, `CSVDataReader` içerisinde yalnızca dosya okuma ve ilk istatistiksel hesaplama için kullanılır. Domain katmanına hiçbir zaman DataFrame nesnesi sızmaz; tüm veriler immutable, strongly-typed `@dataclass` nesnelerine dönüştürülür.
- **Sıfır `Any` Şartı**: Tüm kod tabanı `mypy --strict` standartlarına uyar. Belirsiz tiplere ve `Any` kullanımına izin verilmez.

---

## ⚖️ 2. Python vs. LLM Sorumluluk Dağılımı

Sistemde matematiksel determinizm ile sözel muhakeme yetenekleri kesin çizgilerle ayrılmıştır:

| Sorumluluk Alanı | Modül / Katman | Açıklama & Sınırlar |
| :--- | :--- | :--- |
| **İstatistiksel Sapma & Z-Skoru** | **Python (Domain/Infra)** | Rolling 7-günlük ortalama, standart sapma, z-skoru ($\ge 2.0$) ve yüzde değişimler hesaplanır. Sıfır metinsel teşhis üretilir. |
| **Veri Kalite Sinyali (`DataQualitySignal`)** | **Python (Domain)** | 8 tam huni metriği (Impressions, Clicks, Spend, Conversions, Revenue, CTR, CPC, ROAS) arasındaki uyumsuzluklar (ör. harcama var ama gösterim 0, dönüşüm var ama gelir 0) matematiksel kurallarla sinyalleşir. |
| **Kök Neden Teşhisi** | **Agent (Gemini 2.5 Flash)** | `EvidenceDossier` verisini okuyarak sapmanın **`DATA_QUALITY`** (izleme hatası) mu yoksa **`PERFORMANCE`** (gerçek kampanya çöküşü) mü olduğunu metrik korelasyonu ile saptar. |
| **Reçeteli Aksiyon Planı** | **Agent (Gemini 2.5 Flash)** | Teşhise uygun 4 kanallı (Bütçe, Teklif/Bid, Kreatif, Tracking) somut aksiyon adımları önerir. |
| **C-Level Sabah Brifingi** | **Agent (Gemini 2.5 Flash)** | Pazarlama direktörleri ve C-Level yöneticiler için 3 maddelik stratejik özet ve risk derecelendirmesi üretir. |

---

## 🛡️ 3. Doğrulama Kapısı (Verifier Gate) & Fail-Safe Fallback

LLM halüsinasyonlarını engellemek ve sistem sürekliliğini %100 garanti altına almak için çift kademeli doğrulama ve düşüş mekanizması mevcuttur.

```text
[EvidenceDossier] ──> [Gemini LLM (Batch Reasoning)] ──> [Structured Analysis Result]
                                                                  │
                                                                  ▼
                                                       [Verifier Gate Check]
                                                      ┌───────────┴───────────┐
                                                      │                       │
                                                 (Doğrulandı)             (Hata Var)
                                                      │                       │
                                                      ▼                       ▼
                                              [Artifact & Slack]     [1-Step Reflection Loop]
                                                                              │
                                                                      ┌───────┴───────┐
                                                                      │               │
                                                                   (Başarılı)     (Yine Hatalı)
                                                                      │               │
                                                                      ▼               ▼
                                                              [Artifact & Slack]  [Deterministic Fallback]
```

1. **NumericVerifier ($\pm 1.0\%$ Tolerans)**: LLM tarafından üretilen çıktılardaki tüm sayısal değerleri, `EvidenceDossier` içerisindeki ham verilerle karşılaştırır. Sapma $\pm 1.0\%$ sınırını aşarsa doğrulama başarısız olur.
2. **GroundingVerifier**: LLM çıktısında bahsi geçen kampanya isimleri, metrik adları ve z-skorlarının kaynak dosyada bulunup bulunmadığını kontrol ederek halüsinasyon oluşumunu engeller.
3. **1-Turlu Yansıma (Reflection Retry)**: Doğrulama başarısız olursa, hatanın spesifik nedeni LLM'e geri bildirilerek 1 defalık düzeltme hakkı verilir.
4. **DeterministicFallbackGenerator**: LLM API çökmesi, rate-limit aşımı veya ikinci doğrulama hatası durumunda devreye girer. Boru hattını kesintiye uğratmadan, Python tarafından deterministik olarak üretilen kural tabanlı veri görünümünü yayınlar.

---

## ⚙️ 4. Kurulum & Yapılandırma

### Gereksinimler
- Python 3.11+
- Docker & Docker Compose (Konteynerli çalıştırma için)
- Git

### Yerel Geliştirme Ortamı Kurulumu

```bash
# 1. Depoyu klonlayın
git clone https://github.com/menasy/Marketing-Automation.git
cd Marketing-Automation/marketing-automation

# 2. Sanal ortam oluşturun ve aktif edin
python3 -m venv .venv
source .venv/bin/venv/bin/activate  # Linux/macOS

# 3. Bağımlılıkları yükleyin
pip install --upgrade pip
pip install -r requirements.txt

# 4. Ortam değişkenlerini hazırlayın
cp .env.example .env
```

### Ortam Değişkenleri (`.env`)

```env
# Gemini API Yapılandırması
GEMINI_API_KEY="your-gemini-api-key-here"
GEMINI_MODEL_NAME="gemini-2.5-flash"

# Slack Bildirim Entegrasyonu
SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

# Sistem Ayarları
LOG_LEVEL="INFO"
ENVIRONMENT="production"
OUTPUT_DIR="./output"
DATA_DIR="./data"
```

---

## 🚀 5. Kullanım Kılavuzu (Çalıştırma Modları)

### Mod A: Headless CLI Kullanımı
Komut satırından belirli bir tarih için boru hattını tetiklemek için:

```bash
# Belirli bir tarih için analiz çalıştırma
python -m src.cli.main --date 2026-09-07

# Özel veri ve çıktı dizinleri ile çalıştırma
python -m src.cli.main --date 2026-09-07 --data-dir ./custom_data --output-dir ./custom_output
```

### Mod B: FastAPI REST API Kullanımı
Web servisini başlatmak için:

```bash
# Development sunucusunu başlatın
uvicorn src.presentation.api.main:app --reload --host 0.0.0.0 --port 8000
```
- **Interactive Swagger Docs**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

#### Endpoint Örneği: `POST /api/v1/pipeline/run`
```bash
curl -X 'POST' \
  'http://localhost:8000/api/v1/pipeline/run' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "target_date": "2026-09-07",
  "force_refresh": false
}'
```

### Mod C: Zero-Touch Docker Compose & n8n Entegrasyonu
Tüm sistemi (FastAPI Servisi + n8n Otomasyon Motoru) tek komutla ayağa kaldırın:

```bash
# Konteynerleri arka planda başlatın
docker compose up -d
```

- **n8n Web UI**: `http://localhost:5678` (Varsayılan Giriş: `admin` / `admin123456`)
- **Otomatik İş Akışı**: `automation/workflow.json` dosyası konteyner ilk açıldığında otomatik olarak n8n ortamına aktarılır.
- **Zamanlayıcı (Cron Trigger)**: Her sabah **08:00 Europe/Istanbul** saatinde tetiklenerek `http://api:8000/api/v1/pipeline/run` endpoint'ine istek atar ve çıktıları ortak `./output` hacmine (volume) yazar.

---

## 📁 6. Proje Dizin Haritası

```text
marketing-automation/
├── .env.example                 # Ortam değişkenleri şablonu
├── .gitignore                   # Git hariç tutma kuralları
├── docker-compose.yml           # API ve n8n servis orkestrasyonu
├── Dockerfile                   # Üretim ortamı multi-stage Docker imajı
├── README.md                    # Teknik & Mimari dokümantasyon (Türkçe)
├── USER.md                      # Büyüme & Pazarlama Operatör Kılavuzu (Türkçe)
├── pyproject.toml               # Tool yapılandırmaları (Ruff, Mypy, Pytest)
├── requirements.txt             # Bağımlılık listesi
├── automation/
│   └── workflow.json            # n8n otomatik içe aktarılabilir cron iş akışı
├── scripts/
│   └── setup-n8n.sh             # n8n sıfır temaslı auto-import başlatma betiği
├── data/                        # Girdi CSV dosyaları
│   └── daily_marketing_data.csv # Günlük huni metrik verileri
├── output/                      # Üretilen dinamik rapor çıktıları
│   ├── anomalies.json           # Ham anomali ve z-skoru JSON çıktısı
│   ├── top_3_findings.md        # Öncelikli 3 kritik vaka incelemesi
│   └── sample_briefing.md       # C-Level yönetim özeti
├── src/                         # Temel Kaynak Kodlar (Clean Architecture)
│   ├── agent/                   # LLM & Agentik Katman
│   │   ├── guardrails/          # Verifier (Numeric/Grounding) & Fallback
│   │   ├── orchestrator.py      # BatchReasoningOrchestrator
│   │   ├── prompt_templates.py  # Gemini sistem ve kullanıcı promptları
│   │   └── tools/               # Agent araç tanımları ve kayıt defteri
│   ├── application/             # Kullanım Senaryoları & Portlar
│   │   ├── ports/               # Soyut arayüzler (LLM, Reader, Slack)
│   │   ├── services/            # ArtifactService ve rapor yazıcılar
│   │   └── use_cases/           # RunPipelineUseCase (Ana İş Akışı)
│   ├── cli/                     # Komut Satırı Arayüzü (CLI Main)
│   │   └── main.py              # Headless CLI giriş noktası
│   ├── domain/                  # İş Kuralları & Varlıklar (Entities)
│   │   ├── entities.py          # Anomaly, EvidenceDossier, AnalysisResult
│   │   ├── enums.py             # Severity, RootCause, MetricType
│   │   └── services.py          # Z-score ve Baseline hesaplama servisleri
│   ├── infrastructure/          # Dış Entegrasyonlar & Adaptörler
│   │   ├── data_readers/        # CSVDataReader (Pandas izolasyonu)
│   │   ├── llm/                 # GeminiLLMClient (Google GenAI SDK)
│   │   └── notifications/       # SlackNotificationAdapter (Dynamic Block Kit)
│   └── presentation/            # REST API (FastAPI)
│       └── api/                 # Endpoint tanımları ve FastAPI uygulaması
└── tests/                       # Test Süiti (290+ Test, >%90 Coverage)
    ├── unit/                    # Birim testleri (Domain, Application, Agent, Infra)
    └── integration/             # Entegrasyon testleri (API, CLI, Docker/n8n)
```

---

## 🧪 7. Test & Kalite Güvencesi

Projede sıfır toleranslı kalite kapıları uygulanmaktadır. Kod değişikliklerinin ardından aşağıdaki doğrulama komutlarını çalıştırın:

```bash
# 1. Ruff Linter Denetimi ve Otomatik Düzeltme
.venv/bin/ruff check src/ tests/ --fix

# 2. Ruff Kod Formatlama Kontrolü
.venv/bin/ruff format src/ tests/

# 3. Mypy Strict Tip Denetimi (Sıfır Hata Şartı)
.venv/bin/mypy --strict src/

# 4. Pytest Test Süiti ve Kapsama (Coverage) Raporu
.venv/bin/pytest tests/ --cov=src --cov-report=term-missing
```

---
*Geliştirici ekibine ve operasyon yöneticilerine yönelik detaylı kullanım senaryoları ve Vaka İnceleme Kılavuzu için lütfen [USER.md](file:///home/menasy/Desktop/Marketing-Automation/marketing-automation/USER.md) dosyasını inceleyin.*
