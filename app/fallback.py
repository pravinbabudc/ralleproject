"""
Telemetry Fallback Engine & Anomaly Resilience Subsystem.

Provides fault tolerance and automatic failover when network flow telemetry
is delayed, link utilisation sensors fail, or unclassified application signatures emerge.
"""

import datetime
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from app.models import Link, FlowRecord, Policy

# Stale telemetry threshold: flows older than 30s trigger last-known-good fallback
TELEMETRY_STALE_THRESHOLD_SECONDS = 30

# In-memory last-known-good cache for instantaneous link utilisation
_LINK_UTILISATION_CACHE: Dict[str, float] = {}
_LAST_VALID_FLOW_CACHE: Dict[str, Dict[str, Any]] = {}


class FallbackEngine:
    """
    Provides resilience and fallback mechanisms when telemetry data is missing,
    delayed, corrupted, or unclassified.
    """

    @staticmethod
    def evaluate_flow_freshness(timestamp: Optional[datetime.datetime]) -> Tuple[bool, Optional[str]]:
        """
        Evaluate if flow record telemetry is stale or delayed.
        
        Boundary:
        - If timestamp is missing: Returns True (stale) with alert.
        - If (current_time - timestamp) > 30s: Returns True (stale) with age details.
        - Otherwise: Returns False (fresh).
        
        Returns:
        - Tuple[bool, Optional[str]]: (is_stale, warning_message)
        """
        if not timestamp:
            return True, "Flow timestamp missing. Using cached telemetry data."

        # Handle timezone-aware vs naive UTC comparison
        if timestamp.tzinfo is None:
            now = datetime.datetime.utcnow()
        else:
            now = datetime.datetime.now(datetime.timezone.utc)

        time_diff = (now - timestamp).total_seconds()
        if time_diff > TELEMETRY_STALE_THRESHOLD_SECONDS:
            return True, f"Stale flow telemetry detected (age: {int(time_diff)}s > threshold {TELEMETRY_STALE_THRESHOLD_SECONDS}s). Using cached telemetry."
        
        return False, None

    @staticmethod
    def resolve_link_utilisation(
        link_id: str,
        current_util: Optional[float],
        db: Optional[Session] = None
    ) -> Tuple[float, bool, Optional[str]]:
        """
        Resolve link utilisation through a tri-tiered hierarchical fallback:
        1. Current reading: If non-None and within [0.0, 100.0], cache and return.
        2. Database query: Check historical link record in database.
        3. Cache fallback: Retrieve last-known-good metric from memory cache.
        4. Safe default: Apply conservative default (50.0%) if no historical telemetry exists.
        
        Returns:
        - Tuple[float, bool, Optional[str]]: (resolved_utilisation_pct, is_stale, warning_message)
        """
        global _LINK_UTILISATION_CACHE

        # Tier 1: Valid current telemetry reading
        if current_util is not None and 0.0 <= current_util <= 100.0:
            _LINK_UTILISATION_CACHE[link_id] = current_util
            return current_util, False, None

        # Tier 2: Query database for last recorded utilisation
        if db:
            db_link = db.query(Link).filter(Link.id == link_id).first()
            if db_link and db_link.utilisation_pct is not None:
                _LINK_UTILISATION_CACHE[link_id] = db_link.utilisation_pct
                return db_link.utilisation_pct, True, f"Link utilisation unavailable for '{link_id}'. Using last DB recorded value ({db_link.utilisation_pct}%)."

        # Tier 3: Memory cache fallback
        if link_id in _LINK_UTILISATION_CACHE:
            cached_val = _LINK_UTILISATION_CACHE[link_id]
            return cached_val, True, f"Link utilisation telemetry missing for '{link_id}'. Fallback to last-known-good value ({cached_val}%)."

        # Tier 4: Safe conservative baseline default
        default_val = 50.0
        return default_val, True, f"Link utilisation telemetry missing and no history found for '{link_id}'. Defaulting conservatively to {default_val}%."

    @staticmethod
    def resolve_unknown_application(app_name: str, app_class: str) -> Tuple[str, str, Optional[str]]:
        """
        Safety boundary for unclassified or Shadow IT applications.
        
        Boundary Rule:
        - If app_class is 'UNKNOWN' or application name is missing:
          Assigns conservative 'RATE_LIMIT' action (max 10 Mbps) to safeguard critical traffic queues.
        - Otherwise passes through existing classification.
        
        Returns:
        - Tuple[str, str, Optional[str]]: (resolved_class, conservative_policy_action, warning_msg)
        """
        if app_class == "UNKNOWN" or not app_name:
            warning = f"Unknown application '{app_name}'. Classifying as UNKNOWN and applying conservative RATE_LIMIT fallback policy."
            return "UNKNOWN", "RATE_LIMIT", warning
        return app_class, "NORMAL", None

    @staticmethod
    def get_isolated_org_policy(
        db: Session,
        organisation_id: str,
        app_name: str,
        app_class: str
    ) -> Optional[Policy]:
        """
        Retrieve tenant-isolated custom policy from database.
        
        Evaluation Precedence:
        1. Specific application match for the given organisation_id (e.g. app="ERP").
        2. Application class match for the given organisation_id (e.g. class="Critical").
        
        Security Invariant:
        - Policies belonging to other organisation IDs are never returned (zero cross-tenant leakage).
        """
        # 1. Search for specific application rule for this organisation
        policy = db.query(Policy).filter(
            Policy.organisation_id == organisation_id,
            Policy.application == app_name
        ).first()

        if policy:
            return policy

        # 2. Search for class-level rule for this organisation
        policy = db.query(Policy).filter(
            Policy.organisation_id == organisation_id,
            Policy.application_class == app_class
        ).first()

        return policy
