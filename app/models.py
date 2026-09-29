"""
SQLAlchemy ORM Database Models for HybridFlowGuard.

Defines relational entities for multi-tenant organizations, system users with RBAC roles,
physical and virtual network links, application catalogs, dynamic policies, flow telemetry,
policy decisions, and security audit logs.
"""

import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Organisation(Base):
    """
    Tenant Organisation Entity.
    
    Represents an isolated enterprise division, regional branch, or external partner network.
    All flow telemetry and custom bandwidth policies are scoped to an organisation.
    """
    __tablename__ = "organisations"

    id = Column(String, primary_key=True, index=True, doc="Unique organisation identifier (e.g., org_chennai_hq)")
    name = Column(String, nullable=False, doc="Human-readable organization name")
    status = Column(String, default="active", doc="Organization operational status: active, suspended")

    # One-to-Many Relationships
    users = relationship("User", back_populates="organisation", cascade="all, delete-orphan")
    flow_records = relationship("FlowRecord", back_populates="organisation", cascade="all, delete-orphan")
    policies = relationship("Policy", back_populates="organisation", cascade="all, delete-orphan")


class User(Base):
    """
    User Account Entity with Role-Based Access Control (RBAC).
    
    Supported Roles:
    - admin: Unrestricted global access across all tenants and links.
    - network_manager: Global infrastructure visibility and benchmark execution.
    - organisation_manager: Scoped strictly to assigned organisation_id.
    - external_partner: Read-only partner extranet SLA monitoring.
    - viewer: Read-only compliance and audit log review.
    """
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True, doc="Unique user account identifier")
    username = Column(String, unique=True, index=True, nullable=False, doc="Unique login username")
    organisation_id = Column(String, ForeignKey("organisations.id"), nullable=False, doc="Foreign key linking user to tenant")
    role = Column(String, nullable=False, doc="RBAC role assigned to user")

    organisation = relationship("Organisation", back_populates="users")


class Application(Base):
    """
    Application Registry Entity.
    
    Maintains pre-classified network application profiles with default priority ratings.
    Classes: Critical, Important, Normal, Non-critical.
    """
    __tablename__ = "applications"

    id = Column(String, primary_key=True, index=True, doc="Unique application slug identifier")
    name = Column(String, unique=True, nullable=False, doc="Standardized application name (e.g. ERP, VoIP)")
    application_class = Column(String, nullable=False, doc="QoS Tier: Critical, Important, Normal, Non-critical")
    default_priority = Column(Integer, default=50, doc="Default service priority weight (1-100)")


class Link(Base):
    """
    Network Link Infrastructure Entity.
    
    Represents physical fiber, MPLS lines, cloud DirectConnect / ExpressRoute peering,
    or VPN concentrator gateways connecting enterprise sites.
    """
    __tablename__ = "links"

    id = Column(String, primary_key=True, index=True, doc="Unique link identifier (e.g., link_chennai_cloud)")
    name = Column(String, nullable=False, doc="Descriptive link name")
    source = Column(String, nullable=False, doc="Originating site or office")
    destination = Column(String, nullable=False, doc="Terminating endpoint or cloud region")
    capacity_mbps = Column(Float, nullable=False, default=100.0, doc="Total rated link capacity in Mbps")
    utilisation_pct = Column(Float, nullable=False, default=0.0, doc="Instantaneous link saturation percentage (0-100)")
    status = Column(String, default="active", doc="Link status: active, degraded, offline")


