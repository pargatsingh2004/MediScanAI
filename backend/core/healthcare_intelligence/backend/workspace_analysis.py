"""Shared report analysis helpers for the Django workspace and guest preview."""

import hashlib
import json
import logging
import re

import requests
from django.conf import settings

from .models import Specialty
from .services.medical_nlp import MedicalNLP
from .services.specialty_recommender import SpecialtyRecommender

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = {"en", "hi", "hinglish"}
MEDICINE_NAMES = (
    "paracetamol", "acetaminophen", "ibuprofen", "aspirin", "metformin",
    "atorvastatin", "amlodipine", "losartan", "omeprazole", "pantoprazole",
    "azithromycin", "amoxicillin", "cetirizine", "levothyroxine", "insulin",
    "vitamin d", "vitamin b12", "folic acid", "iron", "warfarin", "clopidogrel",
    "prednisolone", "salbutamol", "montelukast", "ondansetron", "ceftriaxone",
    "telmisartan", "olmesartan", "rosuvastatin", "glycomet", "glucophage", "amlong",
    "thyronorm", "eltroxin", "crocin", "dolo",
)
MEDICINE_INFO = {
    "metformin": {
        "aliases": ("metformin", "glycomet", "glucophage"), "category": "Antidiabetic",
        "summary": "Commonly used to help control blood sugar in type 2 diabetes.",
        "uses": ["Type 2 diabetes", "Insulin resistance"],
        "effects": ["Nausea", "Loose stools", "Stomach discomfort"],
        "precautions": ["Take with food if prescribed that way", "Discuss kidney issues with your doctor"],
    },
    "amlodipine": {
        "aliases": ("amlodipine", "amlong"), "category": "Blood pressure medicine",
        "summary": "Often used to lower blood pressure and reduce heart strain.",
        "uses": ["High blood pressure", "Angina"],
        "effects": ["Ankle swelling", "Headache", "Flushing"],
        "precautions": ["Stand slowly if you feel dizzy", "Monitor blood pressure regularly"],
    },
    "arb": {
        "aliases": ("telmisartan", "losartan", "olmesartan"), "category": "ARB antihypertensive",
        "summary": "Used to help control blood pressure and support kidney protection in some patients.",
        "uses": ["High blood pressure", "Kidney protection in selected patients"],
        "effects": ["Dizziness", "Low blood pressure", "Raised potassium"],
        "precautions": ["Check blood pressure and kidney tests as advised", "Review with a doctor if pregnant or planning pregnancy"],
    },
    "levothyroxine": {
        "aliases": ("levothyroxine", "thyronorm", "eltroxin"), "category": "Thyroid hormone",
        "summary": "Usually prescribed to replace low thyroid hormone levels.",
        "uses": ["Hypothyroidism"],
        "effects": ["Palpitations if dose is high", "Sweating", "Restlessness"],
        "precautions": ["Often taken on an empty stomach if prescribed", "Thyroid levels may need repeat testing"],
    },
    "statin": {
        "aliases": ("atorvastatin", "rosuvastatin"), "category": "Cholesterol-lowering medicine",
        "summary": "Used to lower cholesterol and reduce cardiovascular risk.",
        "uses": ["High cholesterol", "Cardiovascular risk reduction"],
        "effects": ["Muscle aches", "Upset stomach", "Abnormal liver tests"],
        "precautions": ["Report severe muscle pain", "Liver tests may need monitoring"],
    },
    "paracetamol": {
        "aliases": ("paracetamol", "acetaminophen", "crocin", "dolo"), "category": "Pain and fever relief",
        "summary": "Used for fever and mild to moderate pain relief.",
        "uses": ["Fever", "Headache", "Body ache"],
        "effects": ["Usually well tolerated in correct doses", "Liver toxicity in overdose"],
        "precautions": ["Avoid exceeding the prescribed dose", "Check for other combination products containing paracetamol"],
    },
}


def normalize_language(value):
    language = str(value or "en").strip().lower()
    return language if language in SUPPORTED_LANGUAGES else "en"


def _openai_json(system_prompt, user_prompt, model=None):
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        return None
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model or getattr(settings, "OPENAI_ANALYSIS_MODEL", "gpt-4.1-mini"),
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=45,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception:
        logger.exception("AI report analysis request failed; using local analysis")
        return None


