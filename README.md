# HybridFlowGuard: Application-Aware Bandwidth Policy & Telemetry Engine

HybridFlowGuard is a resilient, multi-tenant bandwidth management and policy enforcement platform designed for enterprise hybrid cloud networks. It dynamically evaluates application flows, isolates tenants, mitigates network bufferbloat, and enforces strict QoS guarantees during peak congestion and adverse edge conditions.

---

## 🚀 Key Improvements & Milestone Features

### 1. Active Congestion Simulation Pipeline
- **Baseline (FIFO) vs Policy-Enforced (HybridFlowGuard)**: Empirically benchmarks unmanaged FIFO bufferbloat against dynamic priority queuing and token-bucket shaping.
- **Queue & Saturation Dynamics**: Models finite buffer queues ($2500\text{ KB}$), tail drop packet loss, queuing delays, and link throughput degradation.
- **Empirical KPIs**:
  - Critical throughput maintained at **$\ge 40.5\text{ Mbps}$ ($\ge 90\%$)** under $90\%$ and $98\%$ severe congestion.
  - Critical latency reduced from **$78-115\text{ ms}$** down to **$< 22\text{ ms}$**.
  - Packet loss curtailed from **$3.8-7.5\%$** down to **$< 0.4\%$**.
  - Buffer queue occupancy drained from **$>2300\text{ KB}$** down to **$< 400\text{ KB}$**.
- **Documentation**: See [`docs/congestion_simulation_pipeline.md`](docs/congestion_simulation_pipeline.md) for mathematical derivations, queueing models, and reproducibility guides.

### 2. Expanded Telemetry Simulator (Real-World Network Edge Cases)
- **Bursty Traffic Spikes**: Micro-burst generator simulating sudden $3.5\times - 8.0\times$ volume surges in non-critical flows (bulk backups, large downloads, video buffering).
- **High-Jitter Link Conditions**: Models stochastic packet delay variation (PDV) ($25-95\text{ ms}$, peaks $>150\text{ ms}$) typical of satellite links (Starlink/GEO), cellular 5G, or bufferbloated routers.
- **Dynamic Time-Series Telemetry**: Generates second-by-second link saturation, buffer depth, and jitter timelines.
- **Telemetry Dropout / Stale Metrics**: Evaluates edge fallback resilience when metrics are delayed $>45\text{s}$.

### 3. Interactive Multi-Role Dashboard (`dashboard.py`)
- **Multi-Role RBAC Views**:
  - **Admin**: Full command & control across all links, live decision inspector, cross-tenant policy manager.
  - **Network Manager**: Real-time link saturation matrix, bufferbloat gauges, and active congestion stress-testing.
  - **Organisation Manager**: Tenant-scoped flow enforcement view, departmental throttling breakdown, and tenant custom rules.
  - **External Partner**: Isolated partner extranet link monitor and mission-critical API SLA verification.
  - **Auditor / Viewer**: Read-only compliance scorecards and audit logs.
- **Real-Time Saturation Metrics**: Instantaneous link utilisation vs saturation thresholds ($70\%$ Warning, $85\%$ High, $95\%$ Severe), available headroom, and queue depth timeline.
- **Live Enforcement Decisions Feed**: Filterable stream of flow admissions with action badges (`GUARANTEE_MINIMUM`, `PRIORITISE`, `RATE_LIMIT`, `NORMAL`) and class breakdown charts.

---

## 🛠️ Quickstart & Execution

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Launch the Interactive Dashboard
```bash
streamlit run dashboard.py
```

### 3. Start the FastAPI REST Backend
```bash
uvicorn app.main:app --reload --port 8000
```
Interactive OpenAPI documentation will be available at `http://localhost:8000/docs`.

### 4. Run Benchmark Experiments via CLI
```bash
# Execute standalone active congestion benchmark
python -m experiments.run_experiment
```

### 5. Run the Automated Test Suite
```bash
pytest -v
```