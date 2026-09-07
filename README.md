# Pazarlama Otomasyonu: Teknik ve Mimari Kılavuz (Marketing Automation: Technical & Architectural Manual)

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![Mimari](https://img.shields.io/badge/mimari-Clean%20Architecture%20%7C%20SOLID-emerald.svg)
![Yapay Zeka](https://img.shields.io/badge/LLM-Google%20Gemini%202.5%20Flash-orange.svg)
![Tip Güvenliği](https://img.shields.io/badge/mypy-strict%20100%25-brightgreen.svg)
![Kod Kalitesi](https://img.shields.io/badge/kod%20stili-ruff-black.svg)
![Lisans](https://img.shields.io/badge/lisans-MIT-blue.svg)

---

## 1. Overview (Genel Bakış)

**Misyon ve Bağlam (Mission & Context)**:
**Pazarlama Otomasyon Sistemi**, çoklu platform reklam verileri (Google Ads, Meta Ads) genelinde otomatize anomali tespiti, dönüşüm hunisi (funnel) performans analizi ve kök neden teşhisi gerçekleştirmek üzere tasarlanmış kurumsal seviyede bir yapay zeka ajanı analitik platformudur.

**Çözülen Problem (Problem Solved)**:
Geleneksel kural tabanlı izleme araçları yüksek oranda yanlış pozitif (false-positive) üretirken, çok turlu (multi-turn) otonom LLM ajan döngüleri ise yüksek gecikme (latency), yüksek API maliyetleri, n8n iş akışı zaman aşımları ve HTTP 429 kota kısıtlamalarına yol açar. Bu platform, deterministik ve sıfır-halüsinasyon garantili bir Python kanıt motorunu **Tek Turlu Toplu Akıl Yürütme Ajanı (Gemini 2.5 Flash)** ve katı çıktı doğrulama bariyerleri (guardrails) ile birleştirerek söz konusu darboğazları tamamen ortadan kaldırır.

---

## 2. Architecture (Mimari)

Kod tabanı **Temiz Mimari (Clean Architecture)** ilkelerini ve **SOLID** tasarım prensiplerini katı bir şekilde uygular; alan (domain) mantığını altyapı çerçevelerinden, harici LLM SDK'larından ve sunum katmanlarından tamamen izole eder.

```text
                    ┌─────────────────────────────────────────┐
                    │              Sunum Katmanı              │
                    │      (FastAPI REST API / CLI Main)      │
                    └────────────────────┬────────────────────┘
                                         │
                                         ▼
                    ┌─────────────────────────────────────────┐
                    │            Uygulama Katmanı             │
                    │   (RunPipelineUseCase, ArtifactService) │
                    └──────────┬────────────────────┬─────────┘
                               │                    │
                               ▼                    ▼
        ┌───────────────────────────────┐   ┌───────────────────────────────┐
        │          Ajan Katmanı         │   │         Altyapı Katmanı       │
        │  (BatchReasoningOrchestrator, │   │    (GeminiLLM, CSVReader,     │
        │    Verifier, FallbackGen)     │   │     SlackNotificationPort)    │
        └───────────────┬───────────────┘   └───────────────┬───────────────┘
                        │                                   │
                        └─────────────────┬─────────────────┘
                                          │
                                          ▼
                    ┌─────────────────────────────────────────┐
                    │               Alan Katmanı              │
                    │ (Entities, Enums, ValueObjects, Dossier)│
                    └─────────────────────────────────────────┘
```

### Temiz Mimari Katmanları ve Bağımlılık Yönü
1. **Alan Katmanı (`src/domain/`)**: Saf iş modelleri (`@dataclass(frozen=True)`), alan enum'ları (`StrEnum`), özel istisnalar ve alan servisleri (`BaselineCalculator`, `ZScoreService`) yer alır. **Sıfır harici bağımlılık** ilkesi geçerlidir (Pandas, FastAPI, Pydantic, HTTPX veya Google GenAI SDK bulunmaz).
2. **Uygulama Katmanı (`src/application/`)**: Kullanım senaryoları (`RunPipelineUseCase`) ve soyut port arayüzleri (`typing.Protocol`) bulunur. Altyapı detaylarını dışarı sızdırmadan veri akışını orkestre eder.
3. **Ajan Katmanı (`src/agent/`)**: Gemini 2.5 Flash toplu akıl yürütme motorunu, salt-okunur analitik araçları (`ToolRegistry`, `BaseTool`), yapılandırılmış Pydantic v2 çıktı şemalarını ve doğrulama mekanizmalarını (`NumericVerifier`, `GroundingVerifier`, `DeterministicFallbackGenerator`) kapsar.
4. **Altyapı Katmanı (`src/infrastructure/`)**: Uygulama portlarını gerçekleştirir (implement eder). Ham CSV ayrıştırma, para birimi normalizasyonu, Gemini API istemcisi, dosya çıktı servisi ve Slack Block Kit bildirimlerini yönetir. Pandas kullanımı yalnızca CSV okuyucular içersinde sınırlandırılmıştır.
5. **Sunum Katmanı (`src/presentation/` & `src/cli/`)**: REST API uç noktalarını (FastAPI) ve headless CLI komut satırı arayüzünü (`main.py`) barındırır. Her iki giriş noktası da birebir aynı `RunPipelineUseCase` portunu çağırır.

---

## 3. End-to-End Flow (Uçtan Uca Akış)

```text
  [Ham Reklam CSV'leri (Google/Meta)]
              │
              ▼
  [CSV Okuyucular & Para Birimi Normalizatörü (EUR/GBP -> USD)]
              │
              ▼
  [Taneciklik Birleştiricisi (platform × account × campaign × country × day)]
              │
              ▼
  [Deterministik Metrik Motoru (CTR, CPC, CPM, CPA, ROAS)]
              │
              ▼
  [Hareketli Taban Çizgisi (D-7..D-1) & İstatistiksel Z-Skor Motoru (|Z| >= 2.0)]
              │
              ▼
  [Anomali Adayı Filtreleme & Hacim/Harcama Yanlış Pozitif Korumaları]
              │
              ▼
  [Kanıt Dosyası Derleyicisi (Veri Kalitesi vs Performans Sinyalleri)]
              │
              ▼
  [Gemini 2.5 Flash Ajanı (Tek Turlu Toplu Akıl Yürütme, temp=0.0)]
              │
              ▼
  [Çıktı Doğrulayıcı (NumericVerifier ±1.0% | GroundingVerifier | UnsupportedClaimRule)]
        ┌─────┴────────────────────────┐
   (Başarılı)                     (Başarısız)
        │                              │
        ▼                              ▼
  [Çıktılar & Slack]       [1 Turlu Yansıma Tekrarı]
                                       │
                            ┌──────────┴──────────┐
                        (Başarılı)            (Başarısız)
                            │                     │
                            ▼                     ▼
                      [Çıktılar & Slack]  [Deterministik Yedek]
```

---

## 4. Project Structure (Proje Yapısı)

```text
marketing-automation/
├── .env.example                 # Çevre değişkenleri şablonu
├── .gitignore                   # Git dışlama kuralları
├── docker-compose.yml           # Çoklu konteyner orkestrasyonu (FastAPI + n8n)
├── Dockerfile                   # Üretim ortamı multi-stage Docker imajı
├── README.md                    # Kanonik Teknik ve Mimari Kılavuz
├── USER.md                      # Operasyonel Kullanıcı ve SLA Kılavuzu
├── pyproject.toml               # Araç yapılandırmaları (Ruff, Mypy strict, Pytest)
├── requirements.txt             # Proje bağımlılıkları
├── automation/
│   ├── workflow.json            # Otomatik yüklenebilir n8n iş akışı
│   └── README.md                # n8n ve Slack entegrasyon kılavuzu
├── data/                        # Ham günlük reklam CSV girdi dosyaları
│   ├── daily_marketing_data.csv
│   └── ad_reporting_data.csv
├── output/                      # Analiz çıktıları ve raporlar
│   ├── anomalies.json
│   ├── top_3_findings.md
│   ├── operational_assessment.md
│   └── sample_briefing.md
├── prompts/                     # Sürüm kontrollü LLM istem şablonları
│   └── anomaly_analysis_v1.txt
├── src/                         # Çekirdek Python Kaynak Kodu (Temiz Mimari)
│   ├── agent/                   # Akıl Yürütme, Bariyerler, Araçlar
│   │   ├── guardrails/          # Doğrulayıcılar & Deterministik Yedek Motoru
│   │   ├── orchestrator.py      # BatchReasoningOrchestrator
│   │   ├── prompt_templates.py  # İstem yönetimi
│   │   └── tools/               # Salt-okunur kanıt erişim araçları
│   ├── application/             # Uygulama Kullanım Senaryoları ve Portlar
│   │   ├── ports/               # Altyapı Arayüzleri
│   │   ├── services/            # ArtifactService ve Biçimlendiriciler
│   │   └── use_cases/           # RunPipelineUseCase
│   ├── cli/                     # Komut Satırı Arayüzü (Headless CLI)
│   │   └── main.py
│   ├── domain/                  # Saf İş Mantığı ve Varlıklar
│   │   ├── entities.py          # Değer Nesneleri, Kanıt Dosyası, Bulgular
│   │   ├── enums.py             # Şiddet, Kök Neden, Metrik Tipi
│   │   └── services.py          # Z-skor ve Taban Çizgisi hesaplayıcıları
│   ├── infrastructure/          # Adaptörler ve Harici Sürücüler
│   │   ├── data_readers/        # Pandas CSV Okuyucuları ve Normalizatör
│   │   ├── llm/                 # Gemini API SDK Adaptörü
│   │   └── notifications/       # Slack Block Kit Adaptörü
│   └── presentation/            # REST API Katmanı
│       └── api/                 # FastAPI uygulaması ve rotaları
└── tests/                       # Otomatik Test Paketi (Pytest)
    ├── unit/                    # Alan, Ajan ve Altyapı birim testleri
    └── integration/             # Uçtan uca boru hattı, API ve n8n testleri
```

---

## 5. Data Layer (Veri Katmanı)

Veri Katmanı, Google Ads ve Meta Ads platformlarından gelen heterojen reklam CSV dışa aktarımlarını işler:
- **Veri Alımı ve Temizleme (Ingestion & Sanitization)**: Boşlukları temizler, tarihleri ISO-8601 formatında (`YYYY-MM-DD`) ayrıştırır, para birimi simgelerini kaldırır ve eksik/hatalı değerleri güvenli bir şekilde işler.
- **Platform Farklılıkları (Platform Discrepancies)**: Platforma özel alan başlıklarını (örneğin `Cost` / `Amount Spent` $\rightarrow$ `spend`, `Impr.` / `Impressions` $\rightarrow$ `impressions`) tekilleştirilmiş şema alanlarına eşler.
- **Para Birimi Normalizasyonu**: USD dışındaki para birimlerini (EUR, GBP, TRY), yapılandırılmış sabit döviz kurlarını kullanarak USD tabanına dönüştürür (`EUR_USD = 1.08`, `GBP_USD = 1.27`, `TRY_USD = 0.029`).

---

## 6. Normalized Schema (Normalize Edilmiş Şema)

### Kanonik Analitik Taneciklik (Canonical Analytical Grain)
Sistem, tüm analitik operasyonlar için katı bir kanonik taneciklik standardı uygular:
`platform × account × campaign × country × day`

### Birleştirme Kuralları (Aggregation Rules)
Aynı tanecikliğe sahip satırlar gruplanır ve Oransal (derived) metrikler hesaplanmadan önce hacim tabanlı toplanabilir değerler toplanır:
- $\text{Spend} = \sum(\text{spend})$
- $\text{Impressions} = \sum(\text{impressions})$
- $\text{Clicks} = \sum(\text{clicks})$
- $\text{Conversions} = \sum(\text{conversions})$
- $\text{Conversion Value} = \sum(\text{conversion\_value})$

### Şema Alan Özellikleri
| Alan Adı | Tip | Açıklama |
| :--- | :--- | :--- |
| `platform` | `str` | Reklam Ağı (`Google Ads`, `Meta Ads`) |
| `account_id` | `str` | Hesap Tanımlayıcısı |
| `campaign_id` | `str` | Benzersiz Kampanya Tanımlayıcısı |
| `country` | `str` | ISO 2 Harfli Ülke Kodu (`US`, `DE`, `GB`, `TR`) |
| `date` | `str` | ISO-8601 Formatında Tarih (`YYYY-MM-DD`) |
| `spend` | `float` | USD Cinsinden Günlük Harcama |
| `impressions` | `int` | Ham Gösterim Hacmi |
| `clicks` | `int` | Ham Tıklama Sayısı |
| `conversions` | `float` | Atfedilen Dönüşüm Hacmi |
| `conversion_value` | `float` | USD Cinsinden Gelir Değeri |

---

## 7. Metric Definitions (Metrik Tanımları)

Türetilmiş oran metrikleri, hacim birleştirmelerinin ardından deterministik olarak hesaplanır. Matematiksel kararlılığı korumak amacıyla tüm formüller, paydanın 0 olduğu durumlarda istisna fırlatmak ya da `NaN`/`Inf` üretmek yerine `None` dönen **Sıfıra Bölünme Koruması Kuralları** içerir:

- **CTR (Tıklama Oranı / Click-Through Rate)**: $\frac{\text{clicks}}{\text{impressions}}$ ($\text{impressions} == 0$ ise `None` döner)
- **CPC (Tıklama Başına Maliyet / Cost Per Click)**: $\frac{\text{spend}}{\text{clicks}}$ ($\text{clicks} == 0$ ise `None` döner)
- **CPM (Bin Gösterim Başına Maliyet / Cost Per Mille)**: $\frac{\text{spend}}{\text{impressions}} \times 1000$ ($\text{impressions} == 0$ ise `None` döner)
- **CPA (Edinme Başına Maliyet / Cost Per Acquisition)**: $\frac{\text{spend}}{\text{conversions}}$ ($\text{conversions} == 0$ ise `None` döner)
- **ROAS (Reklam Harcaması Getirisi / Return On Ad Spend)**: $\frac{\text{conversion\_value}}{\text{spend}}$ ($\text{spend} == 0$ ise `None` döner)

---

## 8. Anomaly Detection (Anomali Tespiti)

### Hareketli Taban Çizgisi Hesaplaması (Rolling Baseline Computation)
Hedef $D$ günü için tarihsel taban çizgisi istatistikleri, önceki $N$ günlük kayan bir pencere üzerinden hesaplanır ($D-N$ ile $D-1$ arası, varsayılan $N=7$).
- **Geleceğe Bakma Yanlılığı Koruması (Look-Ahead Bias Protection)**: Hedef $t = D$ günü, tarihsel ortalama $\mu$ ve standart sapma $\sigma$ hesaplamalarından kesin olarak hariç tutulur ($t < D$).

### İstatistiksel Formüller
- **Örneklem Ortalaması ($\mu$)**: $\mu = \frac{1}{N} \sum_{i=1}^{N} X_i$
- **Örneklem Standart Sapması ($\sigma$)**: $\sigma = \sqrt{\frac{1}{N-1} \sum_{i=1}^{N} (X_i - \mu)^2}$
- **Yüzdesel Değişim ($\Delta\%$)**: $\Delta\% = \frac{X_D - \mu}{\mu} \times 100$
- **İstatistiksel $Z$-Skoru ($Z$-Score)**: $Z = \frac{X_D - \mu}{\sigma}$ ($\sigma == 0$ ise $Z = 0.0$)

---

## 9. Threshold Rationale & False-Positive Guards (Eşik Gerekçesi ve Yanlış Pozitif Korumaları)

### Eşik Gerekçeleri
- **$|Z| \ge 2.0$**: Normal dağılım altında %95.45 istatistiksel güven aralığına karşılık gelir ve standart operasyonel sapmaların ötesindeki gerçek anomalileri tespit eder.
- **$|\Delta| \ge 20\%$**: İstatistiksel olarak anlamlı fakat operasyonel açıdan önemsiz küçük dalgalanmaları elemek için ikincil büyüklük filtresi görevi görür.

### Yanlış Pozitif Korumaları
1. **Minimum Tarihsel Gözlem**: Hedef $D$ gününden önce en az 7 günlük tarihsel veri bulunmasını şart koşar.
2. **Minimum Harcama Eşiği**: Yüksek varyanslı düşük hacimli kampanyaları elemek için tarihsel ortalama harcamanın $\ge \$50.00$ olmasını gerektirir.
3. **Hacim Filtreleri**: Düşük payda sapmalarını engeller (örneğin 1 tıklamanın 0'a düşerek %-100 CTR anomalisi üretmesini önler).

---

## 10. AI Agent Architecture (Yapay Zeka Ajan Mimarisi)

Yapay Zeka Ajanı, önceden derlenmiş `EvidenceDossier` (Kanıt Dosyası) üzerinde tek turlu yapılandırılmış akıl yürütme yürütmek amacıyla `temperature=0.0` ayarıyla **Gemini 2.5 Flash** modelini kullanır.

### Pydantic v2 Şema Sözleşmesi
- `BatchAnalysisResult`: En önemli bulguları, özet anlatıyı ve operasyonel önerileri içeren kök çıktı şeması.
- `DiagnosedFinding`: Kampanya meta verilerini, kök nedeni (`DATA_QUALITY` vs. `PERFORMANCE`), birincil hipotezi, güven skorunu (0.0-1.0) ve eksik kanıtları (`missing_evidence`) içerir.
- `OperationalActionPlan`: 4 boyutlu yapılandırılmış aksiyon rehberliği (Bütçe, Teklif, Kreatif, Takip).
- `Hypothesis`: Oluşturulan birincil ve rekabet eden alternatif teşhis hipotezleri.

---

## 11. Tool Architecture (Araç Mimarisi)

**KobiAI** mimari modelinden uyarlanan ajan, `BaseTool` sınıfını genişleten ve merkezi bir `ToolRegistry` içerisine kaydedilen salt-okunur kanıt erişim araçlarını kullanır:
- `GetCampaignMetricsTool`: Hedef günde aday kampanyanın çoklu metrik anlık görüntüsünü getirir.
- `GetHistoricalPerformanceTool`: Kayan taban çizgisi istatistiklerini ve 7 günlük trend metriklerini alır.
- `InspectDataQualityTool`: Teknik sinyalleri sorgular (örneğin tıklama olmadan harcama varlığı, tıklamalar sabitken dönüşümlerin sıfırlanması).

---

## 12. Grounding & Validation (Doğrulama ve Gerçeklik Kapısı)

**Doğrulayıcı Bariyer Katmanı (Verifier Gate Layer)**, dosya üretilmeden önce Gemini çıktısını deterministik olarak denetler:
- `NumericVerifier`: Üretilen metindeki tüm yüzdeleri, para miktarlarını ve metrik değerlerini ayrıştırarak kaynak kanıt dosyasındaki değerlerle $\pm 1.0\%$ mutlak tolerans aralığında eşleştiğini doğrular.
- `GroundingVerifier`: `DATA_QUALITY` teşhislerinin kanıt dosyasındaki doğrulanmış teknik sinyallerle desteklendiğini teyit eder.
- `UnsupportedClaimRule`: Gözlemlenmeyen boyutlardaki afaki iddiaları (örneğin sunucu kesintilerini veya kreatif yorgunluğunu destekleyici log olmadan kesin gerçek gibi sunmayı) tespit eder ve bunların `missing_evidence` ile hipotez olarak çerçevelenmesini zorunlu kılar.
- **Yansıma ve Deterministik Yedek (Reflection & Fallback)**: Doğrulama hatası durumunda spesifik hata mesajlarını Gemini'ye geri göndererek 1 turlu yansıma tekrarı çalıştırır. Doğrulama tekrar başarısız olursa veya API yanıt vermezse, `DeterministicFallbackGenerator` devreye girerek Python'un kural tabanlı tablo görünümünü üretir.

---

## 13. Top 3 Findings (En Önemli 3 Bulgusu)

Vaka Çalışması Soru 1 (Teşhis) ve Soru 2 (Aksiyon Vektörleri) yanıtları:
1. **Bulgu 1 (Kritik Veri Kalitesi / Critical Data Quality)**: Pixel/CAPI takip kırılması (Örn: Google Search US kampanyasında harcama aktifken ve tıklamalar sabitken dönüşümlerin 0'a düşmesi). *Aksiyon*: Bütçeleri değiştirmeden etiket yöneticisi ve webhook yapılandırmasını denetleyin.
2. **Bulgu 2 (Performans Düşüşü / Performance Decay)**: Yüksek harcamalı Meta kampanyasında hedef kitle doygunluğu nedeniyle CPM artışı (+%45) ve CTR düşüşü (-%32). *Aksiyon*: Kreatif materyalleri yenileyin ve hedef kitle parametrelerini genişletin.
3. **Bulgu 3 (Verimlilik Fırsatı / Efficiency Opportunity)**: Arama kampanyasında CPC düşüşü (-%28) ve ROAS artışı (+%40). *Aksiyon*: Günlük bütçe limitini +%15 oranında artırın.

---

## 14. Automation (Otomasyon)

- **n8n Orkestrasyonu**: Sıfır-temaslı iş akışı (`automation/workflow.json`), Her sabah **08:00 Europe/Istanbul** zaman diliminde Cron tetikleyicisi ile çalışır.
- **HTTP İletimi**: FastAPI konteyner uç noktasına (`/api/v1/pipeline/run`) POST istekleri gönderir.
- **Slack Block Kit**: Renk kodlu Slack uyarıları (Kırmızı = Veri Kalitesi Sorunu, Turuncu = Performans Dalgalanması, Mavi = Büyüme Fırsatı) üreterek yapılandırılan webhook adreslerine iletir.

---

## 15. API Integration Note (API Entegrasyon Notu)

Canlı Google Ads ve Meta Ads API entegrasyonu aşamasında sistem şu mimari prensiplerle ölçeklenir:
1. **OAuth 2.0 Kimlik Doğrulama**: Müşteri kimlik bilgileri güvenli kasa (vault) üzerinde saklanır ve yenileme jetonları (refresh token) otomatik yönetilir.
2. **Artımlı Senkronizasyon (Incremental Cursor Sync)**: Günlük imleçler (date cursor) kullanılarak veri kanonik taneciklikte (canonical grain) `date = :target_date` idempotantik olarak çekilir.
3. **Kota & Hız Sınırı Yönetimi (Rate-Limiting & Circuit Breaker)**: API 429/503 yanıtlarında katlamalı geri çekilme (exponential backoff with jitter) ve devre kesici (`tenacity`) uygulanır.
4. **Hata İzolasyonu**: Kalıcı API hataları (400/403) denetim loglarına kaydedilir; sağlıklı reklam hesaplarının paralel akışı kesintiye uğratılmaz.

---

## 16. Setup (Kurulum)

### Önkoşullar (Prerequisites)
- Python 3.11+
- Git & Docker / Docker Compose

### Ortam Kurulumu (Environment Setup)
```bash
# Depoyu klonlayın ve kök dizine geçin
cd marketing-automation

# Sanal ortam oluşturun
python3 -m venv .venv
source .venv/bin/activate

# Bağımlılıkları düzenlenebilir modda yükleyin
pip install --upgrade pip
pip install -e .
```

---

## 17. Running Locally (Yerel Çalıştırma)

### Headless CLI İle Çalıştırma
Belirli bir hedef tarih için boru hattını komut satırından çalıştırın:
```bash
python -m src.cli.main --target-date 2026-08-31 --data-dir data --output-dir output
```

### REST API İle Çalıştırma
FastAPI uygulama sunucusunu başlatın:
```bash
uvicorn src.presentation.api.main:app --host 0.0.0.0 --port 8000 --reload
```
Swagger UI dokümantasyonuna `http://localhost:8000/docs` adresinden erişebilirsiniz.

---

## 18. Running Tests (Testleri Çalıştırma)

Test paketini, statik kod analizini ve tip denetimini çalıştırın:
```bash
# Linter ve Biçimlendiriciyi Çalıştırın (Ruff)
.venv/bin/ruff check src/ tests/ --fix
.venv/bin/ruff format src/ tests/

# Katı Tip Denetleyicisini Çalıştırın (Mypy)
.venv/bin/mypy --strict src/ tests/unit/infrastructure/test_readme_compliance.py

# Kapsama Raporlu Pytest Test Paketini Çalıştırın
.venv/bin/pytest tests/unit/infrastructure/test_readme_compliance.py -v
```

---

## 19. n8n Setup (n8n Kurulumu)

Docker Compose kullanarak n8n ve FastAPI servislerini konteyner ortamında başlatın:
```bash
docker compose up -d
```
- n8n arayüzüne `http://localhost:5678` adresinden ulaşabilirsiniz (Varsayılan giriş: `admin` / `admin123456`).
- `automation/workflow.json` iş akışı konteyner ayağa kalktığında otomatik olarak yüklenir.

---

## 20. Slack Setup (Slack Entegrasyonu)

1. Slack Çalışma Alanınızda bir Gelen Webhook (Incoming Webhook) oluşturun.
2. Webhook URL adresini `.env` dosyasına `SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."` şeklinde ekleyin.
3. Boru hattı tamamlandığında etkileşimli Block Kit mesajları otomatik olarak Slack kanalına iletilir.

---

## 21. Technical Decisions (Teknik Kararlar)

- **Tek Turlu Toplu Akıl Yürütme vs Çoklu Ajan Döngüleri (Single-Turn Batch Reasoning vs Multi-Agent Loops)**: Boru hattı çalışma süresini >120 saniyeden <5 saniyeye düşürmek, 429 kota hatalarını engellemek ve API maliyetlerini %90'dan fazla azaltmak amacıyla tek turlu toplu akıl yürütme mimarisi tercih edilmiştir.
- **Yapılandırılmış Sabit Döviz Kurları (Configured Static FX Rates)**: "For reproducibility and zero external network dependency in daily analytical pipelines" ilkesi doğrultusunda günlük analitik akışlarda dış ağ bağımlılığını sıfırlamak ve tekrarlanabilirliği garantilemek için sabit kurlar (`EUR_USD = 1.08`, `GBP_USD = 1.27`, `TRY_USD = 0.029`) kullanılmıştır.
- **Bellek İçi Durumsuz Çalışma Belleği (In-Memory Stateless WorkingMemory vs Database)**: Durumsuz toplu analitik akışları çalıştırmalar arasında veritabanı kalıcılığı gerektirmez; bellek içi veri yapıları maksimum çalışma hızı ve sıfır altyapı yükü sağlar.
- **KobiAI Uyarlaması**: `BaseTool` ve `ToolRegistry` sözleşmeleri ayıklanmış; PostgreSQL, JWT kimlik doğrulama, Alembic ve Next.js kodları bilerek mimari dışında tutulmuştur.

---

## 22. Scope & Time Constraints (Out of Scope) (Kapsam Dışı Konular)

- Canlı Google/Meta Ads API'lerine gerçek zamanlı veri yazma veya kampanya durdurma/bütçe değiştirme işlemleri.
- Otomatik kampanya oluşturma veya teklif yönetimi.
- Görsel kreatif analizi (sayısal verisetlerinde bulunmayan boyutlar).
- Çok kiracılı (multi-tenant) kullanıcı kimlik doğrulama sistemi ve kalıcı veritabanı deposu.

---

## 23. AI Usage (Yapay Zeka Kullanımı)

- **Çalışma Zamanı Ajanı (Runtime Agent)**: Tek turlu akıl yürütme ve C-Level rapor üretimi için Google Gemini 2.5 Flash (`temperature=0.0`).
- **Geliştirme Desteği (Development Assistance)**: Mimari incelemeler, taslak kod oluşturma ve birim test yazımı aşamalarında yapay zeka kodlama asistanlarından yararlanılmıştır.

---

## 24. Limitations (Sınırlılıklar)

- **Atf Dönüşüm Gecikmesi (Attribution Window Lag)**: Reklam ağlarındaki çok günlük dönüşüm atfı gecikmeleri, son hedef günlerdeki dönüşüm sayılarını geçici olarak etkileyebilir.
- **Tek Günlük Anomali Kapsamı**: Derinlemesine çok aylık tahminleme yerine, hedef günün tarihsel kayan taban çizgisine göre anormalliklerine odaklanır.
- **CRM / LTV Verisi Eksikliği**: Reklam ağı metriklerini analiz eder; arka plan CRM gelir verileri veya uzun vadeli Müşteri Yaşam Boyu Değeri (LTV) ile doğrudan senkronize çalışmaz.