def _openai_text(system_prompt, user_prompt, model=None):
    api_key = getattr(settings, "OPENAI_API_KEY", "")
    if not api_key:
        return None
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model or getattr(settings, "OPENAI_CHAT_MODEL", "gpt-4.1-mini"),
                "temperature": 0.3,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=45,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        logger.exception("AI response request failed; using local response")
        return None


def _local_medicines(text):
    lines = text.splitlines()
    lowered = text.lower()
    medicines = []
    for name in MEDICINE_NAMES:
        if re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", lowered):
            line = next((value for value in lines if re.search(rf"(?<![a-z]){re.escape(name)}(?![a-z])", value, re.I)), "")
            dose_match = re.search(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|μg|ug|ml|g|iu|units?)\b", line, re.I)
            frequency_match = re.search(r"\b(?:once daily|twice daily|three times daily|once a day|twice a day|morning|at night|before breakfast|after food|od|bd|bid|tds|tid|hs)\b", line, re.I)
            medicines.append({
                "name": name.title(),
                "dosage": dose_match.group(0).strip() if dose_match else "",
                "frequency": frequency_match.group(0).strip() if frequency_match else "",
                "purpose": "Medicine name recognized in the report.",
                "notes": "Confirm the dose and instructions with your clinician or pharmacist.",
            })
    return medicines[:12]


def _medicine_key(name):
    normalized = re.sub(r"[^a-z0-9]+", " ", str(name).lower()).strip()
    for key, item in MEDICINE_INFO.items():
        if any(alias in normalized for alias in item["aliases"]):
            return key
    return normalized.split(" ")[0] if normalized else ""


def _build_medicine_details(medicines):
    result = []
    for medicine in medicines:
        key = _medicine_key(medicine.get("name", ""))
        item = MEDICINE_INFO.get(key)
        if item:
            result.append({
                "name": medicine.get("name", ""), "category": item["category"], "summary": item["summary"],
                "uses": item["uses"], "commonSideEffects": item["effects"], "precautions": item["precautions"],
                "interactionWarnings": [], "timingAdvice": "", "source": "knowledge-base",
            })
        else:
            result.append({
                "name": medicine.get("name", ""), "category": "Medication",
                "summary": "Specific medicine details were not found in the built-in knowledge base. Confirm the name and review the original prescription.",
                "uses": [medicine.get("purpose") or "Use not clearly extracted from the report."],
                "commonSideEffects": ["Side effects depend on the exact drug and dose."],
                "precautions": ["Verify the medicine name with a pharmacist or doctor before acting on this summary."],
                "interactionWarnings": [], "timingAdvice": "", "source": "heuristic",
            })
    return result


def _build_interaction_checks(medicines, findings):
    keys = [_medicine_key(item.get("name", "")) for item in medicines]
    tags = set()
    for key in keys:
        if key == "metformin": tags.add("blood-sugar")
        if key == "amlodipine": tags.add("antihypertensive")
        if key == "arb": tags.update(("antihypertensive", "arb"))
    abnormal = {item["metric_key"]: item for item in findings if item["status"] != "normal"}
    checks = []
    if "blood-sugar" in tags and "creatinine" in abnormal:
        checks.append({
            "title": "Kidney function caution with diabetes medicine",
            "medicines": [item["name"] for item in medicines if _medicine_key(item.get("name", "")) == "metformin"],
            "severity": "high" if abnormal["creatinine"]["status"] == "high" else "moderate",
            "explanation": "When creatinine is above range, medicines such as metformin may need clinician review for dose safety.",
            "recommendation": "Do not stop the medicine on your own, but review kidney function and the prescription promptly with your clinician.",
        })
    if "arb" in tags and abnormal.get("potassium", {}).get("status") == "high":
        checks.append({
            "title": "Potassium-related interaction caution",
            "medicines": [item["name"] for item in medicines if _medicine_key(item.get("name", "")) == "arb"],
            "severity": "high",
            "explanation": "Some blood-pressure medicines in the ARB family can worsen high potassium and need closer monitoring.",
            "recommendation": "Review the medicine list, repeat potassium if advised, and avoid self-adding supplements without medical advice.",
        })
    blood_pressure_medicines = [item["name"] for item in medicines if _medicine_key(item.get("name", "")) in {"amlodipine", "arb"}]
    if len(blood_pressure_medicines) >= 2:
        checks.append({
            "title": "Multiple blood-pressure medicines detected", "medicines": blood_pressure_medicines,
            "severity": "moderate",
            "explanation": "Using more than one blood-pressure medicine can be intentional, but dizziness or low blood pressure is worth monitoring.",
            "recommendation": "Take them exactly as prescribed and discuss fainting, weakness, or very low readings with your clinician.",
        })
    if not checks and len(medicines) > 1:
        checks.append({
            "title": "No major built-in interaction flag", "medicines": [item["name"] for item in medicines],
            "severity": "low",
            "explanation": "No high-risk interaction was detected by the limited built-in rule set for the extracted medicines.",
            "recommendation": "OCR can miss brand names or strengths, so verify the exact prescription with a pharmacist or clinician.",
        })
    return checks[:4]