class FlowRecord(Base):
    """
    Network Flow Telemetry Entity.
    
    Captures individual network sessions with traffic metrics (bytes, packets, latency,
    jitter, packet loss) and the policy enforcement action evaluated on ingestion.
    """
    __tablename__ = "flow_records"

    id = Column(String, primary_key=True, index=True, doc="Unique flow record identifier (e.g., flow_a1b2c3d4)")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True, doc="Flow ingestion UTC timestamp")
    organisation_id = Column(String, ForeignKey("organisations.id"), nullable=False, doc="Tenant organization ID")
    source_location = Column(String, nullable=False, doc="Source enterprise site")
    destination = Column(String, nullable=False, doc="Target datacenter or cloud endpoint")
    user_id = Column(String, nullable=False, doc="Originating user identifier")
    user_type = Column(String, nullable=False, doc="User profile tier: Employee, Executive, System Process")
    application = Column(String, nullable=False, doc="Application name")
    application_class = Column(String, nullable=False, doc="QoS Class: Critical, Important, Normal, Non-critical")
    protocol = Column(String, default="TCP", doc="Transport protocol: TCP, UDP, QUIC, SRTP, HTTPS")
    source_ip = Column(String, nullable=False, doc="Source IPv4 address")
    destination_ip = Column(String, nullable=False, doc="Destination IPv4 address")
    bytes = Column(Float, default=0.0, doc="Flow data transfer volume in bytes")
    packets = Column(Integer, default=0, doc="Transmitted packet count")
    latency_ms = Column(Float, default=10.0, doc="Observed round-trip latency in milliseconds")
    packet_loss_pct = Column(Float, default=0.0, doc="Observed packet loss percentage (0-100)")
    jitter_ms = Column(Float, default=1.0, doc="Packet Delay Variation / Jitter in milliseconds")
    burst_factor = Column(Float, default=1.0, doc="Traffic micro-burst multiplier (1.0 = baseline)")
    link_id = Column(String, ForeignKey("links.id"), nullable=False, doc="Link traversed by flow")
    link_capacity_mbps = Column(Float, default=100.0, doc="Link rated capacity in Mbps")
    link_utilisation_pct = Column(Float, default=50.0, doc="Link saturation level at flow arrival")
    service_priority = Column(Integer, default=50, doc="Assigned service priority weight (1-100)")
    policy_action = Column(String, default="NORMAL", doc="Evaluated QoS action: GUARANTEE_MINIMUM, PRIORITISE, RATE_LIMIT, NORMAL")

    organisation = relationship("Organisation", back_populates="flow_records")


class Policy(Base):
    """
    Bandwidth Policy Rule Entity.
    
    Configurable bandwidth allocation rules deployed per tenant or application class.
    Specifies guaranteed floors, rate-limiting ceilings, and admission actions.
    """
    __tablename__ = "policies"

    id = Column(String, primary_key=True, index=True, doc="Unique policy rule identifier (e.g., pol_12345678)")
    organisation_id = Column(String, ForeignKey("organisations.id"), nullable=False, doc="Tenant organization ID")
    application = Column(String, nullable=True, doc="Specific application name (or None for class-wide default)")
    application_class = Column(String, nullable=False, doc="Target application class")
    priority = Column(Integer, default=50, doc="Policy priority weight (1-100)")
    minimum_bandwidth_mbps = Column(Float, default=0.0, doc="Guaranteed minimum reserved bandwidth floor in Mbps")
    maximum_bandwidth_mbps = Column(Float, default=100.0, doc="Maximum allowed rate-limit bandwidth ceiling in Mbps")
    action = Column(String, default="NORMAL", doc="Policy action: PRIORITISE, RATE_LIMIT, GUARANTEE_MINIMUM, NORMAL")

    organisation = relationship("Organisation", back_populates="policies")


class PolicyDecision(Base):
    """
    Policy Decision Log Entity.
    
    Records every admission decision made by the PolicyEngine with priority scores
    and evaluation reasoning for compliance auditability.
    """
    __tablename__ = "policy_decisions"

    id = Column(String, primary_key=True, index=True, doc="Unique decision log identifier")
    flow_id = Column(String, ForeignKey("flow_records.id"), nullable=False, doc="Associated flow record ID")
    decision = Column(String, nullable=False, doc="Decided action: GUARANTEE_MINIMUM, PRIORITISE, RATE_LIMIT, NORMAL")
    priority_score = Column(Float, nullable=False, doc="Computed multi-factor priority score")
    reason = Column(Text, nullable=False, doc="Detailed human-readable evaluation rationale")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, doc="Evaluation UTC timestamp")


class AuditLog(Base):
    """
    Administrative Security Audit Log Entity.
    
    Provides tamper-evident tracking of configuration modifications, policy deployments,
    and administrative interventions across the platform.
    """
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, index=True, doc="Unique audit log entry identifier")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, doc="Audit event UTC timestamp")
    user_id = Column(String, nullable=False, doc="Username or system actor performing action")
    action = Column(String, nullable=False, doc="Action verb: CREATE_POLICY, UPDATE_POLICY, DELETE_POLICY")
    details = Column(Text, nullable=False, doc="Comprehensive JSON/text details of event")
