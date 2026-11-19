from django.test import TestCase
from backend.core.healthcare_intelligence.backend.services.medical_nlp import MedicalNLP
from backend.core.healthcare_intelligence.backend.services.specialty_recommender import SpecialtyRecommender
from backend.core.healthcare_intelligence.backend.services.doctor_ranking import DoctorRankingEngine


class RecommendationSystemsTestCase(TestCase):
    def test_medical_nlp_extraction(self):
        sample_report_text = """
        LABORATORY INVESTIGATION REPORT
        Patient: Jane Doe | Age: 45
        HbA1c: 8.2 %
        Fasting Blood Sugar: 165 mg/dL
        Total Cholesterol: 245 mg/dL
        Serum Creatinine: 0.9 mg/dL
        Blood Pressure: 145/95 mmHg
        """
        findings = MedicalNLP.extract_findings_from_text(sample_report_text)
        self.assertTrue(len(findings) >= 4)

        metrics = [f["metric_key"] for f in findings]
        self.assertIn("hba1c", metrics)
        self.assertIn("glucose_fasting", metrics)
        self.assertIn("cholesterol_total", metrics)

        # Check analysis summary
        analysis = MedicalNLP.analyze_report_findings(findings, raw_text=sample_report_text)
        self.assertIn(analysis["overall_risk"], ["moderate", "high", "critical"])
        self.assertTrue(len(analysis["detected_conditions"]) > 0)

    def test_specialty_recommender(self):
        text = "Patient presenting with acute chest pain, elevated cholesterol, and high blood pressure."
        recs = SpecialtyRecommender.recommend_specialties(text=text, top_k=2)
        self.assertTrue(len(recs) > 0)
        top_code = recs[0]["code"]
        self.assertEqual(top_code, "cardiology")

    def test_doctor_ranking_engine(self):
        score_data = DoctorRankingEngine.compute_score(
            specialty_match_level="primary",
            distance_km=3.5,
            experience_years=15,
            rating=4.9,
            is_available=True,
        )
        self.assertGreater(score_data["total_score"], 80.0)
        self.assertIn("breakdown", score_data)