def _build_medicine_reminders(medicines):
    reminders = []
    for medicine in medicines[:6]:
        frequency = str(medicine.get("frequency", "")).strip()
        normalized = frequency.lower()
        if any(token in normalized for token in ("twice", "bd", "bid")):
            schedule = "Morning and evening"
        elif any(token in normalized for token in ("thrice", "tds", "three")):
            schedule = "Morning, afternoon, and night"
        elif any(token in normalized for token in ("night", "hs", "bed")):
            schedule = "At night"
        elif "morning" in normalized:
            schedule = "Every morning"
        elif any(token in normalized for token in ("once", "daily", "od")):
            schedule = "Once daily at a fixed time"
        else:
            schedule = "Follow the prescription timing"
        key = _medicine_key(medicine.get("name", ""))
        instruction = {
            "metformin": "Take with food if the prescription says so; follow the clinician's written instructions.",
            "levothyroxine": "Follow the prescribed timing; some prescriptions specify taking it on an empty stomach.",
            "amlodipine": "Follow the prescription and discuss dizziness or low blood pressure with your clinician.",
            "arb": "Follow the prescription and review kidney function and potassium as advised.",
            "statin": "Follow the prescribed timing; ask your clinician if you have severe muscle pain.",
            "paracetamol": "Use only as prescribed and check other medicines for the same active ingredient.",
        }.get(key, "Use a phone reminder or pill organizer to keep the prescribed schedule consistent.")
        reminders.append({"medicineName": medicine.get("name", ""), "dosage": medicine.get("dosage", ""), "schedule": schedule, "instructions": instruction})
    return reminders


def _build_lifestyle_recommendations(findings):
    keys = {item["metric_key"] for item in findings if item["status"] != "normal"}
    recommendations = []
    if keys.intersection({"glucose_fasting", "glucose_pp", "glucose_random", "hba1c"}):
        recommendations.extend([
            {"title": "Diet focus", "category": "diet", "details": "Favor high-fiber meals, reduce sugary drinks and refined snacks, and keep meal timing consistent if your clinician has advised diabetes monitoring."},
            {"title": "Activity habit", "category": "activity", "details": "A routine daily walk or other clinician-approved activity can support sugar control and weight management."},
        ])
    if "hemoglobin" in keys:
        recommendations.append({"title": "Iron-supportive meals", "category": "diet", "details": "Discuss iron-rich foods, protein intake, and whether B12 or folate testing is needed instead of self-starting supplements."})
    if "tsh" in keys:
        recommendations.append({"title": "Monitoring plan", "category": "monitoring", "details": "Track fatigue, weight change, or temperature intolerance and review repeat thyroid testing with your clinician."})
    if keys.intersection({"blood_pressure_systolic", "blood_pressure_diastolic", "cholesterol_total", "triglycerides", "ldl"}):
        recommendations.append({"title": "Heart-friendly routine", "category": "diet", "details": "Limit extra salt and heavily processed foods, and keep a home blood-pressure log if advised."})
    if "creatinine" in keys:
        recommendations.append({"title": "Hydration and medicine review", "category": "hydration", "details": "Stay hydrated unless a doctor has restricted fluids, and review painkillers or supplements before using them."})
    if not recommendations:
        recommendations.append({"title": "Balanced routine", "category": "activity", "details": "Keep meals balanced, stay active within your comfort level, and review symptoms rather than relying only on an automated summary."})
    return recommendations[:4]


