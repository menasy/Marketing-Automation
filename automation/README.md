# 🚀 Pazarlama Otomasyonu ve Orkestrasyon Kılavuzu (n8n & FastAPI)

## 📌 Mimari Özet ve Yönetici Özeti (Executive Summary & Architectural Overview)

Bu dizin, otonom pazarlama anomali tespit boru hattının üretim ortamı **n8n otomasyon iş akışını** (`automation/workflow.json`) ve teknik orkestrasyon kılavuzunu içermektedir.

### 🏗️ Mimari Akış Diyagramı (Architecture & Flow Diagram)

```text
               +----------------------------------------+
               |          OTOMASYON TETİKLEYİCİ         |
               |  - Cron Tetikleyici: 0 8 * * *         |
               |    (Her Gün 08:00 Europe/Istanbul)     |
               |  - Manuel / Webhook Tetikleyici        |
               +-------------------+--------------------+
                                   |
                                   v
               +----------------------------------------+
               |           HTTP İSTEK DÜĞÜMÜ            |
               |  POST http://api:8000/api/v1/pipeline/run |
               |  Yük: {"target_date": "D-1", ...}      |
               |  Zaman Aşımı: 120s (LLM penceresi)     |
               +-------------------+--------------------+
                                   |
                                   v
               +----------------------------------------+
               |        EĞER (IF) DURUM GEÇİDİ          |
               |    Durum == 'success' / 200 OK mi?     |
               +---------+--------------------+---------+
                         |                    |
             [DOĞRU / BAŞARILI]       [YANLIŞ / BAŞARISIZ]
                         |                    |
                         v                    v
+----------------------------------+ +----------------------------------+
|  SLACK BAŞARI ÖZETİNİ BİÇİMLENDİR | |  SLACK ACİL UYARISINI BİÇİMLENDİR|
|  - Slack Block Kit UI Oluşturur   | |  - Çalıştırma hatasını çıkarır   |
|  - En Önemli 3 Bulgu ve Özet      | |  - Kritik uyarı yükü hazırlar   |
|    Anlatıyı Düzenler              | |  - Kanal:                        |
|                                  | |    #marketing-alerts-critical    |
+----------------+-----------------+ +----------------+-----------------+
                 |                                    |
                 v                                    v
+----------------------------------+ +----------------------------------+
|   SLACK ÖZET BİLDİRİMİNİ GÖNDER  | |   ACİL UYARI BİLDİRİMİNİ GÖNDER  |
|   (POST ${SLACK_WEBHOOK_URL})    | |   (POST ${SLACK_WEBHOOK_URL})    |
+----------------------------------+ +----------------------------------+
```

---

### 🛡️ Katı Mimari Ayrım Bildirimi (Statement of Architectural Separation)

Temiz Mimari ve SOLID prensiplerini korumak adına, **n8n yalnızca bir orkestrasyon, zamanlama ve bildirim taşıma katmanı** olarak görev yapar.

- **Python / FastAPI Motorunun Üstlendiği Görevler (İş Mantığı ve Akıl Yürütme Çekirdeği):**
  - Ham reklam verilerini (Google Ads ve Meta Ads CSV) okuma ve raporlama para birimine (USD/TRY/EUR) dönüştürme.
  - Deterministik istatistiksel taban çizgisi hesaplamaları (14 günlük kayan pencere, hareketli Z-skoru testleri, yüzdesel metrik değişimleri).
  - Anomali tespiti filtreleri ($|Z| \ge 2.0$, $|\Delta| \ge 20\%$, harcama eşikleri).
  - Yapılandırılmış kanıt dosyası derleme ve çoklu metrik sinyallerini çıkarma (`ZERO_CONVERSIONS_WITH_ACTIVE_SPEND`, `COST_SPIKE_VOLUME_DROP`).
  - Gemini LLM çoklu hipotez kök neden analizi (Veri Kalitesi vs Performans Düşüşü) ve operasyonel aksiyon planlaması.
  - Doğrulama kapısı (Verifier Engine) ve deterministik yedek motoru.

