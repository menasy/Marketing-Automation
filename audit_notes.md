# AUDIT & MAPPING REPORT: AS-IS / TO-BE CODE MAPPING & KOBIAI INTEGRATION PLAN

**Step:** FAZ 0 — PROMPT 0.1  
**Project:** marketing-automation  
**Reference Project:** yzta_kobi_ai  
**Compliance Standard:** `AGENT.md` (SOLID, Clean Architecture, Strict Typing, Zero Hardcoded Secrets, Zero Code Mutations in FAZ 0)

---

## 1. OBJECTIVE & CONTEXT SUMMARY
Mevcut `marketing-automation` kod tabanındaki deterministik Python kodlarında yer alan hardcoded teşhis (`IssueType`), kural tabanlı karar ağaçları ve statik Türkçe/İngilizce tavsiye metinlerinin eksiksiz satır bazlı envanteri çıkarılmıştır. Aynı zamanda `yzta_kobi_ai` projesindeki agent ve tool mimarisi incelenmiş ve bu desenlerin `marketing-automation` projesine taşınma/uyarlanma stratejisi haritalandırılmıştır.

---

## 2. AS-IS ENVANTERİ: HARDCODED MANTIK VE KARAR AĞAÇLARI TESPİTİ

### 2.1. `src/domain/services/finding_ranker.py`
Bu dosya `FindingRanker` adında saf domain servisi olarak kurgulanmış ancak içerisinde severe şekilde teşhis koyma, karar ağaçları ve metin üretme (rule-based recommendation) barındırmaktadır.

* **Hardcoded Ağırlık / Sabit Tabloları (Satır 19 - 44):**
  * `_SEVERITY_ORDER` (Satır 19-24): Severity enum sıralaması (`CRITICAL: 4`, `HIGH: 3`, `MEDIUM: 2`, `LOW: 1`).
  * `_SEVERITY_WEIGHTS` (Satır 26-31): Severity skoru ağırlıkları (`CRITICAL: 100.0`, `HIGH: 75.0`, `MEDIUM: 50.0`, `LOW: 25.0`).
  * `_METRIC_CRITICALITY_MULTIPLIER` (Satır 33-44): Metrik bazlı katsayılar (`CONVERSIONS: 1.5`, `ROAS: 1.5`, `CPA: 1.5`, `CTR: 1.2`, `CPC: 1.2`, `SPEND: 1.0`, vb.).

* **Metod: `_evaluate_issue_type(cls, items)` (Satır 155 - 234):**
  * **İşlevi:** Anomalilerin `DATA_QUALITY`, `PERFORMANCE` veya `MIXED` olup olmadığına karar veren kural tabanlı karar ağacı.
  * **Hardcoded Kelime ve Eşikler:**
    * Satır 180-189: `"pixel"`, `"capi"`, `"gtm"`, `"tracking"`, `"attribution"`, `"duplicate"`, `"currency"`, `"negative"` keyword araması.
    * Satır 198-199: Dönüşüm sıfırlanması (`baseline_value > 0 and current_value == 0`) veya `%90` üzerinde düşüş (`change_rate <= -0.90`).
    * Satır 202-203: CTR çöküşü (`change_rate < -0.20`).
    * Satır 206-208: Maliyet metriği artışı (`change_rate > 0.15`).
  * **Hardcoded Karar Blokları:**
    * Satır 211-215: Negatif metrik veya tracking keyword varsa $\rightarrow$ `IssueType.DATA_QUALITY`
    * Satır 217-219: CTR çöküşü olmaksızın dönüşüm sıfırlanması/çöküşü varsa $\rightarrow$ `IssueType.DATA_QUALITY`
    * Satır 221-226: CTR çöküşü + maliyet artışı veya birden fazla anomali varsa $\rightarrow$ `IssueType.PERFORMANCE`
    * Satır 230-231: Fallback $\rightarrow$ `IssueType.DATA_QUALITY` veya `IssueType.MIXED`.

