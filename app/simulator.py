import uuid
import random
import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np

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

# Recognized edge case scenarios
SUPPORTED_SCENARIOS = [
    "Normal network",
    "90% congestion",
    "98% congestion",
    "Bursty traffic spike",
    "High-jitter link",
    "Bursty spike + High-jitter",
    "Telemetry dropout / delayed report"
]


class CongestionSimulator:
    """
    Generates synthetic flow data under realistic network scenarios and edge cases:
    - Normal network operation (low utilisation, minimal jitter and loss)
    - Sustained high congestion (90% link saturation)
    - Severe saturation (98% link saturation)
    - Bursty traffic spikes (micro-burst surges, flash bulk data transfers)
    - High-jitter link conditions (satellite/cellular packet delay variations, bufferbloat)
    - Combined edge conditions and telemetry latency dropouts
    """

    @staticmethod
    def generate_flow_record(
        scenario: str = "Normal network",
        link_utilisation_override: Optional[float] = None,
        timestamp_override: Optional[datetime.datetime] = None,
        is_burst_override: Optional[bool] = None,
        jitter_override: Optional[float] = None,
        link_id_override: Optional[str] = None,
        org_id_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a single realistic flow record incorporating edge-case dynamics.
        """
        # Select location / link
        matched_locs = [l for l in LOCATIONS if (not link_id_override or l[2] == link_id_override) and (not org_id_override or l[1] == org_id_override)]
        if matched_locs:
            loc_name, org_id, link_id = random.choice(matched_locs)
        else:
            loc_name, org_id, link_id = random.choice(LOCATIONS)
            if link_id_override:
                link_id = link_id_override
            if org_id_override:
                org_id = org_id_override

        # Select application based on weighted distribution
        apps = list(APP_WEIGHTS.keys())
        weights = list(APP_WEIGHTS.values())
        app_name = random.choices(apps, weights=weights, k=1)[0]
        app_class = DEFAULT_APP_CLASSES.get(app_name, "Normal")

        # Normalize scenario string
        scen_lower = scenario.lower()
        is_burst_scenario = "burst" in scen_lower or "spike" in scen_lower
        is_jitter_scenario = "jitter" in scen_lower
        is_severe_scenario = "98%" in scenario or "severe" in scen_lower
        is_high_scenario = "90%" in scenario or "high" in scen_lower
        is_dropout_scenario = "dropout" in scen_lower or "delayed" in scen_lower

        # 1. Determine Burst Factor & Flow Burstiness
        if is_burst_override is not None:
            is_burst = is_burst_override
            burst_factor = round(random.uniform(3.0, 7.5), 2) if is_burst else 1.0
        elif is_burst_scenario:
            # Under burst scenarios, non-critical and normal apps burst heavily, or 45% of any flow
            if app_class in ["Non-critical", "Normal"] or random.random() < 0.45:
                is_burst = True
                burst_factor = round(random.uniform(3.5, 8.0), 2)
            else:
                is_burst = False
                burst_factor = round(random.uniform(1.0, 1.4), 2)
        else:
            is_burst = False
            burst_factor = 1.0

        # 2. Determine Link Utilisation
        if link_utilisation_override is not None:
            util_pct = link_utilisation_override
        elif is_burst_scenario and is_burst:
            util_pct = round(random.uniform(94.0, 99.6), 1)
        elif is_burst_scenario:
            util_pct = round(random.uniform(88.0, 95.0), 1)
        elif is_severe_scenario:
            util_pct = round(random.uniform(95.0, 99.5), 1)
        elif is_high_scenario:
            util_pct = round(random.uniform(88.0, 94.0), 1)
        else:
            util_pct = round(random.uniform(40.0, 65.0), 1)

        # 3. Determine Base Latency & Link Capacity
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

        # 4. Determine Jitter (Packet Delay Variation)
        if jitter_override is not None:
            jitter_ms = jitter_override
        elif is_jitter_scenario:
            # High-jitter link edge case (e.g. satellite / cellular / bufferbloat oscillations)
            # Sample heavy-tailed distribution (Gamma) with frequent spikes
            jitter_base = random.uniform(28.0, 75.0)
            if random.random() < 0.20:
                jitter_base += random.uniform(40.0, 90.0)  # Extreme spike
            jitter_ms = round(jitter_base, 2)
            # High jitter exacerbates latency variation and packet drop likelihood
            latency_mult += (jitter_ms / 40.0) * random.uniform(0.4, 0.9)
            loss_base = round(min(12.0, loss_base + (jitter_ms / 35.0) * random.uniform(0.6, 1.4)), 2)
        elif util_pct >= 95.0:
            jitter_ms = round(random.uniform(14.0, 32.0), 2)
        elif util_pct >= 85.0:
            jitter_ms = round(random.uniform(4.0, 12.0), 2)
        else:
            jitter_ms = round(random.uniform(0.5, 3.0), 2)

        # 5. Bytes and packets (scaled by burst_factor)
        if app_class == "Non-critical":
            flow_bytes = random.uniform(500_000, 15_000_000) * burst_factor
            flow_packets = int(random.randint(500, 10000) * burst_factor)
        elif app_class == "Critical":
            flow_bytes = random.uniform(10_000, 2_000_000) * (burst_factor if is_burst else 1.0)
            flow_packets = int(random.randint(50, 1500) * (burst_factor if is_burst else 1.0))
        else:
            flow_bytes = random.uniform(50_000, 5_000_000) * burst_factor
            flow_packets = int(random.randint(100, 3000) * burst_factor)

        service_priority = DEFAULT_APP_PRIORITIES.get(app_class, 50) + random.randint(-5, 5)
        service_priority = max(1, min(100, service_priority))

        src_ip = f"10.{random.randint(1, 20)}.{random.randint(1, 254)}.{random.randint(1, 254)}"
        dst_ip = f"172.16.{random.randint(1, 10)}.{random.randint(1, 254)}"

        # Timestamp handling (support simulated delayed report / dropout)
        if timestamp_override:
            ts = timestamp_override
        elif is_dropout_scenario:
            # Stale timestamp beyond 45 seconds to trigger telemetry fallback logic
            ts = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=random.randint(45, 120))
        else:
            ts = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=random.randint(0, 300))

        calculated_latency = round(max(2.0, base_latency * latency_mult + (jitter_ms * 0.3)), 2)

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
            "latency_ms": calculated_latency,
            "packet_loss_pct": round(loss_base, 2),
            "jitter_ms": jitter_ms,
            "burst_factor": burst_factor,
            "is_burst": is_burst,
            "link_id": link_id,
            "link_capacity_mbps": link_capacity,
            "link_utilisation_pct": util_pct,
            "service_priority": service_priority,
            "policy_action": "NORMAL"
        }

    @classmethod
    def generate_dataset(
        cls,
        count: int = 1000,
        scenario: str = "Normal network",
        link_id: Optional[str] = None,
        org_id: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Generate a DataFrame of synthetic flow records with optional link/tenant filters.
        """
        records = [
            cls.generate_flow_record(
                scenario=scenario,
                link_id_override=link_id,
                org_id_override=org_id
            ) for _ in range(count)
        ]
        return pd.DataFrame(records)

    @classmethod
    def generate_time_series_telemetry(
        cls,
        link_id: str = "link_chennai_cloud",
        count: int = 60,
        scenario: str = "Normal network",
        step_seconds: int = 1
    ) -> pd.DataFrame:
        """
        Generate sequential time-stamped telemetry for link saturation and queue depth monitoring.
        Models instantaneous link utilisation, buffer queue depth (KB), packet loss, and jitter.
        """
        now = datetime.datetime.now(datetime.timezone.utc)
        records = []
        base_time = now - datetime.timedelta(seconds=count * step_seconds)

        scen_lower = scenario.lower()
        is_burst = "burst" in scen_lower or "spike" in scen_lower
        is_jitter = "jitter" in scen_lower
        is_severe = "98%" in scenario or "severe" in scen_lower
        is_high = "90%" in scenario or "high" in scen_lower

        curr_util = 50.0
        queue_kb = 0.0

        for i in range(count):
            t = base_time + datetime.timedelta(seconds=i * step_seconds)
            
            # Determine instantaneous load
            if is_burst:
                # Periodic micro-burst surge every ~15 steps
                in_burst = (i % 20) in range(8, 14)
                if in_burst:
                    target_util = random.uniform(94.0, 99.8)
                    queue_kb = min(2500.0, queue_kb + random.uniform(300.0, 700.0))
                else:
                    target_util = random.uniform(65.0, 82.0)
                    queue_kb = max(0.0, queue_kb - random.uniform(200.0, 450.0))
            elif is_severe:
                target_util = random.uniform(95.0, 99.5)
                queue_kb = random.uniform(1800.0, 3200.0)
                in_burst = False
            elif is_high:
                target_util = random.uniform(88.0, 94.0)
                queue_kb = random.uniform(800.0, 1500.0)
                in_burst = False
            else:
                target_util = random.uniform(42.0, 64.0)
                queue_kb = max(0.0, random.uniform(10.0, 150.0))
                in_burst = False

            # Smooth drift towards target
            curr_util = round(0.7 * curr_util + 0.3 * target_util, 1)

            # Jitter modeling
            if is_jitter:
                jitter = round(random.uniform(30.0, 85.0) + (random.uniform(20.0, 60.0) if i % 7 == 0 else 0), 2)
            elif curr_util >= 95.0:
                jitter = round(random.uniform(14.0, 32.0), 2)
            elif curr_util >= 85.0:
                jitter = round(random.uniform(4.0, 12.0), 2)
            else:
                jitter = round(random.uniform(0.5, 3.0), 2)

            # Packet loss modeling
            if curr_util >= 95.0 or queue_kb > 2000.0:
                loss = round(random.uniform(2.5, 7.8), 2)
            elif curr_util >= 85.0:
                loss = round(random.uniform(0.5, 2.4), 2)
            else:
                loss = round(random.uniform(0.0, 0.2), 2)

            # Congestion state categorization
            if curr_util >= 95.0:
                saturation_state = "Severe Saturation (≥95%)"
            elif curr_util >= 85.0:
                saturation_state = "High Congestion (≥85%)"
            elif curr_util >= 70.0:
                saturation_state = "Moderate Load (≥70%)"
            else:
                saturation_state = "Normal (<70%)"

            records.append({
                "timestamp": t.isoformat(),
                "time_offset_sec": i * step_seconds,
                "link_id": link_id,
                "link_utilisation_pct": curr_util,
                "queue_depth_kb": round(queue_kb, 1),
                "jitter_ms": jitter,
                "packet_loss_pct": loss,
                "active_flows": random.randint(120, 240) if curr_util >= 85 else random.randint(40, 90),
                "is_burst": in_burst,
                "saturation_state": saturation_state
            })

        return pd.DataFrame(records)
