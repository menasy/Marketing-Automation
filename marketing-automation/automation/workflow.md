# Otomatik Sabah Brifingi & Anomali Uyarı Pipeline'ı — n8n Kullanım ve Düğüm Dokümanı

## 1. İş Amacı ve Operasyonel Hedef

Çoklu reklam hesabı ve platformu (Google Ads, Meta Ads, TikTok Ads vb.) yöneten dijital pazarlama operasyon ekipleri, geleneksel olarak her iş gününün ilk 60–90 dakikasını bireysel panellere manuel giriş yaparak, CSV raporları indirerek, metrik değişimlerini kıyaslayarak ve beklenmeyen kampanya arızalarını (örneğin ani CPC fırlamaları, CTR düşüşleri veya piksel takip kayıpları) arayarak harcamaktadır. 5'ten fazla uluslararası hesap yönetildiğinde bu manuel süreç yavaş, hataya açık ve reaktiftir.

Bu **n8n Otomasyon Workflow'u**, günlük sabah brifingi sürecini uçtan uca otomatikleştirerek bu operasyonel darboğazı çözer. Her sabah **08:00'de (Europe/Istanbul - UTC+3)** n8n tetiklenir, Python Pazarlama Otomasyonu REST API'sini çağırır, yürütmeyi orkestre eder, bulguları yüksek etkili Slack Block Kit yönetici bildirimlerine dönüştürür ve herhangi bir aşamada hata oluşursa acil durum kanallarına uyarı yönlendirir.

### Gelişmiş İzolasyon ve Ayrıştırma İlkesi (Strict Decoupling)
Bu sistemin temel mimari ilkesi **Tam Ayrıştırma (Strict Decoupling)** kuralıdır:
- **n8n** yalnızca harici bir zamanlayıcı (scheduler), HTTP orkestratörü, koşullu yönlendirici ve Slack bildirim taşıyıcısı olarak görev yapar.
- **n8n KESİNLİKLE İŞ MANTIĞI İÇERMEZ.** Veri toplama, döviz ve kırılım normalizasyonu, Z-score istatistiksel anomali tespiti, kök neden analizi ve LLM brifing üretimi tamamen ana Python uygulaması (`marketing-automation`) içerisinde gerçekleşir.

---

## 2. Düğüm Düğüm (Node-by-Node) Yapılandırma Rehberi

n8n workflow'u (`automation/workflow.json`), aşağıdaki gibi yapılandırılmış 7 adet üretim seviyesinde düğümden oluşur:

### Düğüm 1: Zamanlayıcı Tetikleyici (`Cron Trigger`)
- **Düğüm Tipi:** `n8n-nodes-base.scheduleTrigger` (v1.2)
- **Zamanlama:** Her gün saat `08:00` (`0 8 * * *`)
- **Saat Dilimi:** `Europe/Istanbul` (UTC+3)
- **Görevi:** Sabah brifingi sürecini her takvim günü otomatik olarak başlatır.

### Düğüm 2: HTTP İsteği (`HTTP Request Node`)
- **Düğüm Tipi:** `n8n-nodes-base.httpRequest` (v4.2)
- **HTTP Metodu:** `POST`
- **Hedef Endpoint:** `http://localhost:8000/api/v1/pipeline/run`
- **Header:** `Content-Type: application/json`
- **Body:** `{}` (Varsayılan tam uçtan uca akışı tetikler)
- **Zaman Aşımı (Timeout):** `60,000 ms` (60 saniye — normalizasyon, anomali tespiti ve LLM brifing üretiminin tamamlanmasına izin verir)
- **Yeniden Deneme Politikası:** `retryOnFail: true`, `maxTries: 3`, `waitBetweenTries: 2000 ms` (Geçici ağ kesintilerinde otomatik 3 deneme).

### Düğüm 3: IF Koşul Düğümü (`IF Condition Node`)
- **Düğüm Tipi:** `n8n-nodes-base.if` (v2.2)
- **Koşul:** `json.status === 'success'` değerini değerlendirir.
- **Yönlendirme:**
  - **TRUE (Başarılı Akış):** Veriyi Düğüm 4'e (`Format Slack Success Message`) yönlendirir.
  - **FALSE (Hata Akışı):** Veriyi Düğüm 6'ya (`Format Slack Emergency Alert`) yönlendirir.

### Düğüm 4: JavaScript Kod Düğümü (`Format Slack Success Message`)
- **Düğüm Tipi:** `n8n-nodes-base.code` (v2)
- **Görevi:** API yanıt JSON'unu (yönetici brifingi özeti, en kritik anomaliler, oluşturulma zamanı) Slack Block Kit JSON formatına dönüştürür.
- **Oluşturulan Bloklar:**
  - Emojili başlık bloğu (`📊 Daily Marketing Automation Executive Briefing`).
  - Zaman damgası ve durum bağlam bloğu.
  - Yönetici Özetini içeren metin bloğu.
  - En kritik anomalilerin kampanya adı, platform, metrik türü ve Z-score ile listelendiği bölüm.
  - Doğrudan rapora giden eylem butonu (`View Full Briefing Report`).