* **Metod: `_determine_actions(cls, issue_type, items)` (Satır 236 - 295):**
  * **İşlevi:** `IssueType` ve metrik yönlerine göre deterministik olarak aksiyon tuple'ı `(BudgetAction, BidAction, CreativeAction, TrackingAction)` üretir.
  * **Hardcoded Karar Blokları:**
    * Satır 240-251: `IssueType.DATA_QUALITY` $\rightarrow$ `(BudgetAction.HOLD, BidAction.NO_CHANGE, CreativeAction.NO_ACTION, TrackingAction.AUDIT_PIXEL_CAPI / VERIFY_GTM_TAGS)`
    * Satır 253-286: `IssueType.PERFORMANCE` $\rightarrow$ CTR düşüşünde `REFRESH_FATIGUED_CREATIVES`, Dönüşüm düşüşünde `AUDIT_LANDING_PAGE`, CPA/ROAS bozulmasında `DECREASE` budget ve `ADJUST_TARGET_CPA_ROAS` bid.
    * Satır 288-294: `IssueType.MIXED` $\rightarrow$ `(HOLD, NO_CHANGE, RUN_A_B_TEST, NO_ACTION)`.

* **Metod: `_build_operational_action(cls, issue_type, budget_act, bid_act, creative_act, tracking_act, platform)` (Satır 424 - 484):**
  * **İşlevi:** Türkçe statik aksiyon cümleleri üretir.
  * **Hardcoded Statik Stringler:**
    * Satır 437-440: `"{platform_label} GTM etiketlerini doğrulayın, dönüşüm etiketinin tetiklendiğini kontrol edin. Bütçeyi kapatmayın — veri sorunu çözülene kadar bekleyin."`
    * Satır 442-445: `"{platform_label} CAPI/Pixel entegrasyonunu kontrol edin, Event Manager'da son 24 saat etkinlik akışını doğrulayın. Bütçeyi kapatmayın — tracking düzeltilmeden performans değerlendirmesi yapılamaz."`
    * Satır 451-468: `"Günlük bütçeyi %20 kısın"`, `"Bütçeyi düşük performanslı kampanyadan yüksek ROAS'lı kampanyaya aktarın"`, `"hedef CPA/ROAS teklifini güncelleyin"`, `"yıpranmış kreatifleri yenileyin"`, `"açılış sayfasını denetleyin"`, `"yeni kreatiflerle A/B testi başlatın"`, `"negatif keyword listesini gözden geçirin"`.
    * Satır 480-482: `"24-48 saat izlemeye devam edin — atıf gecikme ihtimali var. Trend devam ederse bütçe ve tracking denetimi başlatın."`

* **Metod: `_build_business_impact(cls, issue_type, items)` (Satır 314 - 338):**
  * **İşlevi:** Statik iş etkisi (business impact) metinleri üretir.
  * **Hardcoded Stringler:**
    * Satır 319-321: `"Abrupt conversion/attribution tracking failure detected with active spend of $... Risk of misattributed ROI and invalid automated bidding decisions."`
    * Satır 335: `"Performance decline: ... Requires immediate optimization."`
    * Satır 337: `"Mixed performance signals detected. Potential attribution delay or emerging trend."`

---

### 2.2. `src/infrastructure/reporting/operational_report.py`

* **Metod: `render(self, findings)` (Satır 34 - 138):**
  * **İşlevi:** Top 3 bulguyu Markdown formatında rapora dönüştürür.
  * **Hardcoded Şablon ve Soru-Cevap Metinleri:**
    * Satır 104-107: `#### Soru 1: Bulgu gerçek bir performans sorununa mı işaret etmektedir, yoksa verinin kendisinden mi kaynaklanmaktadır?`
    * Satır 109-112: `**Yanıt (VERİ KALİTESİ / DATA_QUALITY):** Bu bulgu **veri kaynaklı (tracking/attribution)** bir soruna işaret etmektedir.`
    * Satır 114-117: `**Yanıt (GERÇEK PERFORMANS / PERFORMANCE):** Bu bulgu **gerçek bir performans düşüşüne** işaret etmektedir.`
    * Satır 119-122: `**Yanıt (KARMA / MIXED):** Bu bulgu **karma/belirsiz sinyaller** içermektedir.`
    * Satır 126-128: `#### Soru 2: Bütçe, teklif veya kreatif tarafında hangi aksiyonu alırdınız?`
    * Satır 131-134: `Bütçeyi gözden geçir`, `Algoritma hedefini düzenle`, `Görsel yenile`, `Piksel/GTM denetle`.

* **Metod: `to_finding_dict(finding)` (Satır 141 - 173):**
  * **Hardcoded Etiket Sözlüğü:**
    * Satır 147-149: `"data_quality": "VERİ / TRACKING HATASI"`, `"performance": "GERÇEK PERFORMANS SORUNU"`, `"mixed": "KARMA / BELİRSİZ"`.

