from django.test import TestCase
from backend.core.healthcare_intelligence.backend.services.report_extractor import ReportExtractor


class ReportExtractorTestCase(TestCase):
    def test_text_cleaning(self):
        dirty = "Patient Name:\tJohn Doe\n\n\nBlood Sugar:\t 140 mg/dL \n"
        cleaned = ReportExtractor.clean_text(dirty)
        self.assertIn("Patient Name: John Doe", cleaned)
        self.assertIn("Blood Sugar: 140 mg/dL", cleaned)

    def test_sha256_computation(self):
        sample_bytes = b"Sample Medical Lab Report Content"
        sha = ReportExtractor.compute_sha256(sample_bytes)
        self.assertEqual(len(sha), 64)
