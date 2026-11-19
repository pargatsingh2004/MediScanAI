import re
from typing import List, Dict, Any, Optional

# Reference ranges for standard lab tests:
# Format: { "canonical_key": { "name": ..., "unit": ..., "min": ..., "max": ..., "critical_low": ..., "critical_high": ..., "specialty": ... } }
STANDARD_TEST_CATALOG = {
    "glucose_fasting": {
        "name": "Fasting Blood Sugar",
        "aliases": ["fasting blood sugar", "fbs", "glucose fasting", "fasting glucose", "blood glucose fasting"],
        "unit": "mg/dL",
        "min": 70.0,
        "max": 99.0,
        "critical_low": 50.0,
        "critical_high": 250.0,
        "specialty": "endocrinology",
    },
    "glucose_pp": {
        "name": "Post Prandial Blood Sugar",
        "aliases": ["post prandial", "ppbs", "glucose pp", "pp glucose", "2hr post prandial"],
        "unit": "mg/dL",
        "min": 70.0,
        "max": 140.0,
        "critical_low": 55.0,
        "critical_high": 300.0,
        "specialty": "endocrinology",
    },
    "glucose_random": {
        "name": "Random Blood Sugar",
        "aliases": ["random blood sugar", "rbs", "blood glucose random", "random glucose"],
        "unit": "mg/dL",
        "min": 70.0,
        "max": 140.0,
        "critical_low": 50.0,
        "critical_high": 280.0,
        "specialty": "endocrinology",
    },
    "hba1c": {
        "name": "HbA1c (Glycated Hemoglobin)",
        "aliases": ["hba1c", "glycated hemoglobin", "glycosylated hemoglobin", "a1c"],
        "unit": "%",
        "min": 4.0,
        "max": 5.6,
        "critical_low": 3.5,
        "critical_high": 10.0,
        "specialty": "endocrinology",
    },
    "hemoglobin": {
        "name": "Hemoglobin",
        "aliases": ["hemoglobin", "hb", "hgb"],
        "unit": "g/dL",
        "min": 12.0,
        "max": 16.5,
        "critical_low": 7.0,
        "critical_high": 20.0,
        "specialty": "general_medicine",
    },
    "rbc": {
        "name": "Total RBC Count",
        "aliases": ["rbc", "total rbc", "red blood cell count", "erythrocyte count"],
        "unit": "x10^6/uL",
        "min": 4.0,
        "max": 5.5,
        "critical_low": 2.5,
        "critical_high": 7.0,
        "specialty": "general_medicine",
    },
    "wbc": {
        "name": "Total WBC Count",
        "aliases": ["wbc", "total wbc", "total leukocyte count", "tlc", "white blood cells"],
        "unit": "cells/cumm",
        "min": 4000.0,
        "max": 11000.0,
        "critical_low": 2000.0,
        "critical_high": 25000.0,
        "specialty": "general_medicine",
    },
    "platelets": {
        "name": "Platelet Count",
        "aliases": ["platelet", "platelets", "platelet count", "thrombocyte count"],
        "unit": "x10^3/uL",
        "min": 150.0,
        "max": 450.0,
        "critical_low": 40.0,
        "critical_high": 800.0,
        "specialty": "general_medicine",
    },
    "cholesterol_total": {
        "name": "Total Cholesterol",
        "aliases": ["total cholesterol", "serum cholesterol", "cholesterol total"],
        "unit": "mg/dL",
        "min": 125.0,
        "max": 200.0,
        "critical_low": 90.0,
        "critical_high": 350.0,
        "specialty": "cardiology",
    },
    "triglycerides": {
        "name": "Triglycerides",
        "aliases": ["triglyceride", "triglycerides", "serum triglycerides", "tg"],
        "unit": "mg/dL",
        "min": 50.0,
        "max": 150.0,
        "critical_low": 30.0,
        "critical_high": 500.0,
        "specialty": "cardiology",
    },
    "hdl": {
        "name": "HDL Cholesterol",
        "aliases": ["hdl", "hdl cholesterol", "good cholesterol"],
        "unit": "mg/dL",
        "min": 40.0,
        "max": 60.0,
        "critical_low": 25.0,
        "critical_high": 100.0,
        "specialty": "cardiology",
    },
    "ldl": {
        "name": "LDL Cholesterol",
        "aliases": ["ldl", "ldl cholesterol", "bad cholesterol"],
        "unit": "mg/dL",
        "min": 50.0,
        "max": 100.0,
        "critical_low": 30.0,
        "critical_high": 220.0,
        "specialty": "cardiology",
    },
    "creatinine": {
        "name": "Serum Creatinine",
        "aliases": ["creatinine", "serum creatinine", "sr creatinine", "s creatinine"],
        "unit": "mg/dL",
        "min": 0.6,
        "max": 1.2,
        "critical_low": 0.3,
        "critical_high": 4.0,
        "specialty": "nephrology",
    },
    "urea": {
        "name": "Blood Urea",
        "aliases": ["blood urea", "urea", "bun", "blood urea nitrogen"],
        "unit": "mg/dL",
        "min": 15.0,
        "max": 40.0,
        "critical_low": 8.0,
        "critical_high": 100.0,
        "specialty": "nephrology",
    },
    "uric_acid": {
        "name": "Uric Acid",
        "aliases": ["uric acid", "serum uric acid"],
        "unit": "mg/dL",
        "min": 3.5,
        "max": 7.2,
        "critical_low": 2.0,
        "critical_high": 12.0,
        "specialty": "orthopedics",
    },
    "sgpt": {
        "name": "SGPT (ALT)",
        "aliases": ["sgpt", "alt", "alanine aminotransferase", "alanine transaminase"],
        "unit": "U/L",
        "min": 7.0,
        "max": 45.0,
        "critical_low": 2.0,
        "critical_high": 250.0,
        "specialty": "gastroenterology",
    },
    "sgot": {
        "name": "SGOT (AST)",
        "aliases": ["sgot", "ast", "aspartate aminotransferase", "aspartate transaminase"],
        "unit": "U/L",
        "min": 8.0,
        "max": 40.0,
        "critical_low": 2.0,
        "critical_high": 250.0,
        "specialty": "gastroenterology",
    },
    "bilirubin_total": {
        "name": "Total Bilirubin",
        "aliases": ["bilirubin total", "total bilirubin", "serum bilirubin total"],
        "unit": "mg/dL",
        "min": 0.2,
        "max": 1.2,
        "critical_low": 0.05,
        "critical_high": 5.0,
        "specialty": "gastroenterology",
    },
    "tsh": {
        "name": "TSH (Thyroid Stimulating Hormone)",
        "aliases": ["tsh", "thyroid stimulating hormone", "tsh ultra"],
        "unit": "uIU/mL",
        "min": 0.4,
        "max": 4.5,
        "critical_low": 0.05,
        "critical_high": 20.0,
        "specialty": "endocrinology",
    },
    "vitamin_d": {
        "name": "Vitamin D (25-OH)",
        "aliases": ["vitamin d", "25 oh vitamin d", "vit d", "cholecalciferol"],
        "unit": "ng/mL",
        "min": 30.0,
        "max": 100.0,
        "critical_low": 10.0,
        "critical_high": 150.0,
        "specialty": "orthopedics",
    },
    "vitamin_b12": {
        "name": "Vitamin B12",
        "aliases": ["vitamin b12", "vit b12", "cyanocobalamin"],
        "unit": "pg/mL",
        "min": 211.0,
        "max": 911.0,
        "critical_low": 100.0,
        "critical_high": 1500.0,
        "specialty": "neurology",
    },
    "blood_pressure_systolic": {
        "name": "Blood Pressure (Systolic)",
        "aliases": ["systolic", "systolic bp", "bp systolic"],
        "unit": "mmHg",
        "min": 90.0,
        "max": 120.0,
        "critical_low": 75.0,
        "critical_high": 180.0,
        "specialty": "cardiology",
    },
    "blood_pressure_diastolic": {
        "name": "Blood Pressure (Diastolic)",
        "aliases": ["diastolic", "diastolic bp", "bp diastolic"],
        "unit": "mmHg",
        "min": 60.0,
        "max": 80.0,
        "critical_low": 45.0,
        "critical_high": 120.0,
        "specialty": "cardiology",
    },
}