---

### 2.3. Domain Modelleri ve DTO'lardaki Statik String Alanları

* **`src/domain/models/operational_finding.py` (Satır 20 - 28):**
  * `issue_type: IssueType`
  * `evidence_summary: str`
  * `business_impact: str`
  * `metric_change: str`
  * `operational_action: str`
  * `budget_action: str`
  * `bid_action: str`
  * `creative_action: str`
  * `tracking_action: str`
  * *(Not: Agent'a geçiş sonrasında bu alanlar Agent'ın ürettiği Pydantic şemasından beslenecek, Python tarafında deterministik string birleştirmeleri yapılmayacaktır).*

* **`src/application/dto/pipeline_response.py` (Satır 6 - 23):**
  * `FindingSummaryDTO`: `issue_type: str`, `operational_action: str`, `metric_change: str`.

---

## 3. TO-BE DÖNÜŞÜM HARİTASI (PYTHON VS AGENT SINIRLARI)

`AGENT.md` Direktifleri uyarınca Python katmanı yalnızca **Gerçeklik (Truth)** katmanıdır. Teşhis koymaz, öneri metni yazmaz. Agent ise **Akıl Yürütme (Reasoning)** katmanıdır.

### 3.1. `finding_ranker.py` Dönüşüm Planı

| Metod / Mantık | Mevcut Durum (As-Is) | Gelecek Durum (To-Be - FAZ 1+) | Sorumlu Katman |
|---|---|---|---|
| `_evaluate_issue_type` | Hardcoded kurallarla `DATA_QUALITY` vs `PERFORMANCE` teşhisi koyuyor. | **SİLİNECEK.** Teşhis ve hipotez değerlendirmesini Gemini Agent `EvidenceDossier` üzerinden yapacak. | Agent (Gemini) |
| `_determine_actions` | Statik enum aksiyonları atıyor. | **SİLİNECEK.** Aksiyon önerilerini Agent bağlama uygun şekilde üretecek. | Agent (Gemini) |
| `_build_operational_action` | Hardcoded Türkçe tavsiye cümleleri üretiyor. | **SİLİNECEK.** Operasyonel aksiyon metinlerini Agent üretecek. | Agent (Gemini) |
| `_build_business_impact` | Hardcoded İngilizce/Türkçe iş etkisi üretiyor. | **SİLİNECEK.** İş etkisi anlatısını Agent yapacak. | Agent (Gemini) |
| `rank_findings` / `cluster_by_campaign` | Kampanya bazlı gruplama yapıyor. | **TUTULACAK & YENİDEN YAPILANDIRILACAK.** `cluster_by_campaign` saf matematiksel gruplama yapacak. | Python |
| `_calculate_score` | Z-skoru, severity ve spend ile skor hesaplıyor. | **TUTULACAK.** Pure mathematical financial risk score olarak korunacak (`calculate_financial_risk_score`). | Python |
| `compile_evidence_dossier` | *(Yok)* | **YENİ EKLENECEK.** Deterministik verileri, z-skorlarını ve veri kalitesi bayraklarını (`zero_conversions_with_active_spend`) toplayıp Agent'a verecek `EvidenceDossier` üretecek. | Python |

### 3.2. Agent Tarafından Doldurulacak Yeni Pydantic Şemaları (`src/agent/schemas/`)

Agent'ın Gemini `response_schema` veya structured JSON output ile dolduracağı tip güvenli Pydantic sözleşmeleri:

```python
class Hypothesis(BaseModel):
    name: str = Field(description="Hypothesis name e.g. Pixel/CAPI Tracking Breakdown")
    description: str = Field(description="Detailed rationale for hypothesis")
    probability: float = Field(description="Probability score between 0.0 and 1.0")
    supporting_evidence: list[str] = Field(description="Evidence bullet points from dossier")
    missing_evidence: list[str] = Field(description="Evidence needed to confirm with 100% certainty")

class Finding(BaseModel):
    campaign_name: str
    platform: str
    country: str
    primary_metric: str
    severity: Severity
    issue_type: IssueType
    score: float
    metric_change_summary: str
    business_impact_narrative: str
    selected_hypothesis: Hypothesis

class Recommendation(BaseModel):
    campaign_name: str
    budget_action: str
    bid_action: str
    creative_action: str
    tracking_action: str
    rationale: str
    concrete_steps: list[str]

class BatchAnalysisResult(BaseModel):
    findings: list[Finding]
    recommendations: list[Recommendation]
    executive_briefing: str
    confidence_score: float
```

