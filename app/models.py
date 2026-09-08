import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base

class Organisation(Base):
    __tablename__ = "organisations"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    status = Column(String, default="active")

    users = relationship("User", back_populates="organisation")
    flow_records = relationship("FlowRecord", back_populates="organisation")
    policies = relationship("Policy", back_populates="organisation")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    organisation_id = Column(String, ForeignKey("organisations.id"), nullable=False)
    role = Column(String, nullable=False)  # admin, network_manager, organisation_manager, external_partner, viewer

    organisation = relationship("Organisation", back_populates="users")


class Application(Base):
    __tablename__ = "applications"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    application_class = Column(String, nullable=False)  # Critical, Important, Normal, Non-critical
    default_priority = Column(Integer, default=50)


class Link(Base):
    __tablename__ = "links"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    source = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    capacity_mbps = Column(Float, nullable=False, default=100.0)
    utilisation_pct = Column(Float, nullable=False, default=0.0)
    status = Column(String, default="active")


class FlowRecord(Base):
    __tablename__ = "flow_records"

    id = Column(String, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    organisation_id = Column(String, ForeignKey("organisations.id"), nullable=False)
    source_location = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    user_type = Column(String, nullable=False)
    application = Column(String, nullable=False)
    application_class = Column(String, nullable=False)
    protocol = Column(String, default="TCP")
    source_ip = Column(String, nullable=False)
    destination_ip = Column(String, nullable=False)
    bytes = Column(Float, default=0.0)
    packets = Column(Integer, default=0)
    latency_ms = Column(Float, default=10.0)
    packet_loss_pct = Column(Float, default=0.0)
    link_id = Column(String, ForeignKey("links.id"), nullable=False)
    link_capacity_mbps = Column(Float, default=100.0)
    link_utilisation_pct = Column(Float, default=50.0)
    service_priority = Column(Integer, default=50)
    policy_action = Column(String, default="NORMAL")

    organisation = relationship("Organisation", back_populates="flow_records")


class Policy(Base):
    __tablename__ = "policies"

    id = Column(String, primary_key=True, index=True)
    organisation_id = Column(String, ForeignKey("organisations.id"), nullable=False)
    application = Column(String, nullable=True)  # Specific application or None for all in class
    application_class = Column(String, nullable=False)
    priority = Column(Integer, default=50)
    minimum_bandwidth_mbps = Column(Float, default=0.0)
    maximum_bandwidth_mbps = Column(Float, default=100.0)
    action = Column(String, default="NORMAL")  # PRIORITISE, RATE_LIMIT, GUARANTEE_MINIMUM, NORMAL

    organisation = relationship("Organisation", back_populates="policies")


class PolicyDecision(Base):
    __tablename__ = "policy_decisions"

    id = Column(String, primary_key=True, index=True)
    flow_id = Column(String, ForeignKey("flow_records.id"), nullable=False)
    decision = Column(String, nullable=False)
    priority_score = Column(Float, nullable=False)
    reason = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    user_id = Column(String, nullable=False)
    action = Column(String, nullable=False)
    details = Column(Text, nullable=False)