def _local_analysis(text, findings, summary, language):
    medicines = _local_medicines(text)
    conditions = [
        {
            "name": name,
            "confidence": "medium",
            "evidence": ", ".join(item["test_name"] for item in findings if item["status"] != "normal")[:500],
            "explanation": "This is a pattern in report values, not a confirmed diagnosis.",
        }
        for name in summary["detected_conditions"]
    ]
    tests = [
        {
            "name": item["test_name"],
            "value": f'{item["measured_value"]} {item["unit"]}'.strip(),
            "unit": item["unit"],
            "referenceRange": item["reference_range"],
            "status": item["status"],
            "explanation": item["clinical_significance"],
        }
        for item in findings
    ]
    safety_flags = []
    if summary["requires_urgent_care"]:
        safety_flags.append(summary["urgency_reason"] or "A critical value was detected.")
    if not findings:
        safety_flags.append("No standard laboratory values were recognized. Review the OCR text before relying on this preview.")
    return {
        "documentType": "Prescription or medical report",
        "overview": summary["summary"],
        "plainLanguageSummary": summary["summary"],
        "possibleConditions": conditions,
        "medicines": medicines,
        "testValues": tests,
        "precautions": summary["precautions"],
        "followUpQuestions": summary["suggested_questions"],
        "safetyFlags": safety_flags,
        "preferredLanguage": language,
    }


