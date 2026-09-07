"""JSON exporter for EvidenceDossier statistical metrics and anomaly candidates."""

import json
import math
from pathlib import Path

from src.domain.models.evidence_dossier import (
    CampaignEvidence,
    EvidenceDossier,
    MetricEvidence,
)
from src.infrastructure.reporting.io_utils import safe_write_text


def _sanitize_float(val: float | None) -> float | None:
    """Sanitize float value converting NaN, Infinity, or None to None for clean JSON output."""
    if val is None:
        return None
    if math.isnan(val) or math.isinf(val):
        return None
    return val


class JsonAnomalyExporter:
    """Serializes EvidenceDossier and statistical metrics into clean, indented JSON."""

    def _metric_to_dict(self, metric: MetricEvidence) -> dict[str, str | float | bool | None]:
        """Serialize a MetricEvidence object into a clean dictionary."""
        return {
            "metric_name": metric.metric_name,
            "current_value": _sanitize_float(metric.current_value),
            "baseline_value": _sanitize_float(metric.baseline_value),
            "delta_pct": _sanitize_float(metric.delta_pct),
            "z_score": _sanitize_float(metric.z_score),
            "is_anomaly": metric.is_anomaly,
        }

    def _campaign_to_dict(self, campaign: CampaignEvidence) -> dict[str, object]:
        """Serialize a CampaignEvidence object into a clean dictionary."""
        metrics_dict: dict[str, dict[str, str | float | bool | None]] = {
            m_name: self._metric_to_dict(m_ev) for m_name, m_ev in campaign.metrics.items()
        }

        signals_list: list[dict[str, str | float | bool | None]] = []
        for signal in campaign.data_quality_signals:
            sig_type = (
                signal.signal_type.value
                if hasattr(signal.signal_type, "value")
                else str(signal.signal_type)
            )
            signals_list.append(
                {
                    "signal_type": sig_type,
                    "is_triggered": signal.is_triggered,
                    "metric_name": signal.metric_name,
                    "current_value": _sanitize_float(signal.current_value),
                    "baseline_value": _sanitize_float(signal.baseline_value),
                    "delta_pct": _sanitize_float(signal.delta_pct),
                    "factual_statement": signal.factual_statement,
                }
            )

        return {
            "campaign_id": campaign.campaign_id,
            "campaign_name": campaign.campaign_name,
            "platform": campaign.platform,
            "account_id": campaign.account_id,
            "country": campaign.country,
            "spend": _sanitize_float(campaign.spend) or 0.0,
            "financial_impact_score": _sanitize_float(campaign.financial_impact_score) or 0.0,
            "metrics": metrics_dict,
            "data_quality_signals": signals_list,
        }

    def _to_dict(self, dossier: EvidenceDossier) -> dict[str, object]:
        """Convert EvidenceDossier into a serializable dictionary structure."""
        campaigns_list = [
            self._campaign_to_dict(campaign) for campaign in dossier.top_campaign_evidence
        ]

        return {
            "target_date": dossier.target_date,
            "baseline_window": dossier.baseline_window,
            "total_anomalies_detected": dossier.total_anomalies_detected,
            "total_campaigns_impacted": dossier.total_campaigns_impacted,
            "top_campaign_evidence": campaigns_list,
            "campaigns": campaigns_list,
        }

    def render(self, dossier: EvidenceDossier) -> str:
        """Render EvidenceDossier as formatted JSON string with indent=2.

        Args:
            dossier: EvidenceDossier containing statistical metrics and signals.

        Returns:
            Indented JSON string representation.
        """
        data = self._to_dict(dossier)
        return json.dumps(data, indent=2, ensure_ascii=False)

    def export_to_file(self, dossier: EvidenceDossier, output_path: str | Path) -> str:
        """Render EvidenceDossier as JSON and save atomically to disk.

        Args:
            dossier: EvidenceDossier instance.
            output_path: Target file path for the JSON deliverable.

        Returns:
            The written JSON string content.
        """
        content = self.render(dossier)
        safe_write_text(output_path, content, encoding="utf-8")
        return content


# Alias for backward compatibility / alternate naming
AnomalyJsonExporter = JsonAnomalyExporter