- **n8n Otomasyonunun Üstlendiği Görevler (Yalnızca Orkestrasyon ve Bildirim Katmanı / ZERO business logic):**
  - Zaman odaklı cron zamanlaması (`0 8 * * *` Europe/Istanbul).
  - Konteyner ortamındaki Python uç noktasını REST HTTP POST (`http://api:8000/api/v1/pipeline/run`) ile tetikleme.
  - HTTP durum kodlarını ve yanıt sağlık durumunu denetleme.
  - Biçimlendirilmiş Slack Block Kit bildirimlerini ilgili kanallara veya başarısızlık durumunda `#marketing-alerts-critical` kanalına iletme.

> **Mimari Sınır kuralı:** n8n içerisinde **ZERO business logic** (sıfır iş mantığı), metrik hesaplaması, anomali filtrelemesi veya istem yapısı yer almaz. İş kuralları değiştiğinde yalnızca ana Python kod tabanı güncellenir.

---

## ⚙️ Düğüm Detay Özellikleri (Node-by-Node Specification)

n8n iş akışı (`automation/workflow.json`) birbirine bağlı 8 temel düğümden oluşur:

1. **Zamanlayıcı Tetikleyici (Schedule Trigger / `n8n-nodes-base.scheduleTrigger`)**
   - **Cron İfadesi:** `0 8 * * *`
   - **Zaman Dilimi:** `Europe/Istanbul`
   - **Amaç:** Her sabah saat 08:00 Europe/Istanbul zaman diliminde günlük boru hattı çalıştırmasını otomatik başlatır.

2. **Manuel Tetikleyici (Manual Trigger / `n8n-nodes-base.manualTrigger`)**
   - **Amaç:** n8n arayüzünden veya CLI üzerinden talep üzerine çalıştırma, geçmişe dönük veri işleme ve test çalıştırmaları sağlar.

3. **HTTP İstek Düğümü (HTTP Request Node / `n8n-nodes-base.httpRequest`)**
   - **HTTP Yöntemi:** `POST`
   - **Uç Nokta URL:** `http://api:8000/api/v1/pipeline/run`
   - **Üstbilgiler (Headers):** `Content-Type: application/json`
   - **İstek Yükü (Payload):**
     ```json
     {
       "target_date": "={{ $now.minus({days: 1}).toFormat('yyyy-MM-dd') }}",
       "data_dir": "data",
       "output_dir": "output"
     }
     ```
   - **Zaman Aşımı Politikası:** Gemini LLM toplu akıl yürütme, öz-düzeltme bariyerleri ve dosya çıktı üretimini kapsamak üzere 120,000 ms (120 saniye).
   - **Tekrar Deneme Politikası:** Katlamalı geri Çekilme ile 3 tekrar denemesi (2,000 ms gecikme).

4. **Eğer (IF) Koşul Geçidi (Status Gate / `n8n-nodes-base.if`)**
   - **Koşul:** `leftValue: "={{ $json.status }}"`, `operator: "equals"`, `rightValue: "success"` (veya status code 200).
   - **Doğru (True) Kolu:** Başarı mesajı biçimlendiricisine yönlendirir.
   - **Yanlış (False) Kolu:** Acil durum hata uyarısı biçimlendiricisine yönlendirir.

5. **Slack Başarı Mesajını Biçimlendir (Format Slack Success Message / `n8n-nodes-base.code`)**
   - **Amaç:** Yapılandırılmış JSON çıktısını (`PipelineResult`) Slack Block Kit arayüz bileşenlerine (Başlık, Yönetici Anlatısı, En Önemli 3 Bulgu Matrisi, Operasyonel Aksiyonlar) dönüştürür.

6. **Slack Yönetici Özetini Gönder (Send Slack Briefing / `n8n-nodes-base.httpRequest`)**
   - **HTTP Yöntemi:** `POST`
   - **Hedef URL:** `={{ $env.SLACK_WEBHOOK_URL }}`
   - **Yük:** `{"blocks": $json.blocks}`
   - **Hedef Kanal:** Birincil Pazarlama Operasyon Kanalı.

7. **Slack Acil Durum Uyarısını Biçimlendir (Format Slack Emergency Alert / `n8n-nodes-base.code`)**
   - **Amaç:** Çalıştırma hatası izini, başarısız olan aşama tanımlayıcısını (`failed_stage`), çalıştırma UUID değerini ve zaman damgasını kritik uyarı bloğu formatına getirir.