### Düğüm 5: HTTP İsteği (`Send Slack Briefing`)
- **Düğüm Tipi:** `n8n-nodes-base.httpRequest` (v4.2)
- **HTTP Metodu:** `POST`
- **Hedef URL:** `={{ $vars.SLACK_WEBHOOK_URL }}`
- **Payload:** Düğüm 4'ten gelen Slack Block Kit JSON verisi.

### Düğüm 6: JavaScript Kod Düğümü (`Format Slack Emergency Alert`)
- **Düğüm Tipi:** `n8n-nodes-base.code` (v2)
- **Görevi:** Pipeline yürütmesi başarısız olduğunda acil durum uyarı yükünü formatlar.
- **Uyarı Alanları:** Yürütme ID'si (`execution_id`), hedef kanal (`#marketing-alerts-critical`), başarısız olan aşama, hata mesajı ve zaman damgası.

### Düğüm 7: HTTP İsteği (`Send Emergency Alert to #marketing-alerts-critical`)
- **Düğüm Tipi:** `n8n-nodes-base.httpRequest` (v4.2)
- **HTTP Metodu:** `POST`
- **Hedef URL:** `={{ $vars.SLACK_WEBHOOK_URL }}`
- **Payload:** Düğüm 6'dan gelen acil durum mesajı (`#marketing-alerts-critical` kanalına iletilir).

---

## 3. Saat Dilimi ve Operasyonel Gerekçe

- **Yapılandırılan Saat Dilimi:** `Europe/Istanbul` (UTC+3)
- **Tetiklenme Saati:** `08:00 AM`
- **Operasyonel Gerekçe:**
  1. **Mesai Saatleri Uyumluğu:** Avrupa ve İstanbul pazarlama operasyon ekipleri günlük değerlendirmelerine 08:30–09:00 saatleri arasında başlar. 08:00'de tetikleme yapmak, brifingin sabah toplantılarından önce hazır olmasını sağlar.
  2. **Veri Hazırlık Süresi:** Reklam platformları (Google Ads, Meta Ads) bir önceki güne ait günlük verileri UTC saatine göre 03:00–05:00 arasında kesinleştirir. 08:00'de çalıştırmak, eksik veya kesintili veri çekim riskini tamamen ortadan kaldırır.

---

## 4. Ortam Değişkenleri ve Gizli Anahtar Yönetimi

Tüm hassas endpoint URL'leri ve token'lar n8n Global Değişkenleri (`$vars`) veya ortam değişkenleri üzerinden yönetilir. **`workflow.json` içerisinde sıfır hardcoded secret bulunur.**

### Önerilen Değişkenler
| Değişken Adı | Amacı | Örnek Değer |
|---|---|---|
| `API_BASE_URL` | Pazarlama Otomasyonu FastAPI temel adresi | `http://localhost:8000` |
| `SLACK_WEBHOOK_URL` | Slack Incoming Webhook URL adresi | `https://hooks.slack.com/services/T00/B00/XXX` |
| `SLACK_CRITICAL_CHANNEL` | Acil uyarı kanalı | `#marketing-alerts-critical` |

---

## 5. Hata Senaryoları ve Otomatik İyileşme Politikası

Workflow, dayanıklı hata yönetimi ve otomatik iyileşme mekanizmalarına sahiptir:

```
                          [HTTP Request: POST /api/v1/pipeline/run]
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 │                                               │
           [HTTP 200 OK]                                  [HTTP 5xx / Timeout]
                 │                                               │
         [Status Kontrolü]                              [Yeniden Deneme Motoru]
         ┌───────┴───────┐                             (Max 3 deneme, 2s backoff)
    [Success]        [Failure]                                   │
        │                │                          ┌────────────┴────────────┐
[Format Briefing]  [Format Alert]                 [Çözüldü mü?]           [Tükendi]
        │                │                          │                         │
  [Send Slack]     [Send Critical Alert]         [Başarılı]             [Acil Durum Uyarısı
                                                                          Kanala İletilir]
```

### Ele Alınan Hata Senaryoları

1. **Geçici Ağ Kesintileri / API Yavaşlaması (HTTP 504 / Connection Reset):**
   - Düğüm 2 üzerindeki retry politikası (`retryOnFail: true`) ile ele alınır.
   - 2.000 ms beklemeli 3 otomatik deneme yapılır.

2. **Backend Uygulama Hatası (HTTP 500 / Status "failed"):**
   - IF koşul düğümü **Hata Akışına** yönlendirir.
   - Kırmızı uyarı kartı oluşturularak `execution_id`, `failed_stage` ve hata detayı eklenir.
   - Derhal `#marketing-alerts-critical` kanalına iletilir.

3. **Slack Webhook Kesintisi:**
   - Python e-posta bildirim servisi (`EmailNotificationService`), ikincil bağımsız bildirim taşıyıcısı olarak yedekte bekler.
