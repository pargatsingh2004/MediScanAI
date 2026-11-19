"""Build unit-aware measurements comparisons from an ordered report collection."""

import math

from modules.report_comparison.data_science.metrics import calculate_change


def build_comparison(reports):
    """Return report summaries and metric deltas while preserving unit mismatches."""
    reports = list(reports)
    values = {}
    summaries = []
    for report in reports:
        summaries.append({
            "id": str(report.id),
            "title": report.title or report.original_filename,
            "createdAt": report.created_at.isoformat(),
            "reportStatus": report.status,
            "overallRisk": (report.insights_json or {}).get("overallRisk", "unknown"),
        })
        analysis = getattr(report, "analysis", None)
        if analysis is None:
            continue
        for finding in analysis.findings.all():
            if finding.numeric_value is None or not math.isfinite(float(finding.numeric_value)):
                continue
            key = finding.metric_key or finding.test_name.lower().replace(" ", "_")
            row = values.setdefault(key, {
                "metricKey": key,
                "testName": finding.test_name,
                "unit": finding.unit,
                "units": [],
                "values": [],
            })
            if finding.unit and finding.unit not in row["units"]:
                row["units"].append(finding.unit)
            row["values"].append({
                "reportId": str(report.id),
                "reportLabel": report.title or report.original_filename,
                "createdAt": report.created_at.isoformat(),
                "metricKey": key,
                "testName": finding.test_name,
                "value": finding.numeric_value,
                "unit": finding.unit,
                "status": finding.status,
            })

    metrics = []
    for row in values.values():
        ordered = row["values"]
        first_value, last_value = ordered[0]["value"], ordered[-1]["value"]
        row["hasUnitMismatch"] = len(row["units"]) > 1
        if row["hasUnitMismatch"]:
            row.update({
                "direction": "unit_mismatch",
                "delta": None,
                "deltaPercent": None,
                "summary": f"{row['testName']} values use different units across reports; a combined change was not calculated.",
            })
            row["values"] = [{
                **item,
                "differenceFromFirst": None,
                "differenceFromPrevious": None,
                "percentChangeFromFirst": None,
                "percentChangeFromPrevious": None,
            } for item in ordered]
        else:
            change = calculate_change(first_value, last_value, row["units"])
            delta = change["delta"]
            row.update({
                "direction": change["direction"],
                "delta": delta,
                "deltaPercent": change["delta_percent"],
                "summary": f"{row['testName']} changed by {delta:g} {row['unit']} across the selected reports.",
            })
            enriched = []
            previous_value = None
            for item in ordered:
                change_previous = item["value"] - previous_value if previous_value is not None else None
                enriched.append({
                    **item,
                    "differenceFromFirst": item["value"] - first_value,
                    "differenceFromPrevious": change_previous,
                    "percentChangeFromFirst": ((item["value"] - first_value) / abs(first_value) * 100) if first_value else None,
                    "percentChangeFromPrevious": (change_previous / abs(previous_value) * 100) if previous_value else None,
                })
                previous_value = item["value"]
            row["values"] = enriched
        metrics.append(row)
    return {"reports": summaries, "metrics": metrics}


def iter_csv_rows(reports):
    """Yield report findings for the comparison CSV download."""
    for report in reports:
        analysis = getattr(report, "analysis", None)
        if analysis is None:
            continue
        for finding in analysis.findings.all():
            yield (
                finding.test_name,
                report.title or report.original_filename,
                report.created_at.isoformat(),
                finding.measured_value,
                finding.unit,
                finding.reference_range,
                finding.status,
            )
