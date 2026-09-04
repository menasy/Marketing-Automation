# E-Trink Global — Pazarlama Otomasyonu ve İstatistiksel Anomali Tespit Pipeline'ı

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Code Style](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Type Check](https://img.shields.io/badge/types-mypy%20strict-brightgreen.svg)](https://mypy-lang.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

E-Trink Global’in uluslararası çok kanallı reklam operasyonları (Google Ads, Meta Ads) için geliştirilmiş; günlük veri toplama, döviz ve kırılım (grain) normalizasyonu, bakış yönü sapmasız (look-ahead bias protection) 14–30 günlük kayan istatistiksel baz çizgisi hesaplama, Z-score tabanlı anomali tespiti, operasyonel kök neden analizi ve LLM destekli kanıta dayalı yönetici brifingi üreten üretim seviyesinde (production-grade) Python mimarisi.

---

## 1. Proje Özeti & Vizyon

Uluslararası ölçekte çoklu reklam hesabı ve para birimi yöneten dijital pazarlama operasyon ekipleri, her iş gününün ilk 60–90 dakikasını panellere manuel giriş yapıp CSV raporları indirmek, metrik değişimlerini kıyaslamak ve olası reklam arızalarını (CPA fırlamaları, CTR düşüşleri, piksel/dönüşüm takip kayıpları) tespit etmekle harcamaktadır.

Bu proje, E-Trink Global pazarlama operasyonundaki manuel müdahale ihtiyacını tamamen ortadan kaldıran uçtan uca **Otomatik Sabah Brifingi ve Anomali Tespit Mimarisi** sunar:

1. **Veri Toplama & Normalizasyon:** Farklı kanallardan (Google Ads, Meta Ads) gelen ham günlük verileri standart şemaya getirir, döviz kurlarını (EUR, TRY, GBP vb.) USD bazlı hedef para birimine çevirir ve `1 satır = 1 platform × 1 hesap × 1 kampanya × 1 ülke × 1 gün` (canonical grain) seviyesinde birleştirir.
2. **Kayan İstatistiksel Baz Çizgisi:** Değerlendirilen $D$ hedef gününden önceki $[D-N, D-1]$ ($N \in [14, 30]$) tarih aralığını kapsayan kayan tarih penceresinde ortalama, standart sapma ve medyan değerlerini hesaplar. Hedef $D$ günü istatistiksel hesaba dahil edilmeyerek **bakış yönü sapması (look-ahead bias)** tamamen engellenir.
3. **Z-Score & Hacim Muhafızları (Volume Guards):** Metrik yönü kurallarına (CPA/CPC artışı olumsuz, ROAS/CTR düşüşü olumsuz, Spend artışı nötr) ve min. 7 günlük veri şartına göre istatistiksel Z-score sapmalarını hesaplar. Mikro bütçe ve sıfır dönüşüm gürültülerini hacim muhafızlarıyla filtreler.
4. **Operasyonel Bulgular ve Kök Neden Analizi:** Kampanya bazlı anomalileri kümeleyerek sorunun **Veri Kalitesi (Data Quality)** mı yoksa **Performans (Performance)** kaynaklı mı olduğunu deterministik kurallarla teşhis eder; Bütçe, Teklif, Kreatif ve Takip aksiyonları reçete eder.
5. **LLM Yönetici Brifingi & Grounding Güvenliği:** OpenAI GPT-4o-mini entegrasyonu ile sadece doğrulanmış `anomalies.json` girdisinden hareketle yönetici brifingi üretir. `output_validator.py` ile brifingdeki tüm kampanya, metrik ve oranların doğruluğunu deterministik olarak denetler.
6. **n8n & Zamanlanmış Bildirim Dağıtımı:** Mimarinin tamamı FastAPI ve headless CLI arabirimleri üzerinden dışarı açılır. n8n workflow'u ile her sabah 08:00'de (Europe/Istanbul) otomatik tetiklenerek Slack Block Kit ve Email üzerinden yöneticilere ulaştırılır.

---

## 2. Mimari Yapı (Clean Architecture & SOLID)

Proje, **Clean Architecture (Temiz Mimari)** ve **SOLID** ilkelerine tam uyum sağlayacak şekilde tasarlanmıştır. Bağımlılık yönü strictly dıştan içe doğrudur:

```
[Presentation: FastAPI / CLI]
       │
       ▼
[Application: Use Cases & Ports]
       │
       ▼
[Domain: Entities, Enums & Pure Services] ◄── [Infrastructure: Readers, LLM, Parsers]
```

### Katman Sorumlulukları ve İzolasyon Kuralları

- **Domain Katmanı (`src/domain/`):** Core iş mantığı, dondurulmuş veri sınıfları (`@dataclass(frozen=True)`), domain enum'ları (`StrEnum`) ve saf servisleri (`MetricCalculator`, `FindingRanker`, `AnomalyPolicy`) barındırır. **Sıfır dış bağımlılık** kuralı geçerlidir; Pandas, NumPy, FastAPI, HTTPX, Pydantic veya I/O kütüphaneleri bu katmana kesinlikle sızamaz.
- **Application Katmanı (`src/application/`):** Uygulama senaryolarını (`RunPipelineUseCase`, `NormalizeDataUseCase` vb.) ve altyapı arayüzlerini (Protocols/ABCs: `IDataReader`, `IBaselineProvider`, `ILanguageModelService`) içerir. Yalnızca Domain katmanına bağımlıdır.
- **Infrastructure Katmanı (`src/infrastructure/`):** Application katmanındaki portları gerçekleyen CSV okuyucular, Pandas veri işleyiciler, Z-score istatistiksel motoru, OpenAI LLM entegrasyonu, Pydantic Settings ve Slack/Email adaptörlerini barındırır. *Pandas DataFrames sadece CSV okuma/birleştirme aşamasında kullanılır, domain nesnelerine dönüştürülerek isolasyon sağlanır.*
- **Presentation Katmanı (`src/presentation/` & `src/cli/`):** FastAPI REST API uç noktalarını (`POST /api/v1/pipeline/run`) ve komut satırı uygulamasını (CLI) barındırır. İş mantığı içermez, sadece istekleri DTO'lara dönüştürerek `RunPipelineUseCase` çalıştırır.

---

## 3. Canlı API Entegrasyon Notu (Zorunlu – Max 10 Satır)

> Meta Marketing API (`/insights`) ve Google Ads API (`GoogleAdsService.SearchStream`) canlı entegrasyonunda; Meta tarafında System User Token (Long-Lived), Google tarafında ise OAuth2 Refresh Token + Developer Token ile gRPC/REST kimlik doğrulaması sağlanır. Günlük veri çekimlerinde son 7 günün attribution pencereli verisi çekilerek incremental upsert stratejisi uygulanır. Meta `X-Business-Use-Case-Usage` ve Google `RESOURCE_EXHAUSTED` HTTP 429 / gRPC limitlerinde exponential backoff & jitter mekanizması devreye girer. Başarısız istekler Dead Letter Queue (DLQ) ve Sentry üzerinde izlenerek veri kaybı engellenir. `IDataSource` portu sayesinde domain mantığı değişmeden API okuyucuları sisteme takılabilir.

---

## 4. Anomali Eşik Değerlerinin Gerekçesi (Zorunlu – 1 Paragraf)

> Reklam açık artırma (auction) ekosistemlerinde günlük harcama, tıklama ve dönüşüm metrikleri doğal bir piyasa dalgalanmasına (volatilitesine) sahiptir. Bu nedenle sabit yüzde sapmaları (ör. %40 harcama artışı, %30 CPA yükselişi, %50 dönüşüm düşüşü) tek başına değerlendirildiğinde ciddi bir **false-positive (yanlış alarm)** yorgunluğuna yol açar. Sistemimizde 14–30 günlük kayan istatistiksel pencerede hesaplanan 2-sigma ($Z \ge 2.0$, %95 güven aralığı) ve 3-sigma ($Z \ge 3.0$, %99.7 güven aralığı) screening eşikleri, metrik sapmasının rastgele piyasa gürültüsü mü yoksa istatistiksel olarak anlamlı bir arıza mı olduğunu ayırt eder. Min. 100 gösterim, min. $10 harcama ve min. 5 geçmiş dönüşüm gibi **Hacim Muhafızları (Volume Guards)** ile birleştirilen bu istatistiksel yaklaşım, mikro bütçeli kampanyalardaki matematiksel bölme sapmalarını eler ve operasyon ekiplerinin yalnızca gerçek aksiyon gerektiren krizlere odaklanmasını sağlar.

---

## 5. LLM Katmanı, Kısıtlar ve Grounding Denetimi

- **Harici Prompt Mimarisi:** Sistem yönergeleri kod içerisine gömülmeyip tamamen harici `/prompts/executive_briefing.md` dosyasında yönetilir.
- **Sıfır Halüsinasyon Kısıtı (`temperature=0.0`):** LLM bir anomali tespit motoru veya hesaplayıcı değildir; sadece tespit edilmiş `anomalies.json` verisini açıklayan bir özetleyicidir. Dış kaynaklı sektör ortalamaları, sezonluk tahminler veya veride bulunmayan varsayımlar kesin olarak yasaklanmıştır.
- **Deterministik Doğrulama (`output_validator.py`):** Üretilen Markdown brifing metni teslim edilmeden önce regex ve dize karşılaştırma denetiminden geçer. Metinde geçen tüm kampanya isimleri, metrik türleri ve yüzdesel/sayısal değerler kaynak JSON ile çapraz sorgulanır. Uyuşmazlık durumunda metne otomatik uyarı eklenir veya istisna fırlatılır.

---

## 6. Otomasyon Mimarisi (n8n & 08:00 Zamanlama)

- **Zamanlama:** Her gün sabah `08:00` (Europe/Istanbul - UTC+3). Ad platformlarının bir önceki güne ait veri hesaplamalarını tamamlaması sonrası en taze veriyle çalışır.
- **Orkestrasyon (n8n Workflow):** `automation/workflow.json` dosyası üzerinden n8n'e aktarılır.
  1. Cron Trigger düğümü 08:00'de tetiklenir.
  2. HTTP Request düğümü `POST http://localhost:8000/api/v1/pipeline/run` çağrısı yapar (60s timeout, 3 retry backoff).
  3. IF Condition düğümü `status === 'success'` kontrolü yapar.
  4. Başarılı akış: Özet ve en kritik 3 anomaliyi Slack Block Kit formatına getirip `#marketing-briefings` kanalına iletir.
  5. Hata akışı: Hata detayları ve `execution_id` ile `#marketing-alerts-critical` kanalına acil durum uyarısı düşer.

---

## 7. Reklam Operasyonu Değerlendirmesi Özeti (Top 3 Bulgu)

Veri seti üzerinde çalıştırılan analiz sonucunda en yüksek operasyonel ciddiyet skoruna sahip 3 kritik bulgu ve reçete edilen aksiyonlar belirlenmiştir:

1. **`AH | Retargeting | UK` (Meta Ads - UK):**
   - *Sınıflandırma:* **PERFORMANCE** (Gerçek Performans Düşüşü).
   - *Kanıt:* CPA %252.3 yükselmiş ($8.87 \rightarrow $31.24, Z=+17.43), ROAS %73.7 düşmüş ($11.36 \rightarrow $2.99, Z=-4.70), Dönüşüm %57.6 azalmıştır.
   - *Aksiyonlar:* Bütçe: `DECREASE`, Teklif: `ADJUST_TARGET_CPA_ROAS`, Kreatif: `AUDIT_LANDING_PAGE`, Takip: `NO_ACTION`.
2. **`AH | Advantage+ Shopping` (Meta Ads - UK):**
   - *Sınıflandırma:* **PERFORMANCE** (Gerçek Performans Düşüşü).
   - *Kanıt:* CPA %259.5 yükselmiş ($30.33 \rightarrow $109.03, Z=+14.86), ROAS %71.0 düşmüş, Dönüşüm %76.5 azalmıştır.
   - *Aksiyonlar:* Bütçe: `DECREASE`, Teklif: `ADJUST_TARGET_CPA_ROAS`, Kreatif: `AUDIT_LANDING_PAGE`, Takip: `NO_ACTION`.
3. **`VC | Prospecting | US` (Meta Ads - US):**
   - *Sınıflandırma:* **PERFORMANCE** (Gerçek Performans Düşüşü).
   - *Kanıt:* CPA %253.2 yükselmiş ($53.09 \rightarrow $187.52, Z=+14.54), ROAS %75.0 düşmüş, CTR %15.0 azalmıştır.
   - *Aksiyonlar:* Bütçe: `DECREASE`, Teklif: `ADJUST_TARGET_CPA_ROAS`, Kreatif: `REFRESH_FATIGUED_CREATIVES`, Takip: `NO_ACTION`.

---

## 8. Kurulum & Çalıştırma Adımları

### Ön Gereksinimler
- Python 3.11 veya 3.12
- Sanal ortam (`venv`)

### Kurulum

```bash
# Proje dizinine geçiş yapın
cd marketing-automation

# Sanal ortam oluşturun ve aktif edin
python3 -m venv .venv
source .venv/bin/activate

# Bağımlılıkları geliştirme modunda yükleyin
pip install -e ".[dev]"

# Ortam değişkenlerini hazırlayın
cp .env.example .env
```

### CLI Üzerinden Pipeline Çalıştırma

```bash
# Varsayılan veri yollarıyla çalıştırma
python -m src.cli.main

# Özel veri yolları ve değerlendirme tarihi ile çalıştırma
python -m src.cli.main \
  --google-csv data/google_ads_daily.csv \
  --meta-csv data/meta_ads_daily.csv \
  --window-days 14 \
  --currency USD
```

### FastAPI Sunucusunu Başlatma & REST API Tetikleme

```bash
# Uvicorn ile API sunucusunu başlatın
uvicorn src.presentation.api.app:app --host 0.0.0.0 --port 8000 --reload
```

Başka bir terminalden API'yi tetikleyin:

```bash
curl -X POST "http://localhost:8000/api/v1/pipeline/run" \
  -H "Content-Type: application/json" \
  -d '{
    "window_days": 14,
    "reporting_currency": "USD"
  }'
```

---

## 9. Teknik Kararlar & Kapsam Dışı Bırakılanlar

### Alınan Mühendislik Kararları
- **Pandas İzolasyonu:** Pandas sadece veri okuma ve birleştirme safhasında tutulmuş; Domain ve Application katmanlarına dondurulmuş pure Python dataclass nesneleri geçirilmiştir.
- **Sıfıra Bölme Güvenliği:** CTR, CPC, CPA ve ROAS hesaplamalarında payda sıfır olduğunda sahte `0.0` dönülmemiş, kesin olarak `None` dönülerek veri kirletilmesi engellenmiştir.
- **Deterministik Fallback:** OpenAI API anahtarı girilmediğinde veya servis zaman aşımına uğradığında pipeline çökmez; deterministik şablon motoru üzerinden brifing üretmeye devam eder.

### Kapsam Dışı Bırakılanlar (Out of Scope)
- **Canlı API Bağlantıları:** Süre ve bütçe kısıtı nedeniyle canlı Google/Meta API SDK bağlayıcıları yerine CSV okuyucuları entegre edilmiştir (Mimari `IDataSource` portu ile canlı API'ye hazırdır).
- **Gerçek Zamanlı WebSocket/SSE:** Sabah brifingi konsepti gereği batch/cron odaklı mimari tercih edilmiş, anlık yayın mimarisi kapsam dışı bırakılmıştır.

---

## 10. Yapay Zekâ Kullanım Beyanı

Bu projenin geliştirilmesi sürecinde **Antigravity (Gemini 3.6 Flash)** yapay zekâ asistanı kullanılmıştır. AI araçları şu aşamalarda şeffaf bir şekilde değerlendirilmiştir:
1. Clean Architecture katman izolasyon kurallarının ve TDD test senaryolarının tasarlanması,
2. Edge-case (uç durum) test verilerinin scaffolding süreçleri,
3. Dokümantasyon ve n8n mermaid şemalarının hazırlanması.

Tüm domain kuralları, Z-score istatistiksel hesaplama mantığı, defensive math kontrolleri, kök neden analizi ve validasyon kodları mühendislik standartlarına uygun şekilde doğrulanmış ve test edilmiştir.