---

## 4. KOBİAI TRANSFER & ADAPTASYON PLANI

Reference Repository (`yzta_kobi_ai`) incelenmiş ve mimari bileşenlerin taşınma haritası çıkarılmıştır:

### 4.1. Taşınacak ve Uyarlanacak Bileşenler

1. **`BaseTool` & `ToolResult` Transferi:**
   * **Kaynak:** `yzta_kobi_ai/backend/app/agent/tools/base.py`
   * **Hedef:** `marketing-automation/src/agent/tools/base.py`
   * **Uyarlama:** `ToolResult` veri yapısı korunacak (`success`, `data`, `error`, `to_llm_text()`). `BaseTool` soyut sınıfında `name`, `description`, `parameters` ve `execute()` imzası yer alacak. `marketing-automation` senaryosunda tool'lar lokal veri inceleme (ör. campaign drill-down, historical baseline query) yapacağı için async/sync arayüz batch çalıştırmaya uygun hale getirilecek.

2. **`ToolRegistry` Transferi:**
   * **Kaynak:** `yzta_kobi_ai/backend/app/agent/tools/__init__.py`
   * **Hedef:** `marketing-automation/src/agent/tools/registry.py`
   * **Uyarlama:** Tool kaydı, isimle çağırma (`execute`), ve Gemini `google-genai` SDK `types.Tool(function_declarations=...)` formatında schema export eden `get_function_declarations()` metodları aynen taşınacak.

3. **`AgentOrchestrator` Transferi & Adaptasyonu:**
   * **Kaynak:** `yzta_kobi_ai/backend/app/agent/orchestrator.py`
   * **Hedef:** `marketing-automation/src/agent/runtime/orchestrator.py`
   * **Uyarlama:**
     * `yzta_kobi_ai` projesinde `orchestrator` çok turlu (multi-turn) sohbet (chat) ve Redis session geçmişi üzerinde çalışmaktadır.
     * `marketing-automation` projesinde ise **tek seferlik batch analizi (one-shot / bounded reasoning loop)** yapılacaktır.
     * Redis geçmiş yükleme/kaydetme adımları çıkarılacak, doğrudan `EvidenceDossier` verisi `system_instruction` ve `contents` olarak Gemini modeline verilecek. Bounded loop (max 3-5 iterasyon) tool ihtiyacı durumunda ReAct çalıştırıp finalde `BatchAnalysisResult` üretecektir.

### 4.2. KobiAI'den Kesinlikle ALINMAYACAK (Dışarıda Bırakılacak) Parçalar

| Bileşen (KobiAI) | Hariç Tutulma Nedeni |
|---|---|
| **PostgreSQL & SQLAlchemy Async** | `marketing-automation` statik/batch reklam verisi (CSV/API) işleyen stateless bir pipeline'dır. İlişkisel veritabanı gereksinimi yoktur. |
| **Redis & `ConversationMemory`** | Her pipeline çalıştırması anlık batch veridir. Oturum bazlı sohbet geçmişi saklanmaz. |
| **JWT Cookie Auth & Role Context (`AgentContext`)** | Web kullanıcı girişi veya yetkilendirme katmanı (Admin vs Customer) bulunmamaktadır. |
| **Next.js & Frontend API Route'ları** | Bu proje CLI, FastAPI ve Slack Block Kit odaklı arka plan otomasyonudur. |
| **Pending Action & Approval Flow** | E-ticaret sipariş/fiyat değiştirme onay akışı (`CreatePendingProductPriceUpdateTool` vb.) marketing automation kapsamı dışındadır. |

---

## 5. DOĞRULAMA (VERIFICATION)

FAZ 0 kurallarına tam uyum sağlanmıştır:
- `src/` ve `tests/` klasörlerindeki hiçbir Python kodu değiştirilmemiş, silinmemiş veya refactor edilmemiştir.
- `pyproject.toml` veya paket bağımlılıklarına dokunulmamıştır.
- Sistemde herhangi bir veritabanı veya altyapı komutu çalıştırılmamıştır.

`git status --porcelain` çıktısı sadece `audit_notes.md` dosyasının eklendiğini teyit edecektir.

---
**Rapor Sonu — FAZ 0 Başarıyla Tamamlandı.**
