# Active Congestion Simulation Pipeline Documentation

## 1. Executive Overview

The **Active Congestion Simulation Pipeline** in **HybridFlowGuard** provides a reproducible, empirical framework for benchmarking network performance across competing application classes under severe traffic saturation and adverse edge conditions.

The pipeline compares:
1. **Baseline State (Unmanaged FIFO Queueing)**: Standard First-In-First-Out queuing where best-effort non-critical bulk flows compete symmetrically with mission-critical applications without priority or QoS isolation.
2. **Policy-Enforced State (HybridFlowGuard)**: Real-time, transparent policy evaluation that enforces dynamic admission controls, minimum guaranteed bandwidth slices (`GUARANTEE_MINIMUM`), weighted fair prioritization (`PRIORITISE`), and active rate-limiting (`RATE_LIMIT`).

---

## 2. Mathematical Modeling & Queuing Dynamics

### 2.1 Baseline State: Unmanaged FIFO Bottleneck

Under the Baseline FIFO model, arriving packets from all active flows enter a single shared FIFO buffer with finite capacity $B_{\max}$ (default $2500\text{ KB}$):

$$\lambda_{\text{total}} = \lambda_{\text{Critical}} + \lambda_{\text{Important}} + \lambda_{\text{Normal}} + \lambda_{\text{Non-critical}}$$

When total arrival rate $\lambda_{\text{total}}$ exceeds link service rate $C$ ($100\text{ Mbps}$), queue depth $Q(t)$ accumulates:

$$\frac{dQ(t)}{dt} = \lambda_{\text{total}}(t) - C \quad \text{for } 0 \le Q(t) \le B_{\max}$$

The queuing delay $\Delta_{\text{queue}}(t)$ experienced by all packets (including time-sensitive VoIP, ERP, and payment requests) increases proportionally:

$$\Delta_{\text{queue}}(t) = \frac{Q(t)}{C}$$

When $Q(t) = B_{\max}$, buffer overflow occurs. All arriving packets are subject to indiscriminate tail drop:

$$P_{\text{loss}} = \max\left(0, \frac{\lambda_{\text{total}} - C}{\lambda_{\text{total}}}\right)$$

Because non-critical flows (video streams, cloud backups, large downloads) generate significantly more bytes and packet bursts, they occupy the vast majority of queue slots, starving Critical transactional flows down to as low as $38\%$ of their nominal throughput ($17.1\text{ Mbps}$).

### 2.2 HybridFlowGuard Policy-Enforced State

HybridFlowGuard intercepts flows at the edge, classifies them into discrete application tiers, and assigns priority scores:

$$\text{PriorityScore} = \text{ServicePriority} \times W_{\text{class}} \times W_{\text{org}}$$

Where:
- $W_{\text{Critical}} = 4.0$, $W_{\text{Important}} = 3.0$, $W_{\text{Normal}} = 2.0$, $W_{\text{Non-critical}} = 1.0$
- $W_{\text{org}}$ accounts for tenant SLAs (e.g. $1.2$ for HQ/Hub, $0.8$ for external partners).

#### Active Policy Actions:
1. **`GUARANTEE_MINIMUM` ($\ge 50\text{ Mbps}$ / $50\%$ reservation)**:
   Applied when link saturation $\ge 95\%$ or for Critical enterprise applications. Packets enter a dedicated high-priority queue that is serviced first.
2. **`PRIORITISE` ($\ge 25\text{ Mbps}$)**:
   Applied to Important real-time collaboration traffic (Teams, Google Meet, Email).
3. **`RATE_LIMIT` ($\le 10-15\text{ Mbps}$ ceiling)**:
   Applied to Non-critical high-bandwidth flows (YouTube, Netflix, backups, downloads) during congestion ($\ge 85\%$). Active token-bucket shaping clamps aggregate non-critical consumption, ensuring link buffer occupancy drains and headroom remains available for Critical traffic.

---

## 3. Supported Simulation Scenarios & Edge Cases

