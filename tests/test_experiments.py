import pytest
import os
import pandas as pd
from experiments.run_experiment import ExperimentRunner, ActiveCongestionPipeline, EXPERIMENT_RESULTS_FILE
from app.simulator import CongestionSimulator

def test_experiment_runner_90_percent_congestion():
    res = ExperimentRunner.run(scenario="90% congestion", num_flows=50)
    assert res["scenario"] == "90% congestion"
    assert res["link_utilisation_pct"] == 90.0
    assert "metrics_summary" in res
    assert len(res["metrics_summary"]) == 4

    # Critical application throughput KPI check
    crit_tp_metric = res["metrics_summary"][0]
    assert crit_tp_metric["metric"] == "Critical application throughput"
    assert crit_tp_metric["hybridflowguard"] > crit_tp_metric["baseline"]
    assert crit_tp_metric["result"] == "PASS"

    # Latency KPI check
    lat_metric = res["metrics_summary"][1]
    assert lat_metric["hybridflowguard"] < lat_metric["baseline"]

    # Packet loss KPI check
    loss_metric = res["metrics_summary"][2]
    assert loss_metric["hybridflowguard"] < loss_metric["baseline"]

    # Check error analysis text presence
    assert "Experimental Error & Performance Analysis" in res["error_analysis"]

def test_experiment_runner_severe_congestion():
    res = ExperimentRunner.run(scenario="98% congestion", num_flows=50)
    assert res["scenario"] == "98% congestion"
    assert res["link_utilisation_pct"] == 98.0
    crit_tp_metric = res["metrics_summary"][0]
    assert crit_tp_metric["result"] == "PASS"

def test_experiment_runner_bursty_traffic_spike():
    res = ExperimentRunner.run(scenario="Bursty traffic spike", num_flows=50)
    assert res["scenario"] == "Bursty traffic spike"
    assert "extended_metrics" in res
    assert "timeline_metrics" in res
    assert len(res["timeline_metrics"]) > 0

    # Under bursty spike, HFG throttles non-critical traffic and protects critical throughput
    crit_metric = res["metrics_summary"][0]
    assert crit_metric["hybridflowguard"] >= 40.5
    assert crit_metric["result"] == "PASS"

    # Verify buffer draining metric
    buffer_metric = next(m for m in res["extended_metrics"] if m["metric"] == "Buffer queue depth")
    assert buffer_metric["hybridflowguard"] < buffer_metric["baseline"]

def test_experiment_runner_high_jitter_link():
    res = ExperimentRunner.run(scenario="High-jitter link", num_flows=50)
    assert res["scenario"] == "High-jitter link"
    
    # Verify jitter mitigation metric
    jitter_metric = next(m for m in res["extended_metrics"] if "jitter" in m["metric"].lower())
    assert jitter_metric["hybridflowguard"] < jitter_metric["baseline"]
    assert jitter_metric["result"] == "PASS"

def test_active_congestion_pipeline_direct():
    pipeline = ActiveCongestionPipeline(link_capacity_mbps=100.0, buffer_capacity_kb=2500.0)
    result = pipeline.simulate(scenario="Bursty spike + High-jitter", num_flows=30)
    assert result["critical_throughput_hfg"] > result["critical_throughput_baseline"]
    assert result["critical_latency_hfg"] < result["critical_latency_baseline"]
    assert "flow_traces" in result
    assert len(result["flow_traces"]) > 0

def test_simulator_burst_and_jitter_generation():
    df_burst = CongestionSimulator.generate_dataset(count=50, scenario="Bursty traffic spike")
    assert "jitter_ms" in df_burst.columns
    assert "burst_factor" in df_burst.columns
    assert "is_burst" in df_burst.columns
    assert df_burst["burst_factor"].max() > 1.0

    df_jitter = CongestionSimulator.generate_dataset(count=50, scenario="High-jitter link")
    assert df_jitter["jitter_ms"].max() > 20.0

def test_simulator_time_series_telemetry():
    ts_df = CongestionSimulator.generate_time_series_telemetry(link_id="link_chennai_cloud", count=20, scenario="Bursty traffic spike")
    assert len(ts_df) == 20
    assert "link_utilisation_pct" in ts_df.columns
    assert "queue_depth_kb" in ts_df.columns
    assert "jitter_ms" in ts_df.columns
    assert "saturation_state" in ts_df.columns

def test_experiment_runner_results_file_creation():
    # Verify results CSV is generated
    assert os.path.exists(EXPERIMENT_RESULTS_FILE)
