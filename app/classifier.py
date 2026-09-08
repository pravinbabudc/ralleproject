from typing import Dict, Optional
from sqlalchemy.orm import Session
from app.models import Application

DEFAULT_APP_CLASSES: Dict[str, str] = {
    # Critical
    "ERP": "Critical",
    "VoIP": "Critical",
    "Business API": "Critical",
    "Payment processing": "Critical",
    "Production database": "Critical",

    # Important
    "Email": "Important",
    "Microsoft Teams": "Important",
    "Google Meet": "Important",
    "Collaboration applications": "Important",

    # Normal
    "General web browsing": "Normal",
    "Documentation": "Normal",
    "Social media": "Normal",

    # Non-critical
    "Video streaming": "Non-critical",
    "Large downloads": "Non-critical",
    "Backup": "Non-critical",
    "Software updates": "Non-critical"
}

DEFAULT_APP_PRIORITIES: Dict[str, int] = {
    "Critical": 100,
    "Important": 70,
    "Normal": 40,
    "Non-critical": 10
}

class ApplicationClassifier:
    """Classifies application network traffic into priority classes."""

    @staticmethod
    def classify(app_name: str, db: Optional[Session] = None) -> str:
        """Classify an application name to its class (Critical, Important, Normal, Non-critical, UNKNOWN)."""
        if not app_name or not app_name.strip():
            return "UNKNOWN"

        app_clean = app_name.strip()

        # Check DB overrides if DB session is available
        if db:
            db_app = db.query(Application).filter(Application.name == app_clean).first()
            if db_app and db_app.application_class:
                return db_app.application_class

        # Fallback to default dictionary
        if app_clean in DEFAULT_APP_CLASSES:
            return DEFAULT_APP_CLASSES[app_clean]

        # Case insensitive fallback lookup
        for known_app, app_cls in DEFAULT_APP_CLASSES.items():
            if known_app.lower() == app_clean.lower():
                return app_cls

        return "UNKNOWN"

    @staticmethod
    def get_default_priority(app_class: str) -> int:
        """Return baseline priority weight for a class."""
        return DEFAULT_APP_PRIORITIES.get(app_class, 20)
