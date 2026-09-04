# Görsel Mimari & Akış Diyagramları — Sabah Brifingi Pipeline'ı

Bu doküman, n8n Sabah Brifingi ve Anomali Uyarı Otomasyon Pipeline'ının Mermaid.js diyagramları ile hazırlanmış görsel mimari ve akış şemalarını sunar.

---

## 1. Uçtan Uca Sıralama Diyagramı (Sequence Diagram)

Aşağıdaki sıralama diyagramı; n8n Zamanlayıcısı (Cron Trigger), FastAPI Uygulaması, Dahili Domain Servisleri, OpenAI LLM Servisi ve Slack Webhook uç noktaları arasındaki etkileşim akışını detaylandırır.

```mermaid
sequenceDiagram
    autonumber
    participant Cron as n8n Zamanlayıcı Tetikleyici<br/>(08:00 Europe/Istanbul)
    participant HTTP as n8n HTTP İstek Düğümü
    participant API as FastAPI Pipeline API<br/>(POST /api/v1/pipeline/run)
    participant Domain as Python Domain & Servisler<br/>(Normalizasyon, Anomali Motoru)
    participant LLM as OpenAI GPT-4o-mini
    participant IF as n8n IF Koşul Düğümü
    participant Slack as Slack Webhook<br/>(#marketing-alerts)

    Cron->>HTTP: Cron Etkinliği Tetikle (08:00 AM)
    activate HTTP
    HTTP->>API: POST /api/v1/pipeline/run (Timeout 60s)
    activate API
    API->>Domain: CSV Verilerini Oku & Normalize Et (Google/Meta)
    activate Domain
    Domain->>Domain: Kayan Baz Çizgisi & Z-Score Hesapla
    Domain->>Domain: Operasyonel Bulguları Derecelendir (Top 3)
    Domain-->>API: Derecelendirilmiş Anomalileri Döndür
    deactivate Domain
    
    API->>LLM: Brifing Özetini Üret (temperature=0.0)
    activate LLM
    LLM-->>API: Yönetici Brifing Metni
    deactivate LLM

    API-->>HTTP: HTTP 200 OK { status: "success", briefing: {...}, anomalies: [...] }
    deactivate API
    HTTP->>IF: Yanıt JSON'unu İlet
    deactivate HTTP

    activate IF
    alt status == 'success' (Başarılı Akış)
        IF->>Slack: Formatlanmış Block Kit Brifing Mesajını Gönder
        Slack-->>IF: HTTP 200 OK (Brifing İletildi)
    else status == 'failed' VEYA HTTP 5xx (Hata Akışı)
        IF->>Slack: Acil Durum Uyarısını #marketing-alerts-critical Kanalına Gönder
        Slack-->>IF: HTTP 200 OK (Acil Uyarı İletildi)
    end
    deactivate IF
```

---

## 2. Akış Şeması ve Yeniden Deneme (Retry) Mantığı

Aşağıdaki akış şeması; düğüm karar ağacını, koşul değerlendirmesini ve katlanarak artan bekleme süreli (exponential backoff) yeniden deneme politikasını görselleştirir.

```mermaid
flowchart TD
    Start(["⏰ Cron Tetikleyici<br/>08:00 Europe/Istanbul"]) --> HTTP["🌐 HTTP İstek Düğümü<br/>POST /api/v1/pipeline/run"]

    subgraph RetryLoop ["Yeniden Deneme Motoru (Max 3 Deneme, 2s Backoff)"]
        HTTP -->|HTTP 200 OK| Cond["⚡ IF Koşul Düğümü<br/>status === 'success'?"]
        HTTP -->|Ağ Kesintisi / Timeout / 5xx| Retry{"Deneme Sayısı < 3?"}
        Retry -->|Evet| Wait["⏳ 2000ms Bekle"] --> HTTP
        Retry -->|Hayır| FailAlert["🚨 Acil Durum Uyarısı Formatla"]
    end

    Cond -->|Evet: Başarılı| FormatSuccess["📝 Slack Block Kit Brifingini Formatla"]
    Cond -->|Hayır: Hata| FailAlert

    FormatSuccess --> SendSlack["💬 Slack Brifingi Gönder<br/>(#marketing-briefings)"]
    FailAlert --> SendAlert["🚨 Acil Durum Uyarısı Gönder<br/>(#marketing-alerts-critical)"]

    SendSlack --> EndSuccess(["✅ Süreç Başarıyla Tamamlandı"])
    SendAlert --> EndFail(["❌ Acil Durum Uyarısı İletildi"])

    style Start fill:#2ecc71,stroke:#27ae60,color:#fff
    style Cond fill:#f1c40f,stroke:#f39c12,color:#333
    style FailAlert fill:#e74c3c,stroke:#c0392b,color:#fff
    style SendAlert fill:#e74c3c,stroke:#c0392b,color:#fff
    style SendSlack fill:#3498db,stroke:#2980b9,color:#fff
    style EndSuccess fill:#2ecc71,stroke:#27ae60,color:#fff
    style EndFail fill:#95a5a6,stroke:#7f8c8d,color:#fff
```
