from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.classifier import ApplicationClassifier
from app.fallback import FallbackEngine
from app.schemas import PolicyEvalRequest, PolicyEvalResult
from app.models import Policy, PolicyDecision

# Weights for priority score calculation
APP_CLASS_WEIGHTS: Dict[str, float] = {
    "Critical": 4.0,
    "Important": 3.0,
    "Normal": 2.0,
    "Non-critical": 1.0,
    "UNKNOWN": 0.5
}

ORG_TIER_WEIGHTS: Dict[str, float] = {
    "org_chennai_hq": 1.2,
    "org_bangalore_hub": 1.2,
    "org_mumbai_hub": 1.1,
    "org_aws_cloud": 1.0,
    "org_azure_cloud": 1.0,
    "org_remote_work": 1.0,
    "org_external_partner": 0.8
}

class PolicyEngineConfig:
    """Configurable threshold parameters."""
    CONGESTION_LOW: float = 70.0      # 70% threshold
    CONGESTION_HIGH: float = 85.0     # 85% threshold
    CONGESTION_SEVERE: float = 95.0   # 95% threshold

class PolicyEngine:
    """Transparent rule-based bandwidth policy engine."""

    def __init__(self, config: Optional[PolicyEngineConfig] = None):
        self.config = config or PolicyEngineConfig()

    def calculate_priority_score(self, service_priority: int, app_class: str, organisation_id: str) -> float:
        """
        priority_score = service_priority * application_weight * organisation_weight
        """
        app_weight = APP_CLASS_WEIGHTS.get(app_class, 1.0)
        org_weight = ORG_TIER_WEIGHTS.get(organisation_id, 1.0)
        
        score = float(service_priority) * app_weight * org_weight
        return round(score, 2)

    def evaluate(self, request: PolicyEvalRequest, db: Optional[Session] = None) -> PolicyEvalResult:
        """
        Evaluates dynamic policy rules and returns a structured PolicyEvalResult with decision reasoning.
        """
        # 1. Telemetry freshness check
        is_stale_flow, flow_warning = FallbackEngine.evaluate_flow_freshness(request.timestamp)

        # 2. Link utilisation resolution (handles missing telemetry)
        util_pct, is_stale_util, util_warning = FallbackEngine.resolve_link_utilisation(
            link_id=request.link_id,
            current_util=request.link_utilisation_pct,
            db=db
        )

        # Combine warnings if telemetry is degraded
        stale_telemetry = is_stale_flow or is_stale_util
        warnings = [w for w in [flow_warning, util_warning] if w]
        telemetry_warning_str = " | ".join(warnings) if warnings else None

        # 3. Classify application if missing
        app_class = request.application_class or ApplicationClassifier.classify(request.application, db=db)
        
        # 4. Fallback check for UNKNOWN app
        resolved_class, unknown_fallback_action, unknown_warning = FallbackEngine.resolve_unknown_application(
            request.application, app_class
        )
        if unknown_warning and telemetry_warning_str:
            telemetry_warning_str += f" | {unknown_warning}"
        elif unknown_warning:
            telemetry_warning_str = unknown_warning

        # 5. Calculate priority score
        priority_score = self.calculate_priority_score(request.service_priority, resolved_class, request.organisation_id)

        # 6. Check for organization-specific custom policies in DB
        custom_policy: Optional[Policy] = None
        if db:
            custom_policy = FallbackEngine.get_isolated_org_policy(
                db=db,
                organisation_id=request.organisation_id,
                app_name=request.application,
                app_class=resolved_class
            )

        # Default bandwidth allocations (Mbps)
        min_bw = 0.0
        max_bw = 100.0
        decision = "NORMAL"
        reason = ""

        # 7. Apply Rule Evaluation Logic
        if custom_policy and custom_policy.action != "NORMAL":
            decision = custom_policy.action
            min_bw = custom_policy.minimum_bandwidth_mbps
            max_bw = custom_policy.maximum_bandwidth_mbps
            reason = (
                f"Custom organisation policy applied for '{request.application}' ({resolved_class}): "
                f"Action={decision}, MinBW={min_bw}Mbps, Priority Score={priority_score}."
            )
        elif resolved_class == "UNKNOWN":
            decision = "RATE_LIMIT"
            max_bw = 10.0
            reason = f"Application '{request.application}' is UNKNOWN. Conservative rate limit applied max 10Mbps."
        elif util_pct >= self.config.CONGESTION_SEVERE and resolved_class == "Critical":
            decision = "GUARANTEE_MINIMUM"
            min_bw = 50.0  # Guarantee at least 50% link capacity
            max_bw = 100.0
            reason = (
                f"CRITICAL SEVERE CONGESTION ({util_pct:.1f}% >= {self.config.CONGESTION_SEVERE}%): "
                f"Guaranteeing minimum {min_bw}Mbps for '{request.application}' (Class: {resolved_class}, Priority Score: {priority_score})."
            )
        elif util_pct >= self.config.CONGESTION_HIGH and resolved_class == "Non-critical":
            decision = "RATE_LIMIT"
            max_bw = 15.0  # Throttle non-critical traffic during high congestion
            reason = (
                f"HIGH CONGESTION DETECTED ({util_pct:.1f}% >= {self.config.CONGESTION_HIGH}%): "
                f"Throttling non-critical '{request.application}' to max {max_bw}Mbps (Class: {resolved_class}, Priority Score: {priority_score})."
            )
        elif util_pct >= self.config.CONGESTION_LOW and resolved_class in ["Critical", "Important"]:
            decision = "PRIORITISE"
            min_bw = 25.0
            reason = (
                f"MODERATE CONGESTION ({util_pct:.1f}% >= {self.config.CONGESTION_LOW}%): "
                f"Prioritising '{request.application}' traffic (Class: {resolved_class}, Priority Score: {priority_score})."
            )
        else:
            decision = "NORMAL"
            reason = (
                f"Link utilisation normal ({util_pct:.1f}% < {self.config.CONGESTION_LOW}%). "
                f"Standard bandwidth allocation for '{request.application}' (Class: {resolved_class})."
            )

        # Append stale telemetry notation to reason if active
        if stale_telemetry:
            reason += " [NOTE: Fallback telemetry active]"

        # Create evaluation result
        result = PolicyEvalResult(
            flow_id=request.flow_id,
            decision=decision,
            priority_score=priority_score,
            reason=reason,
            minimum_bandwidth_mbps=min_bw,
            maximum_bandwidth_mbps=max_bw,
            stale_telemetry=stale_telemetry,
            warning=telemetry_warning_str
        )

        # Log decision in DB if flow_id and db are provided
        if db and request.flow_id:
            try:
                import uuid
                decision_log = PolicyDecision(
                    id=f"dec_{uuid.uuid4().hex[:10]}",
                    flow_id=request.flow_id,
                    decision=decision,
                    priority_score=priority_score,
                    reason=reason
                )
                db.add(decision_log)
                db.commit()
            except Exception:
                db.rollback()

        return result