8. **Kritik Uyarıyı Gönder (Send Emergency Alert to #marketing-alerts-critical / `n8n-nodes-base.httpRequest`)**
   - **HTTP Yöntemi:** `POST`
   - **Hedef URL:** `={{ $env.SLACK_WEBHOOK_URL }}`
   - **Yük:** `{"channel": "#marketing-alerts-critical", "blocks": $json.blocks}`
   - **Hedef Kanal:** `#marketing-alerts-critical`

---

## 🐳 Otomatik Yükleme ve Konteyner Yayılımı (Zero-Touch Auto-Import)

`docker-compose.yml`, manuel arayüz yapılandırmasına ihtiyaç duymadan hem FastAPI arka plan servisini hem de n8n otomasyon motorunu otomatik olarak yayına alır.

### Otomatik Yükleme Mekanizması (Zero-Touch Auto-Import)

Konteyner ayağa kalkarken n8n, `docker-compose.yml` içerisinde tanımlı CLI yükleme komutunu çalıştırır:
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

### Manuel Yükleme Adımları (n8n UI Fallback)

n8n web arayüzü (`http://localhost:5678`) üzerinden değerlendirme yapılıyorsa:
1. Tarayıcıda `http://localhost:5678` adresini açın.
2. **Workflows** -> **Import from File** adımlarını takip edin.
3. Proje dizinindeki `automation/workflow.json` dosyasını seçin.
4. Tüm 8 düğümün yüklendiğini doğrulayın ve **Activate** butonuna basın.

---

## 🔒 Çevre Değişkenleri ve Güvenlik İzolasyonu (Environment Variables)

Tüm gizli anahtarlar ve çevre değişkenleri katı biçimde izole edilmiştir. Kod tabanında veya JSON iş akışlarında hiçbir kimlik bilgisi, jeton veya webhook URL'si hardcode edilmemiştir.

| Çevre Değişkeni | Açıklama | Örnek / Konum |
|---|---|---|
| `SLACK_WEBHOOK_URL` | Slack uyarıları ve özetleri için Gelen Webhook URL adresi | `.env` dosyasından aktarılır |
| `GEMINI_API_KEY` | Gemini Pro / Flash LLM API kimlik doğrulama anahtarı | `.env` dosyasından aktarılır |
| `GENERIC_TIMEZONE` | n8n cron zamanlayıcısı için zaman dilimi ayarı | `Europe/Istanbul` |
| `N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS` | Güvenlik için dosya yetki denetimlerini zorunlu kılar | `true` |

---

## 🧪 Test ve Operasyonel Doğrulama Kılavuzu (Testing & Verification Runbook)

Uçtan uca otomasyon işlevselliğini doğrulamak için aşağıdaki adımları sırasıyla uygulayın:

### Adım 1: FastAPI Servis Sağlığını Doğrulama
```bash
curl -f http://localhost:8000/health
```
Beklenen Çıktı: `{"status":"healthy","environment":"production","version":"1.0.0"}`

### Adım 2: CLI İle Manuel Tetikleme
```bash
python -m src.cli.main --target-date 2026-08-31 --window-days 14 --currency USD
```
Beklenen Çıktı: Boru hattı çalışır, özet çıktıyı ekrana basar ve `output/` dizinine raporları yazar.

### Adım 3: cURL / REST API İle Tetikleme
```bash
curl -X POST http://localhost:8000/api/v1/pipeline/run \
  -H "Content-Type: application/json" \
  -d '{"target_date": "2026-08-31", "data_dir": "data", "output_dir": "output"}'
```
Beklenen Çıktı: `execution_id`, `status: "success"` ve rapor yollarını içeren `200 OK` JSON yanıtı.

### Adım 4: n8n Çalıştırma Geçmişini İnceleme
1. `http://localhost:5678/executions` adresine gidin.
2. Cron zamanlayıcısı veya manuel tetikleyici ile başlatılan başarılı çalıştırmayı gözlemleyin.
3. Yeşil renkli düğüm loglarını inceleyin ve Slack webhook çıktısını teyit edin.
