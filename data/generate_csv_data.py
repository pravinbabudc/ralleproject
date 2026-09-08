import os
import pandas as pd
from app.simulator import CongestionSimulator

DATA_DIR = os.path.dirname(__file__)

def generate_all_csvs():
    os.makedirs(DATA_DIR, exist_ok=True)

    print("Generating sample_flows.csv...")
    df_sample = CongestionSimulator.generate_dataset(count=2000, scenario="Normal network")
    df_sample.to_csv(os.path.join(DATA_DIR, "sample_flows.csv"), index=False)

    print("Generating normal_flows.csv...")
    df_normal = CongestionSimulator.generate_dataset(count=1500, scenario="Normal network")
    df_normal.to_csv(os.path.join(DATA_DIR, "normal_flows.csv"), index=False)

    print("Generating congested_flows.csv...")
    df_congested = CongestionSimulator.generate_dataset(count=1500, scenario="90% congestion")
    df_congested.to_csv(os.path.join(DATA_DIR, "congested_flows.csv"), index=False)

    print("Generating failure_flows.csv...")
    # Failure dataset includes missing link utilisation, delayed timestamps, and unknown applications
    df_failure = CongestionSimulator.generate_dataset(count=1000, scenario="98% congestion")
    
    # Introduce failure telemetry artifacts
    # 1. Unknown applications
    df_failure.loc[df_failure.index[:100], "application"] = "CustomUnregisteredProtocol"
    df_failure.loc[df_failure.index[:100], "application_class"] = "UNKNOWN"
    
    # 2. Missing link utilisation
    df_failure.loc[df_failure.index[100:200], "link_utilisation_pct"] = None

    df_failure.to_csv(os.path.join(DATA_DIR, "failure_flows.csv"), index=False)

    print("All CSV datasets successfully generated!")

if __name__ == "__main__":
    generate_all_csvs()
