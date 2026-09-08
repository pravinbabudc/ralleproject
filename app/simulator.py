import uuid
import random
import datetime
from typing import List, Dict, Any, Optional
import pandas as pd

from app.classifier import DEFAULT_APP_CLASSES, DEFAULT_APP_PRIORITIES

LOCATIONS = [
    ("Chennai Office", "org_chennai_hq", "link_chennai_cloud"),
    ("Bangalore Office", "org_bangalore_hub", "link_bangalore_cloud"),
    ("Mumbai Office", "org_mumbai_hub", "link_mumbai_cloud"),
    ("AWS Cloud", "org_aws_cloud", "link_aws_backbone"),
    ("Azure Cloud", "org_azure_cloud", "link_azure_backbone"),
    ("Remote Employees", "org_remote_work", "link_vpn_gateway"),
    ("External Partners", "org_external_partner", "link_partner_extranet")
]

USER_TYPES = ["Employee", "Executive", "System Process", "Partner User", "Automated Task"]

PROTOCOLS = ["TCP", "UDP", "HTTPS", "SRTP", "QUIC"]

# Base traffic proportions
APP_WEIGHTS = {
    # Critical
    "ERP": 15,
    "VoIP": 15,
    "Business API": 10,
    "Payment processing": 5,
    "Production database": 5,
    # Important
    "Email": 10,
    "Microsoft Teams": 10,
    "Google Meet": 5,
    "Collaboration applications": 5,
    # Normal
    "General web browsing": 5,
    "Documentation": 3,
    "Social media": 2,
    # Non-critical
    "Video streaming": 5,
    "Large downloads": 3,
    "Backup": 1,
    "Software updates": 1
}

class CongestionSimulator:
    """Generates synthetic flow data under varying network congestion scenarios."""

    @staticmethod
    def generate_flow_record(
        scenario: str = "Normal network",
        link_utilisation_override: Optional[float] = None,
        timestamp_override: Optional[datetime.datetime] = None
    ) -> Dict[str, Any]:
        """Generate a single realistic flow record."""

        loc_name, org_id, link_id = random.choice(LOCATIONS)

        # Select application based on weighted distribution
        apps = list(APP_WEIGHTS.keys())
        weights = list(APP_WEIGHTS.values())
        app_name = random.choices(apps, weights=weights, k=1)[0]
        app_class = DEFAULT_APP_CLASSES.get(app_name, "Normal")

        # Determine link utilisation based on scenario
        if link_utilisation_override is not None:
            util_pct = link_utilisation_override
        elif "98%" in scenario or "Severe" in scenario:
            util_pct = round(random.uniform(95.0, 99.5), 1)
        elif "90%" in scenario or "High" in scenario:
            util_pct = round(random.uniform(88.0, 94.0), 1)
        else:
            util_pct = round(random.uniform(40.0, 65.0), 1)

        # Determine metrics based on congestion level and application class
        link_capacity = 100.0  # Mbps
        base_latency = 8.0 if "Cloud" in loc_name else 18.0

        if util_pct >= 95.0:
            latency_mult = random.uniform(3.5, 6.0)
            loss_base = random.uniform(2.5, 8.0)
        elif util_pct >= 85.0:
            latency_mult = random.uniform(1.8, 3.0)
            loss_base = random.uniform(0.5, 2.5)
        else:
            latency_mult = random.uniform(1.0, 1.2)
            loss_base = random.uniform(0.0, 0.2)

        # Bytes and packets depend on app class
        if app_class == "Non-critical":
            flow_bytes = random.uniform(500_000, 15_000_000)
            flow_packets = random.randint(500, 10000)
        elif app_class == "Critical":
            flow_bytes = random.uniform(10_000, 2_000_000)
            flow_packets = random.randint(50, 1500)
        else:
            flow_bytes = random.uniform(50_000, 5_000_000)
            flow_packets = random.randint(100, 3000)

        service_priority = DEFAULT_APP_PRIORITIES.get(app_class, 50) + random.randint(-5, 5)
        service_priority = max(1, min(100, service_priority))

        src_ip = f"10.{random.randint(1, 20)}.{random.randint(1, 254)}.{random.randint(1, 254)}"
        dst_ip = f"172.16.{random.randint(1, 10)}.{random.randint(1, 254)}"

        ts = timestamp_override or datetime.datetime.utcnow() - datetime.timedelta(seconds=random.randint(0, 300))

        return {
            "id": f"flow_{uuid.uuid4().hex[:12]}",
            "timestamp": ts.isoformat(),
            "organisation_id": org_id,
            "source_location": loc_name,
            "destination": f"Datacenter-{random.choice(['A', 'B', 'Cloud'])}",
            "user_id": f"usr_{random.randint(1000, 9999)}",
            "user_type": random.choice(USER_TYPES),
            "application": app_name,
            "application_class": app_class,
            "protocol": "UDP" if app_name in ["VoIP", "Google Meet"] else random.choice(PROTOCOLS),
            "source_ip": src_ip,
            "destination_ip": dst_ip,
            "bytes": round(flow_bytes, 2),
            "packets": flow_packets,
            "latency_ms": round(base_latency * latency_mult, 2),
            "packet_loss_pct": round(loss_base, 2),
            "link_id": link_id,
            "link_capacity_mbps": link_capacity,
            "link_utilisation_pct": util_pct,
            "service_priority": service_priority,
            "policy_action": "NORMAL"
        }

    @classmethod
    def generate_dataset(cls, count: int = 1000, scenario: str = "Normal network") -> pd.DataFrame:
        """Generate a DataFrame of synthetic flow records."""
        records = [cls.generate_flow_record(scenario=scenario) for _ in range(count)]
        return pd.DataFrame(records)