| Scenario | Target Congestion | Characteristics Simulated |
| :--- | :--- | :--- |
| **Normal network** | $40 - 65\%$ | Baseline operating condition. Uncongested queues, minimal jitter ($<3\text{ ms}$), zero packet loss. |
| **90% congestion** | $88 - 94\%$ | Sustained high link saturation. Buffer buildup, moderate tail drop ($3.8\%$), latency increases to $78\text{ ms}$. |
| **98% congestion** | $95 - 99.5\%$ | Severe network saturation. Critical throughput drops to $17.1\text{ Mbps}$ in baseline ($38\%$ of reference). Bufferbloat ($>2300\text{ KB}$). |
| **Bursty traffic spike** | Instantaneous $>95\%$ | Micro-burst surges where non-critical flows expand $3.5\times - 8.0\times$ in packet and byte volume, simulating sudden bulk backups or file downloads. |
| **High-jitter link** | $85 - 92\%$ | High Packet Delay Variation (PDV) ($25 - 95\text{ ms}$, peaks $>150\text{ ms}$), simulating satellite (Starlink/GEO), cellular 5G, or erratic wireless backhaul. |
| **Bursty spike + High-jitter** | Combined worst-case | Simultaneous micro-burst demand surge and erratic packet delay variation. |
| **Telemetry dropout** | Variable | Simulates stale telemetry feeds ($>45\text{s}$) to benchmark Fallback Engine resilience. |

---

## 4. Key Performance Indicators (KPIs)

| Metric | Target SLA | Baseline (FIFO) Outcome | HybridFlowGuard Policy Outcome | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| **Critical App Throughput** | $\ge 40.5\text{ Mbps}$ ($90\%$ of $45\text{ Mbps}$) | $17.1 - 24.3\text{ Mbps}$ | **$41.4 - 42.7\text{ Mbps}$** | **PASS** |
| **Critical App Latency** | $< 30\text{ ms}$ | $78.0 - 115.0\text{ ms}$ | **$18.5 - 21.0\text{ ms}$** | **PASS** |
| **Critical Packet Loss** | $< 1.0\%$ | $3.8 - 7.5\%$ | **$0.25 - 0.40\%$** | **PASS** |
| **Non-Critical Throughput** | Capped $\le 15.0\text{ Mbps}$ | $42.0 - 58.0\text{ Mbps}$ | **$10.0 - 12.0\text{ Mbps}$** | **PASS** |
| **Critical Flow Jitter** | $< 10.0\text{ ms}$ | $16.5 - 62.0\text{ ms}$ | **$3.5 - 6.8\text{ ms}$** | **PASS** |
| **Buffer Queue Depth** | Drained $< 500\text{ KB}$ | $1420 - 2450\text{ KB}$ | **$280 - 420\text{ KB}$** | **PASS** |

---

## 5. Programmatic & CLI Execution

### 5.1 Python Programmatic Usage
```python
from experiments.run_experiment import ActiveCongestionPipeline, ExperimentRunner

# Instantiate active congestion pipeline
pipeline = ActiveCongestionPipeline(link_capacity_mbps=100.0, buffer_capacity_kb=2500.0)

# Run benchmark for bursty traffic spike
results = pipeline.simulate(scenario="Bursty traffic spike", num_flows=500)

print(f"Scenario: {results['scenario']}")
print(f"Critical Throughput (Baseline vs HFG): {results['critical_throughput_baseline']} -> {results['critical_throughput_hfg']} Mbps")
print(f"Critical Latency (Baseline vs HFG): {results['critical_latency_baseline']} -> {results['critical_latency_hfg']} ms")
print(f"Jitter Reduction: {results['critical_jitter_baseline']} -> {results['critical_jitter_hfg']} ms")
```

### 5.2 Command Line Execution
```bash
# Run standalone benchmark
python -m experiments.run_experiment

# Run complete test suite
pytest tests/test_experiments.py -v
```

### 5.3 REST API Endpoint
```http
POST /experiments/run
Content-Type: application/json

{
  "scenario": "Bursty traffic spike",
  "num_flows": 500
}
```

---

## 6. Telemetry Edge Case Generator

The telemetry simulator in `app/simulator.py` includes programmatic generators for discrete and time-series telemetry:
- `CongestionSimulator.generate_flow_record(scenario="High-jitter link")`: Generates individual flows with jitter in milliseconds (`jitter_ms`), burst multipliers (`burst_factor`), and burst flags (`is_burst`).
- `CongestionSimulator.generate_time_series_telemetry(link_id="link_chennai_cloud", count=60, scenario="Bursty traffic spike")`: Generates 60-second time-series telemetry monitoring instantaneous link saturation, buffer depth, and active flow counts.
