import pytest
import os
from experiments.run_experiment import ExperimentRunner, EXPERIMENT_RESULTS_FILE

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

def test_experiment_runner_results_file_creation():
    # Verify results CSV is generated
    assert os.path.exists(EXPERIMENT_RESULTS_FILE)
