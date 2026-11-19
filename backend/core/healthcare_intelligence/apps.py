from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class HealthcareIntelligenceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.core.healthcare_intelligence"
    label = "healthcare_intelligence"
    verbose_name = "Healthcare Intelligence & Smart Doctor Recommendation"

    def ready(self):
        try:
            from modules.report_analysis.data_science.prediction.predictor import warm_up_models
            warm_up_models()
        except Exception:
            logger.exception("Specialty classifier warm-up failed; rule-based analysis remains available.")
