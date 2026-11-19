"""Build numeric trends only from reports owned by the requested user."""

import math

from backend.core.healthcare_intelligence.backend.models import MedicalReport
from modules.health_trends.data_science.trend_statistics import compare_last_values


def build_trends(user):
    """Return the response payload used by the health trends page and API."""
    reports = list(
        MedicalReport.objects.filter(user=user)
        .order_by("created_at")
        .prefetch_related("analysis__findings")
    )
    grouped = {}
    for report in reports:
        if not hasattr(report, "analysis"):
            continue
        for finding in report.analysis.findings.all():
            if finding.numeric_value is None or not math.isfinite(float(finding.numeric_value)):
                continue
            key = finding.metric_key or finding.test_name.lower().replace(" ", "_")
            series = grouped.setdefault(
                key,
                {"metricKey": key, "testName": finding.test_name, "unit": finding.unit, "points": []},
            )
            series["points"].append({
                "reportId": str(report.id),
                "reportLabel": report.title or report.original_filename,
                "createdAt": report.created_at.isoformat(),
                "metricKey": key,
                "testName": finding.test_name,
                "value": finding.numeric_value,
                "unit": finding.unit,
                "status": finding.status,
            })

    insights = []
    metric_count = 0
    for series in grouped.values():
        points = series["points"]
        metric_count += len(points)
        latest = points[-1]
        statistics = compare_last_values([point["value"] for point in points])
        previous = points[-2] if len(points) > 1 else None
        delta = statistics["delta"]
        insights.append({
            "metricKey": series["metricKey"],
            "testName": series["testName"],
            "unit": series["unit"],
            "latestValue": statistics["latest"],
            "previousValue": statistics["previous"],
            "direction": statistics["direction"] if statistics["direction"] != "unknown" else "stable",
            "delta": delta,
            "deltaPercent": statistics["delta_percent"],
            "summary": (
                f"Latest value: {latest['value']:g} {series['unit']}."
                if not previous
                else f"Changed by {delta:g} {series['unit']} since the previous report."
            ),
            "status": latest["status"],
        })
    return {
        "reportsCount": len(reports),
        "storedMetricsCount": metric_count,
        "metricSeries": list(grouped.values()),
        "trendInsights": insights,
    }


def iter_csv_rows(user):
    """Yield normalized CSV rows for the user's numeric report findings."""
    reports = (
        MedicalReport.objects.filter(user=user)
        .order_by("created_at")
        .prefetch_related("analysis__findings")
    )
    for report in reports:
        if not hasattr(report, "analysis"):
            continue
        for finding in report.analysis.findings.all():
            if finding.numeric_value is not None and math.isfinite(float(finding.numeric_value)):
                yield (
                    finding.test_name,
                    report.title or report.original_filename,
                    report.created_at.isoformat(),
                    finding.numeric_value,
                    finding.unit,
                    finding.status,
                )