class MedicalNLP:
    """Extracts, normalizes, and triages medical biomarkers and lab results."""

    @classmethod
    def extract_findings_from_text(cls, text: str) -> List[Dict[str, Any]]:
        """Extract structured medical findings from raw/cleaned report text."""
        findings = []
        lines = text.splitlines()

        for key, meta in STANDARD_TEST_CATALOG.items():
            # Check all aliases for this test
            for alias in meta["aliases"]:
                # Pattern: alias followed by optional separator (: / -), number, and optional unit
                pattern = rf"(?i)\b{re.escape(alias)}\b\s*[:\-=]?\s*([<>~]?\s*\d+(?:\.\d+)?)"
                match = re.search(pattern, text)
                if match:
                    raw_val_str = match.group(1).replace(" ", "").replace("~", "")
                    clean_num_match = re.search(r"(\d+(?:\.\d+)?)", raw_val_str)
                    if clean_num_match:
                        num_val = float(clean_num_match.group(1))
                        status, severity, note = cls.evaluate_value(num_val, meta)
                        findings.append({
                            "metric_key": key,
                            "test_name": meta["name"],
                            "measured_value": str(num_val),
                            "numeric_value": num_val,
                            "unit": meta["unit"],
                            "reference_range": f"{meta['min']} - {meta['max']} {meta['unit']}",
                            "status": status,
                            "severity": severity,
                            "clinical_significance": note,
                            "specialty_code": meta["specialty"],
                        })
                        break  # Found match for this test, don't repeat for aliases

        # Also search for combined BP e.g., 140/90 mmHg
        bp_match = re.search(r"(?i)\b(?:bp|blood\s*pressure)\b\s*[:\-=]?\s*(\d{2,3})\s*[\/\-]\s*(\d{2,3})", text)
        if bp_match:
            sys_val = float(bp_match.group(1))
            dia_val = float(bp_match.group(2))
            sys_meta = STANDARD_TEST_CATALOG["blood_pressure_systolic"]
            dia_meta = STANDARD_TEST_CATALOG["blood_pressure_diastolic"]
            sys_status, sys_sev, sys_note = cls.evaluate_value(sys_val, sys_meta)
            dia_status, dia_sev, dia_note = cls.evaluate_value(dia_val, dia_meta)

            findings.append({
                "metric_key": "blood_pressure_systolic",
                "test_name": "Systolic Blood Pressure",
                "measured_value": str(sys_val),
                "numeric_value": sys_val,
                "unit": "mmHg",
                "reference_range": "90 - 120 mmHg",
                "status": sys_status,
                "severity": sys_sev,
                "clinical_significance": f"Systolic reading: {sys_note}",
                "specialty_code": "cardiology",
            })
            findings.append({
                "metric_key": "blood_pressure_diastolic",
                "test_name": "Diastolic Blood Pressure",
                "measured_value": str(dia_val),
                "numeric_value": dia_val,
                "unit": "mmHg",
                "reference_range": "60 - 80 mmHg",
                "status": dia_status,
                "severity": dia_sev,
                "clinical_significance": f"Diastolic reading: {dia_note}",
                "specialty_code": "cardiology",
            })

        return findings

    @classmethod
    def evaluate_value(cls, value: float, meta: Dict[str, Any]) -> tuple:
        """Determines status, severity, and explanatory note for a measured value."""
        min_v = meta["min"]
        max_v = meta["max"]
        crit_low = meta.get("critical_low", min_v * 0.6)
        crit_high = meta.get("critical_high", max_v * 1.5)

        if value < crit_low:
            return (
                "critical",
                "critical",
                f"Critically below normal interval ({min_v} - {max_v} {meta['unit']}). Requires immediate medical attention.",
            )
        elif value > crit_high:
            return (
                "critical",
                "critical",
                f"Critically elevated above normal interval ({min_v} - {max_v} {meta['unit']}). Requires immediate medical attention.",
            )
        elif value < min_v:
            diff = (min_v - value) / min_v
            severity = "high" if diff > 0.2 else "moderate"
            return (
                "low",
                severity,
                f"Below normal baseline ({min_v} - {max_v} {meta['unit']}). Follow up with physician.",
            )
        elif value > max_v:
            diff = (value - max_v) / max_v
            severity = "high" if diff > 0.2 else "moderate"
            return (
                "high",
                severity,
                f"Elevated above normal baseline ({min_v} - {max_v} {meta['unit']}). Follow up with physician.",
            )
        else:
            return (
                "normal",
                "low",
                f"Within healthy reference limits ({min_v} - {max_v} {meta['unit']}).",
            )

    @classmethod
    def analyze_report_findings(cls, findings: List[Dict[str, Any]], raw_text: str = "") -> Dict[str, Any]:
        """Aggregate findings into overall risk, conditions, precautions, and questions."""
        abnormal_findings = [f for f in findings if f["status"] != "normal"]
        critical_findings = [f for f in findings if f["severity"] == "critical"]
        high_findings = [f for f in findings if f["severity"] == "high"]

        # Determine overall risk
        if critical_findings:
            overall_risk = "critical"
            requires_urgent_care = True
            urgency_reason = f"Urgent: {len(critical_findings)} biomarker(s) indicate critical threshold breaches ({', '.join(f['test_name'] for f in critical_findings[:3])})."
        elif len(high_findings) >= 2 or any(f["status"] == "high" for f in findings if f["metric_key"] in ["glucose_fasting", "hba1c", "blood_pressure_systolic"]):
            overall_risk = "high"
            requires_urgent_care = False
            urgency_reason = "Multiple biomarkers exceed high clinical tolerance levels. Prompt specialist consultation recommended."
        elif abnormal_findings:
            overall_risk = "moderate"
            requires_urgent_care = False
            urgency_reason = ""
        else:
            overall_risk = "low"
            requires_urgent_care = False
            urgency_reason = ""

        # Detected conditions summary
        conditions = []
        specialty_signals = set()
        for f in abnormal_findings:
            specialty_signals.add(f.get("specialty_code"))
            if f["metric_key"] in ["glucose_fasting", "glucose_pp", "hba1c"]:
                conditions.append("Elevated Blood Glucose / Hyperglycemic Pattern")
            elif f["metric_key"] in ["blood_pressure_systolic", "blood_pressure_diastolic"]:
                conditions.append("Elevated Blood Pressure / Prehypertensive Pattern")
            elif f["metric_key"] in ["cholesterol_total", "triglycerides", "ldl"]:
                conditions.append("Dyslipidemia / Elevated Lipid Profile")
            elif f["metric_key"] in ["creatinine", "urea"]:
                conditions.append("Renal Parameter Alteration")
            elif f["metric_key"] in ["sgpt", "sgot", "bilirubin_total"]:
                conditions.append("Hepatic Enzyme Alteration")
            elif f["metric_key"] == "hemoglobin" and f["status"] == "low":
                conditions.append("Low Hemoglobin / Anemia Profile")
            elif f["metric_key"] == "vitamin_d" and f["status"] == "low":
                conditions.append("Vitamin D Deficiency")
            elif f["metric_key"] == "tsh" and f["status"] == "high":
                conditions.append("Elevated TSH / Hypothyroid Pattern")

        conditions = list(dict.fromkeys(conditions))  # Deduplicate

        # Summary
        if not findings:
            summary = "Document processed successfully. No quantitative standard laboratory biomarkers were recognized in the uploaded document. Please verify image clarity or document format."
        elif not abnormal_findings:
            summary = f"All {len(findings)} detected biomarkers are within healthy reference intervals. Continue maintaining a balanced lifestyle and regular preventive check-ups."
        else:
            summary = f"Analyzed {len(findings)} biomarker(s). Found {len(abnormal_findings)} metric(s) outside normal limits ({', '.join(f['test_name'] for f in abnormal_findings[:4])}). Specialty review is recommended."

        # Precautions
        precautions = [
            "Maintain adequate hydration throughout the day unless restricted by your doctor.",
            "Schedule a clinical review with a qualified medical doctor before altering any medications or treatments.",
            "Avoid strenuous exertion or heavy meals immediately prior to follow-up fasting tests.",
            "Keep a log of current symptoms, blood pressure, or blood glucose measurements if monitored at home.",
        ]

        # Suggested questions
        questions = [
            "What do these specific biomarker values mean in the context of my current health history?",
            "Are follow-up confirmatory tests recommended within 2 to 4 weeks?",
            "What dietary, exercise, or lifestyle modifications would best support my recovery?",
            "Are there any prescription medications or supplements that I should review with you?",
        ]

        return {
            "summary": summary,
            "findings": findings,
            "abnormal_count": len(abnormal_findings),
            "detected_conditions": conditions,
            "precautions": precautions,
            "suggested_questions": questions,
            "overall_risk": overall_risk,
            "requires_urgent_care": requires_urgent_care,
            "urgency_reason": urgency_reason,
            "specialty_signals": list(specialty_signals),
            "confidence_score": 92.0 if len(findings) >= 3 else 78.0,
        }