def analyze_extracted_report(text, raw_text="", filename="Report", file_bytes=b"", language="en"):
    """Build the report and insights shapes used by the original workspace UI."""
    language = normalize_language(language)
    findings = MedicalNLP.extract_findings_from_text(text)
    summary = MedicalNLP.analyze_report_findings(findings, raw_text=raw_text or text)
    analysis = _local_analysis(text, findings, summary, language)

    # Use the configured model when available. The local analyzer remains a complete fallback.
    ai_result = _openai_json(
        "You explain medical reports for patients. Return JSON only with documentType, overview, plainLanguageSummary, possibleConditions, medicines, precautions, followUpQuestions, safetyFlags, and an insights object. Ground every statement in the supplied report. Do not diagnose or invent values. Keep extracted testValues from the application's measured data unchanged. Only include medicines and interactions supported by the report; never recommend a dose change. Write patient-facing text in the requested language (en, hi, or hinglish). In insights, include riskPredictions, medicineDetails, interactionChecks, lifestyleRecommendations, medicineReminders, emergencyAssessment, doctorRecommendations, and generalGuidance when supported. Use the application's normalized test values and reference ranges as the source of truth.",
        json.dumps({"language": language, "filename": filename, "reportText": text[:18000], "measuredValues": analysis["testValues"]}, ensure_ascii=False),
    )
    if isinstance(ai_result, dict):
        for key in ("documentType", "overview", "plainLanguageSummary", "possibleConditions", "medicines", "precautions", "followUpQuestions", "safetyFlags"):
            if key in ai_result and isinstance(ai_result[key], (str, list)):
                analysis[key] = ai_result[key]
        analysis["testValues"] = _local_analysis(text, findings, summary, language)["testValues"]
        analysis["preferredLanguage"] = language

    risk = summary["overall_risk"]
    abnormal = [item for item in findings if item["status"] != "normal"]
    abnormal_findings = [
        {
            "name": item["test_name"],
            "value": f'{item["measured_value"]} {item["unit"]}'.strip(),
            "referenceRange": item["reference_range"],
            "status": item["status"],
            "severity": item["severity"],
            "explanation": item["clinical_significance"],
        }
        for item in abnormal
    ]
    alerts = [
        {
            "title": item["test_name"],
            "severity": item["severity"],
            "reason": item["clinical_significance"],
            "recommendation": "Discuss this result with a qualified healthcare professional.",
        }
        for item in abnormal
    ]
    test_evaluations = [
        {
            "name": item["test_name"],
            "metricKey": item["metric_key"],
            "value": item["measured_value"],
            "numericValue": item["numeric_value"],
            "unit": item["unit"],
            "referenceRange": item["reference_range"],
            "status": item["status"],
            "severity": item["severity"],
            "isAbnormal": item["status"] != "normal",
            "explanation": item["clinical_significance"],
            "normalRangeSummary": item["reference_range"],
        }
        for item in findings
    ]
    risk_predictions = [
        {
            "condition": condition["name"],
            "probability": 0.7 if risk in {"high", "critical"} else 0.45,
            "severity": risk,
            "rationale": [condition["evidence"]] if condition["evidence"] else [],
            "preventiveSteps": ["Review this pattern with a qualified clinician."],
            "suggestedSpecialist": "General Medicine",
        }
        for condition in analysis["possibleConditions"]
        if isinstance(condition, dict)
    ]
    medicine_entries = [item for item in analysis["medicines"] if isinstance(item, dict)]
    interaction_checks = _build_interaction_checks(medicine_entries, findings)
    medicine_details = _build_medicine_details(medicine_entries)
    medicine_reminders = _build_medicine_reminders(medicine_entries)
    lifestyle_recommendations = _build_lifestyle_recommendations(findings)
    for detail in medicine_details:
        key = _medicine_key(detail["name"])
        detail["interactionWarnings"] = [
            f'{check["title"]}: {check["recommendation"]}'
            for check in interaction_checks
            if check["severity"] != "low" and any(_medicine_key(name) == key for name in check["medicines"])
        ]
        reminder = next((item for item in medicine_reminders if _medicine_key(item["medicineName"]) == key), None)
        detail["timingAdvice"] = reminder["instructions"] if reminder else ""
        detail["precautions"] = list(dict.fromkeys(detail["precautions"] + detail["interactionWarnings"] + ([detail["timingAdvice"]] if detail["timingAdvice"] else [])))
    specialties = SpecialtyRecommender.recommend_specialties(text=text, findings=findings, top_k=3)
    doctor_recommendations = [
        {
            "specialist": item.get("name", item.get("specialty", "General Medicine")),
            "priority": risk if risk in {"moderate", "high", "critical"} else "low",
            "reason": item.get("reason", "Suggested from the report pattern; confirm with your clinician."),
        }
        for item in specialties
    ]
    content_hash = hashlib.sha256(file_bytes).hexdigest() if file_bytes else ""
    ocr_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    analysis_hash = hashlib.sha256(json.dumps(analysis, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    proof = {
        "algorithm": "SHA-256",
        "issuedAt": "",
        "documentHash": content_hash,
        "ocrHash": ocr_hash,
        "analysisHash": analysis_hash,
        "blockHash": hashlib.sha256(f"{content_hash}:{ocr_hash}:{analysis_hash}".encode()).hexdigest(),
        "verificationMessage": "Hashes help verify file and analysis integrity; they do not verify the medical correctness of the report.",
    }
    insights = {
        "overallRisk": risk,
        "summary": analysis["plainLanguageSummary"],
        "abnormalFindings": abnormal_findings,
        "alerts": alerts,
        "generalGuidance": summary["precautions"],
        "safetyNotice": "This tool supports understanding and does not replace a licensed clinician's advice.",
        "preferredLanguage": language,
        "testEvaluations": test_evaluations,
        "riskPredictions": risk_predictions,
        "medicineDetails": medicine_details,
        "interactionChecks": interaction_checks,
        "lifestyleRecommendations": lifestyle_recommendations,
        "medicineReminders": medicine_reminders,
        "emergencyAssessment": {
            "requiresUrgentCare": summary["requires_urgent_care"],
            "severity": risk,
            "headline": "Urgent clinical review suggested" if summary["requires_urgent_care"] else "No urgent pattern detected by this screening",
            "action": summary["urgency_reason"] or "Seek care promptly if you have severe or worsening symptoms.",
            "criticalTests": [item["test_name"] for item in findings if item["severity"] == "critical"],
        },
        "doctorRecommendations": doctor_recommendations,
        "authenticity": proof,
    }
    ai_insights = ai_result.get("insights") if isinstance(ai_result, dict) else None
    if isinstance(ai_insights, dict):
        for key in (
            "riskPredictions", "medicineDetails", "interactionChecks", "lifestyleRecommendations",
            "medicineReminders", "emergencyAssessment", "doctorRecommendations", "generalGuidance",
        ):
            if key in ai_insights and isinstance(ai_insights[key], (list, dict)):
                insights[key] = ai_insights[key]
        if isinstance(ai_insights.get("generalGuidance"), list):
            insights["generalGuidance"] = ai_insights["generalGuidance"]
    if language in {"hi", "hinglish"} and not ai_result:
        localized_summaries = {
            "hi": "रिपोर्ट की समीक्षा पूरी हुई। पहचाने गए मानों की मूल रिपोर्ट और डॉक्टर के साथ पुष्टि करें।",
            "hinglish": "Report review complete hua. Identified values ko original report aur doctor ke sath confirm karein.",
        }
        analysis["plainLanguageSummary"] = localized_summaries[language]
        analysis["overview"] = localized_summaries[language]
        insights["summary"] = localized_summaries[language]
    return {
        "findings": findings,
        "summary": summary,
        "specialties": specialties,
        "analysis": analysis,
        "insights": insights,
    }


def generate_chat_reply(question, report, history=(), language="en"):
    language = normalize_language(language)
    report_summary = report.analysis_json.get("plainLanguageSummary", "") if report.analysis_json else ""
    report_context = {
        "filename": report.original_filename,
        "summary": report_summary,
        "findings": (report.insights_json or {}).get("abnormalFindings", []),
        "ocrExcerpt": (report.ocr_text or "")[:6000],
        "recentConversation": list(history)[-8:],
    }
    reply = _openai_text(
        "You are a careful medical-report explainer. Answer using only the supplied report context. Explain uncertainty, do not diagnose, do not recommend starting/stopping/dosing medicines, and advise emergency services for severe symptoms. Write in the requested language.",
        json.dumps({"language": language, "question": question, "report": report_context}, ensure_ascii=False),
    )
    if reply:
        return reply
    if report_summary:
        return f"This report's saved summary says: {report_summary} If you share a specific value or term, I can explain what the report records. Please confirm treatment decisions with your clinician."
    return "I can help explain the text in this report. Please ask about a specific value or phrase, and confirm medical decisions with your clinician."


def generate_ai_comparison(reports, metrics, language="en"):
    language = normalize_language(language)
    result = _openai_json(
        "Compare only the supplied medical report summaries and measurements. Return JSON with summary, healthImpact, keyDifferences (objects with id, label, direction, summary, healthImpact, confidence, values), notes, followUpQuestions, and generatedBy. Do not diagnose, infer a treatment, or claim that a change is clinically meaningful without context. Use the requested language.",
        json.dumps({"language": language, "reports": reports, "metrics": metrics}, ensure_ascii=False),
        model=getattr(settings, "OPENAI_ANALYSIS_MODEL", "gpt-4.1-mini"),
    )
    if isinstance(result, dict):
        result["reports"] = reports
        result["generatedBy"] = "openai"
        result.setdefault("summary", "Numeric changes are shown for review with a qualified clinician.")
        result.setdefault("healthImpact", "Changes should be interpreted in the context of your health history and lab ranges.")
        result.setdefault("keyDifferences", [])
        result.setdefault("notes", [])
        result.setdefault("followUpQuestions", [])
        return result
    return {
        "reports": reports,
        "summary": "Compare these values with your clinician, since reference ranges can depend on the lab and your health context.",
        "healthImpact": "The numeric changes are shown for review and do not establish a diagnosis.",
        "keyDifferences": [],
        "notes": ["Only comparable numeric findings are included."],
        "followUpQuestions": ["Are these changes meaningful for my health history?"],
        "generatedBy": "unknown",
    }


def humanize_reply(message, language="en"):
    reply = _openai_text(
        "Rewrite the supplied medical assistant message in calm, simple patient-friendly language. Keep all facts, avoid adding advice or diagnoses, and use the requested language.",
        json.dumps({"language": normalize_language(language), "message": message}, ensure_ascii=False),
    )
    return reply or message
