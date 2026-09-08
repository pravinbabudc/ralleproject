import datetime
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from app.models import Link, FlowRecord, Policy

TELEMETRY_STALE_THRESHOLD_SECONDS = 30

# In-memory last-known-good values cache for telemetry fault tolerance
_LINK_UTILISATION_CACHE: Dict[str, float] = {}
_LAST_VALID_FLOW_CACHE: Dict[str, Dict[str, Any]] = {}

class FallbackEngine:
    """Provides resilience and fallback mechanisms when telemetry data is missing, delayed, or corrupted."""

    @staticmethod
    def evaluate_flow_freshness(timestamp: Optional[datetime.datetime]) -> Tuple[bool, Optional[str]]:
        """Detect if flow record data is stale."""
        if not timestamp:
            return True, "Flow timestamp missing. Using cached telemetry data."

        now = datetime.datetime.utcnow()
        time_diff = (now - timestamp).total_seconds()
        if time_diff > TELEMETRY_STALE_THRESHOLD_SECONDS:
            return True, f"Stale flow telemetry detected (age: {int(time_diff)}s > threshold {TELEMETRY_STALE_THRESHOLD_SECONDS}s). Using cached telemetry."
        
        return False, None

    @staticmethod
    def resolve_link_utilisation(link_id: str, current_util: Optional[float], db: Optional[Session] = None) -> Tuple[float, bool, Optional[str]]:
        """
        Resolve link utilisation. If missing or invalid (None), use last-known-good value.
        Returns: (resolved_utilisation_pct, is_stale, warning_message)
        """
        global _LINK_UTILISATION_CACHE

        if current_util is not None and 0.0 <= current_util <= 100.0:
            # Update cache with valid reading
            _LINK_UTILISATION_CACHE[link_id] = current_util
            return current_util, False, None

        # Check DB if available
        if db:
            db_link = db.query(Link).filter(Link.id == link_id).first()
            if db_link and db_link.utilisation_pct is not None:
                _LINK_UTILISATION_CACHE[link_id] = db_link.utilisation_pct
                return db_link.utilisation_pct, True, f"Link utilisation unavailable for '{link_id}'. Using last DB recorded value ({db_link.utilisation_pct}%)."

        # Fallback to cache
        if link_id in _LINK_UTILISATION_CACHE:
            cached_val = _LINK_UTILISATION_CACHE[link_id]
            return cached_val, True, f"Link utilisation telemetry missing for '{link_id}'. Fallback to last-known-good value ({cached_val}%)."

        # Default fallback if no history exists
        default_val = 50.0
        return default_val, True, f"Link utilisation telemetry missing and no history found for '{link_id}'. Defaulting conservatively to {default_val}%."

    @staticmethod
    def resolve_unknown_application(app_name: str, app_class: str) -> Tuple[str, str, Optional[str]]:
        """
        Fallback logic for unknown application.
        Returns: (resolved_class, conservative_policy_action, warning_msg)
        """
        if app_class == "UNKNOWN" or not app_name:
            warning = f"Unknown application '{app_name}'. Classifying as UNKNOWN and applying conservative RATE_LIMIT fallback policy."
            return "UNKNOWN", "RATE_LIMIT", warning
        return app_class, "NORMAL", None

    @staticmethod
    def get_isolated_org_policy(db: Session, organisation_id: str, app_name: str, app_class: str) -> Optional[Policy]:
        """
        Retrieve tenant-isolated policy for an organisation.
        Never leak policies between different organisation IDs.
        """
        # 1. Search for specific app policy for this organisation
        policy = db.query(Policy).filter(
            Policy.organisation_id == organisation_id,
            Policy.application == app_name
        ).first()

        if policy:
            return policy

        # 2. Search for app_class policy for this organisation
        policy = db.query(Policy).filter(
            Policy.organisation_id == organisation_id,
            Policy.application_class == app_class
        ).first()

        return policy
