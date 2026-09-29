from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

# Organisation Schemas
class OrganisationBase(BaseModel):
    name: str
    status: str = "active"

class OrganisationCreate(OrganisationBase):
    id: str

class OrganisationOut(OrganisationBase):
    id: str

    class Config:
        from_attributes = True

# User Schemas
class UserBase(BaseModel):
    username: str
    organisation_id: str
    role: str

class UserCreate(UserBase):
    id: str

class UserOut(UserBase):
    id: str

    class Config:
        from_attributes = True

# Application Schemas
class ApplicationBase(BaseModel):
    name: str
    application_class: str  # Critical, Important, Normal, Non-critical
    default_priority: int = 50

class ApplicationCreate(ApplicationBase):
    id: str

class ApplicationOut(ApplicationBase):
    id: str

    class Config:
        from_attributes = True

# Link Schemas
class LinkBase(BaseModel):
    name: str
    source: str
    destination: str
    capacity_mbps: float = 100.0
    utilisation_pct: float = 0.0
    status: str = "active"

class LinkCreate(LinkBase):
    id: str

class LinkOut(LinkBase):
    id: str

    class Config:
        from_attributes = True

# Policy Schemas
class PolicyBase(BaseModel):
    organisation_id: str
    application: Optional[str] = None
    application_class: str
    priority: int = 50
    minimum_bandwidth_mbps: float = 0.0
    maximum_bandwidth_mbps: float = 100.0
    action: str = "NORMAL"

class PolicyCreate(PolicyBase):
    pass

class PolicyUpdate(BaseModel):
    application: Optional[str] = None
    application_class: Optional[str] = None
    priority: Optional[int] = None
    minimum_bandwidth_mbps: Optional[float] = None
    maximum_bandwidth_mbps: Optional[float] = None
    action: Optional[str] = None

class PolicyOut(PolicyBase):
    id: str

    class Config:
        from_attributes = True

# Flow Record Schemas
class FlowRecordBase(BaseModel):
    organisation_id: str
    source_location: str
    destination: str
    user_id: str
    user_type: str
    application: str
    application_class: Optional[str] = None
    protocol: str = "TCP"
    source_ip: str
    destination_ip: str
    bytes: float = 0.0
    packets: int = 0
    latency_ms: float = 10.0
    packet_loss_pct: float = 0.0
    jitter_ms: float = 1.0
    burst_factor: float = 1.0
    link_id: str
    link_capacity_mbps: float = 100.0
    link_utilisation_pct: Optional[float] = None
    service_priority: int = 50
    policy_action: Optional[str] = "NORMAL"

class FlowRecordCreate(FlowRecordBase):
    timestamp: Optional[datetime] = None

class FlowRecordOut(FlowRecordBase):
    id: str
    timestamp: datetime
    application_class: str
    link_utilisation_pct: float

    class Config:
        from_attributes = True

# Policy Evaluation Schemas
class PolicyEvalRequest(BaseModel):
    flow_id: Optional[str] = None
    organisation_id: str
    application: str
    application_class: Optional[str] = None
    link_id: str
    link_utilisation_pct: Optional[float] = None
    service_priority: int = 50
    timestamp: Optional[datetime] = None

class PolicyEvalResult(BaseModel):
    flow_id: Optional[str] = None
    decision: str
    priority_score: float
    reason: str
    minimum_bandwidth_mbps: float
    maximum_bandwidth_mbps: float
    stale_telemetry: bool = False
    warning: Optional[str] = None

# Policy Decision Out
class PolicyDecisionOut(BaseModel):
    id: str
    flow_id: str
    decision: str
    priority_score: float
    reason: str
    timestamp: datetime

    class Config:
        from_attributes = True

# Experiment Schemas
class ExperimentRunRequest(BaseModel):
    scenario: str = "90% congestion" # "Normal network", "90% congestion", "98% congestion"
    num_flows: int = 500

class ExperimentMetric(BaseModel):
    metric: str
    baseline: float
    target: str
    hybridflowguard: float
    result: str
    unit: str = "Mbps"

class ExperimentResultOut(BaseModel):
    scenario: str
    timestamp: datetime
    critical_throughput_baseline: float
    critical_throughput_hfg: float
    critical_latency_baseline: float
    critical_latency_hfg: float
    critical_loss_baseline: float
    critical_loss_hfg: float
    non_critical_throughput_baseline: float
    non_critical_throughput_hfg: float
    link_utilisation_pct: float
    policy_decision_time_ms: float
    metrics_summary: List[ExperimentMetric]
    error_analysis: str

# Audit Log Out
class AuditLogOut(BaseModel):
    id: str
    timestamp: datetime
    user_id: str
    action: str
    details: str

    class Config:
        from_attributes = True

# System Health & Telemetry Status
class TelemetryStatus(BaseModel):
    status: str
    last_flow_timestamp: Optional[str] = None
    last_utilisation_timestamp: Optional[str] = None
    stale_flow_detected: bool = False
    missing_link_utilisation_detected: bool = False
    unknown_applications_count: int = 0
    fallback_active: bool = False
    message: str
