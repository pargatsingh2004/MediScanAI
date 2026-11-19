import logging
from typing import List, Dict, Any
from modules.report_analysis.data_science.prediction.predictor import predict_specialty_probabilities

logger = logging.getLogger(__name__)

# Primary specialty keyword dictionaries
SPECIALTY_RULES = {
    "cardiology": {
        "name": "Cardiology",
        "keywords": [
            "heart", "cardiac", "cardio", "angina", "chest pain", "palpitation", "cholesterol",
            "triglyceride", "ldl", "hdl", "hypertension", "blood pressure", "bp", "ecg", "arrhythmia",
            "coronary", "atherosclerosis", "dyslipidemia", "pulse",
        ],
        "description": "Specializes in heart disorders, blood pressure management, and cardiovascular disease.",
    },
    "dermatology": {
        "name": "Dermatology",
        "keywords": [
            "skin", "rash", "itching", "eczema", "psoriasis", "dermatitis", "acne", "hives",
            "lesion", "melanoma", "mole", "alopecia", "hair loss", "fungal", "urticaria",
        ],
        "description": "Specializes in conditions affecting skin, hair, nails, and cutaneous allergies.",
    },
    "orthopedics": {
        "name": "Orthopedics",
        "keywords": [
            "bone", "joint", "knee", "spine", "back pain", "fracture", "arthritis", "osteoarthritis",
            "ligament", "sprain", "uric acid", "gout", "vitamin d", "stiffness", "tendon",
        ],
        "description": "Specializes in musculoskeletal conditions, bones, joints, ligaments, and mobility disorders.",
    },
    "neurology": {
        "name": "Neurology",
        "keywords": [
            "brain", "headache", "migraine", "nerve", "neuropathy", "numbness", "tingling",
            "seizure", "epilepsy", "tremor", "dizziness", "vertigo", "stroke", "memory", "vitamin b12",
        ],
        "description": "Specializes in disorders of the central and peripheral nervous system and brain health.",
    },
    "gastroenterology": {
        "name": "Gastroenterology",
        "keywords": [
            "stomach", "liver", "acid reflux", "gerd", "gastritis", "ulcer", "sgpt", "sgot",
            "alt", "ast", "bilirubin", "jaundice", "digestive", "diarrhea", "constipation", "bowel",
        ],
        "description": "Specializes in gastrointestinal tract, liver, gallbladder, and digestive disorders.",
    },
    "nephrology": {
        "name": "Nephrology",
        "keywords": [
            "kidney", "renal", "creatinine", "urea", "bun", "urine", "proteinuria", "edema",
            "swelling", "filtration", "gfr", "stones", "dialysis",
        ],
        "description": "Specializes in kidney function, renal clearance, electrolyte balance, and chronic kidney disease.",
    },
    "ophthalmology": {
        "name": "Ophthalmology",
        "keywords": [
            "eye", "vision", "blur", "cataract", "glaucoma", "retinopathy", "cornea", "macular",
            "conjunctivitis", "floaters", "sight",
        ],
        "description": "Specializes in eye care, visual acuity, retinopathy, and ocular disorders.",
    },
    "endocrinology": {
        "name": "Endocrinology",
        "keywords": [
            "diabetes", "glucose", "sugar", "hba1c", "fbs", "ppbs", "insulin", "thyroid",
            "tsh", "t3", "t4", "hormone", "hypothyroid", "hyperthyroid", "endocrine", "pcos",
        ],
        "description": "Specializes in hormonal glands, diabetes, thyroid management, and metabolic conditions.",
    },
    "pulmonology": {
        "name": "Pulmonology",
        "keywords": [
            "lung", "cough", "asthma", "breath", "shortness of breath", "wheezing", "chest tightness",
            "bronchitis", "pneumonia", "respiratory", "oxygen", "spo2",
        ],
        "description": "Specializes in respiratory system, lungs, asthma, and chronic pulmonary diseases.",
    },
    "general_medicine": {
        "name": "General Medicine",
        "keywords": [
            "fever", "weakness", "fatigue", "body ache", "hemoglobin", "anemia", "wbc", "rbc",
            "platelet", "infection", "general", "routine", "malaise",
        ],
        "description": "Provides comprehensive adult healthcare, preventive reviews, and general medical evaluation.",
    },
}


class SpecialtyRecommender:
    """Classifies clinical text, lab findings, and symptoms to recommend medical specialties."""

    @classmethod
    def recommend_specialties(
        cls,
        text: str = "",
        findings: List[Dict[str, Any]] = None,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """Calculates multi-specialty recommendations with calibrated relevance scores."""
        scores: Dict[str, float] = {code: 0.0 for code in SPECIALTY_RULES}
        findings = findings or []
        lower_text = text.lower() if text else ""

        # 1. Direct Biomarker signals from findings
        for f in findings:
            spec_code = f.get("specialty_code")
            if spec_code in scores:
                weight = 0.50 if f.get("severity") in ["critical", "high"] else 0.30
                scores[spec_code] += weight

        # 2. Rule-based keyword matching
        for code, meta in SPECIALTY_RULES.items():
            for kw in meta["keywords"]:
                if kw in lower_text:
                    scores[code] += 0.15

        # 3. Machine Learning probabilities
        if lower_text.strip():
            ml_probs = predict_specialty_probabilities(lower_text)
            for code, prob in ml_probs.items():
                if code in scores:
                    scores[code] += prob * 0.40

        # Always ensure General Medicine has a baseline if nothing specific triggered
        if max(scores.values()) == 0.0:
            scores["general_medicine"] = 0.85

        # Normalize scores to 0.0 - 1.0 (clamped)
        max_score = max(scores.values()) if max(scores.values()) > 0 else 1.0
        recommendations = []
        for code, raw_score in scores.items():
            if raw_score > 0.10:
                normalized_score = round(min(1.0, raw_score / max(1.0, max_score * 0.9)), 2)
                priority = "high" if normalized_score >= 0.70 else "moderate" if normalized_score >= 0.40 else "low"
                recommendations.append({
                    "code": code,
                    "name": SPECIALTY_RULES[code]["name"],
                    "description": SPECIALTY_RULES[code]["description"],
                    "relevance_score": normalized_score,
                    "relevance_percent": int(normalized_score * 100),
                    "priority": priority,
                })

        recommendations.sort(key=lambda x: x["relevance_score"], reverse=True)
        return recommendations[:top_k]
