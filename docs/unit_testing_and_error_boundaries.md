# Unit Testing Architecture & Error Boundaries Specification

This document provides a granular technical specification of the unit testing suite, error boundaries, failure domains, and fault-tolerance mechanisms in **HybridFlowGuard**.

---

## 1. Unit Testing Architecture

The HybridFlowGuard automated test suite is built on `pytest` and structured into five modular test suites covering API contracts, policy engine rules, fallback behavior, tenant isolation (RBAC), and empirical active congestion benchmarks.

```
tests/
├── test_api.py              # REST API contracts, RBAC HTTP headers, and error codes (400, 403, 404, 500)
├── test_policy_engine.py    # Priority scoring formula, congestion thresholds, and custom DB policy overrides
├── test_fallback.py         # Telemetry freshness, missing metrics, and unknown application fallback
├── test_permissions.py      # Multi-tenant RBAC permissions, write protection, and tenant filtering
└── test_experiments.py      # Active congestion pipeline, baseline vs HFG benchmarks, and edge case telemetry
```

### 1.1 Test Suite Breakdown

| Test Module | Test Name | Target Component | Description / Invariant Tested |
| :--- | :--- | :--- | :--- |
| **`test_api.py`** | `test_health_endpoint` | `GET /health` | Validates operational uptime status, service identity, and ISO-8601 timestamp. |
| | `test_failures_status_endpoint` | `GET /failures/status` | Verifies failure detection response schema, stale flow detection, and missing link flags. |
| | `test_organisations_endpoint` | `GET /organisations` | Tests tenant filtering via `X-User-Role` and `X-Organisation-ID` headers. |
| | `test_links_endpoint` | `GET /links` | Verifies link topology retrieval, capacities, and instantaneous utilisation. |
| | `test_applications_endpoint` | `GET /applications` | Verifies application catalog and default priority ratings. |
| | `test_create_and_update_policy` | `POST /policies`, `PUT /policies/{id}` | Tests policy creation and subsequent modification with audit log generation. |
| | `test_evaluate_policy_endpoint` | `POST /policy/evaluate` | Validates direct policy evaluation with real-time decision payload. |
| | `test_get_flows` | `GET /flows` | Tests flow record ingestion and tenant-scoped retrieval. |
| | `test_create_flow` | `POST /flows` | Tests synchronous flow ingestion and automatic policy evaluation on ingestion. |
| | `test_experiments_run_endpoint` | `POST /experiments/run` | Validates active congestion experiment execution over REST API. |
| | `test_experiments_results_endpoint`| `GET /experiments/results` | Tests historical benchmark results retrieval from persistent storage. |
| **`test_policy_engine.py`** | `test_priority_score_calculation` | `PolicyEngine.calculate_priority_score` | Validates $\text{PriorityScore} = P_{\text{service}} \times W_{\text{class}} \times W_{\text{org}}$ formula. |
| | `test_evaluate_critical_severe_congestion` | `PolicyEngine.evaluate` | Invariant: Link load $\ge 95\%$ on Critical class triggers `GUARANTEE_MINIMUM`. |
| | `test_evaluate_noncritical_high_congestion` | `PolicyEngine.evaluate` | Invariant: Link load $\ge 85\%$ on Non-critical class triggers `RATE_LIMIT`. |
| | `test_evaluate_important_moderate_congestion` | `PolicyEngine.evaluate` | Invariant: Link load $\ge 70\%$ on Important class triggers `PRIORITISE`. |
| | `test_evaluate_normal_uncongested` | `PolicyEngine.evaluate` | Invariant: Link load $< 70\%$ returns standard `NORMAL` action. |
| | `test_evaluate_unknown_application` | `PolicyEngine.evaluate` | Tests fallback classification and conservative `RATE_LIMIT` clamping. |
| | `test_evaluate_custom_policy_override` | `PolicyEngine.evaluate` | Tests tenant-specific database policy overrides taking precedence over defaults. |
| **`test_fallback.py`** | `test_evaluate_flow_freshness_fresh` | `FallbackEngine.evaluate_flow_freshness` | Fresh timestamp ($\le 30\text{s}$) returns `is_stale=False`. |
| | `test_evaluate_flow_freshness_stale` | `FallbackEngine.evaluate_flow_freshness` | Aged timestamp ($> 30\text{s}$) triggers `is_stale=True` with warning. |
| | `test_resolve_link_utilisation_valid` | `FallbackEngine.resolve_link_utilisation` | Valid utilisation reading ($0-100\%$) updates in-memory cache and returns directly. |
| | `test_resolve_link_utilisation_missing_with_cache`| `FallbackEngine.resolve_link_utilisation` | Missing reading (`None`) falls back to cached last-known-good metric. |
| | `test_resolve_link_utilisation_missing_no_history`| `FallbackEngine.resolve_link_utilisation` | Unseen link with missing metric defaults conservatively to $50.0\%$. |
| | `test_resolve_unknown_application_known` | `FallbackEngine.resolve_unknown_application` | Known application class passes through unmodified. |
| | `test_resolve_unknown_application_unknown` | `FallbackEngine.resolve_unknown_application` | Unclassified application (`UNKNOWN`) is mapped to `RATE_LIMIT` with alert. |
| | `test_isolated_org_policy_app_match` | `FallbackEngine.get_isolated_org_policy` | Policy scoped to specific application name takes highest precedence. |
| | `test_isolated_org_policy_class_match`| `FallbackEngine.get_isolated_org_policy` | Policy scoped to application class acts as tenant fallback. |
| | `test_isolated_org_policy_no_cross_tenant_leak`| `FallbackEngine.get_isolated_org_policy` | Invariant: Tenant A's policies are never returned for Tenant B. |
| **`test_permissions.py`** | `test_role_write_permissions` | `PermissionChecker.validate_role_for_write` | Confirms `admin`, `network_manager`, and `organisation_manager` have write access. |
| | `test_role_write_denied_for_read_only`| `PermissionChecker.validate_role_for_write` | Invariant: `viewer` and `external_partner` raise `PermissionError` on write. |
| | `test_enforce_tenant_isolation_admin` | `PermissionChecker.enforce_tenant_isolation` | `admin` and `network_manager` can operate across all tenant IDs. |
| | `test_enforce_tenant_isolation_org_manager`| `PermissionChecker.enforce_tenant_isolation` | `organisation_manager` operating on different tenant raises `PermissionError`. |
| | `test_filter_records_by_tenant_admin` | `PermissionChecker.filter_records_by_tenant` | Administrators receive complete unfiltered dataset. |
| | `test_filter_records_by_tenant_manager`| `PermissionChecker.filter_records_by_tenant` | Tenant managers receive strictly their assigned organization's records. |
| **`test_experiments.py`** | `test_experiment_runner_90_percent_congestion` | `ActiveCongestionPipeline.simulate` | Invariant: Critical throughput under 90% congestion exceeds baseline and meets target ($\ge 40.5\text{ Mbps}$). |
| | `test_experiment_runner_severe_congestion` | `ActiveCongestionPipeline.simulate` | Invariant: Under 98% severe saturation, Critical throughput meets SLA target. |
| | `test_experiment_runner_bursty_traffic_spike` | `ActiveCongestionPipeline.simulate` | Validates non-critical rate-limiting and buffer draining during micro-bursts. |
| | `test_experiment_runner_high_jitter_link` | `ActiveCongestionPipeline.simulate` | Validates jitter mitigation via priority queuing over variable delay links. |
| | `test_active_congestion_pipeline_direct` | `ActiveCongestionPipeline` direct call | Validates standalone execution and timeline series output. |
| | `test_simulator_burst_and_jitter_generation` | `CongestionSimulator.generate_dataset` | Confirms `jitter_ms`, `burst_factor`, and `is_burst` attributes are generated. |
| | `test_simulator_time_series_telemetry` | `CongestionSimulator.generate_time_series_telemetry` | Validates time-series dataframe fields and saturation status categories. |
| | `test_experiment_runner_results_file_creation` | Results Persistence | Confirms `experiments/results.csv` is created and populated. |

---

## 2. Granular Error Boundaries & Fault Tolerance

HybridFlowGuard establishes seven strict error boundaries that isolate subsystems, preventing transient telemetry anomalies, network buffer overruns, or malicious cross-tenant requests from destabilizing the core policy engine.

```
+----------------------------------------------------------------------------------------------------+
|                                    BOUNDARY 4: RBAC & TENANT ISOLATION                             |
|  - Blocks unauthorized writes (HTTP 403 Forbidden)                                                 |
|  - Prevents cross-tenant data leaks at the query layer                                              |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                                                  v
+----------------------------------------------------------------------------------------------------+
|                                  BOUNDARY 1: TELEMETRY AGE & STALENESS                             |
|  - Evaluates Δt = now - timestamp. If Δt > 30s: activates stale_telemetry flag                    |
|  - Fallback: Maintains Last-Known-Good policy allocations without dropping sessions                |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                                                  v
+----------------------------------------------------------------------------------------------------+
|                                  BOUNDARY 2: MISSING LINK METRIC INTEGRITY                         |
|  - Validates 0 <= LinkUtilisation <= 100%. If None or invalid:                                     |
|  - Fallback: In-memory cache -> DB recorded value -> Conservative Default (50% or 85%)             |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                                                  v
+----------------------------------------------------------------------------------------------------+
|                                  BOUNDARY 3: APPLICATION CLASSIFICATION                            |
|  - Intercepts unclassified signatures (Shadow IT / unknown protocols)                              |
|  - Fallback: Maps to 'UNKNOWN' class and enforces conservative RATE_LIMIT (Max 10 Mbps)            |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                                                  v
+----------------------------------------------------------------------------------------------------+
|                                  BOUNDARY 7: LINK BUFFER & QUEUE OVERFLOW                          |
|  - Absorbs non-critical bursts via token-bucket shaping (Ceiling: 12-15 Mbps)                      |
|  - Safeguards Critical queues against Head-of-Line blocking and tail drops                         |
+-------------------------------------------------+--------------------------------------------------+
                                                  |
                                                  v
+----------------------------------------------------------------------------------------------------+
|                                  BOUNDARY 5 & 6: DATABASE & CSV STORAGE RESILIENCE                 |
|  - Auto-migration check on startup adds missing columns dynamically                                |
|  - on_bad_lines='skip' ensures corrupted CSV rows never crash API endpoints                        |
+----------------------------------------------------------------------------------------------------+
```

---

### Detailed Boundary Specifications

#### Boundary 1: Telemetry Age & Stale Timestamp Boundary
- **Failure Condition**: Telemetry agent delayed by WAN outages, network partition, or clock drift ($\Delta t > 30\text{ seconds}$).
- **Containment Mechanism**:
  ```python
  time_diff = (now - timestamp).total_seconds()
  if time_diff > TELEMETRY_STALE_THRESHOLD_SECONDS:
      return True, f"Stale flow telemetry detected (age: {int(time_diff)}s > threshold {TELEMETRY_STALE_THRESHOLD_SECONDS}s)."
  ```
- **Error Behavior**: The `stale_telemetry` flag is marked `True`, and an audit annotation is appended to the decision record. The policy engine maintains existing bandwidth allocations instead of dropping sessions.

#### Boundary 2: Missing or Corrupted Link Metric Boundary
- **Failure Condition**: Link utilisation sensor returns `None`, negative values, or values $>100\%$.
- **Containment Mechanism**: Tri-tiered hierarchical resolution:
  1. **Tier 1 (In-Memory Hot Cache)**: Uses last valid reading recorded for `link_id`.
  2. **Tier 2 (Database Persistence)**: Queries historical link record from `links` table.
  3. **Tier 3 (Safe Conservative Default)**: Applies $50.0\%$ (or $85.0\%$ under congestion warnings) to protect high-priority queues.
- **Error Behavior**: System logs a degradation warning to `GET /failures/status` while maintaining zero downtime.

#### Boundary 3: Shadow IT & Unclassified Application Boundary
- **Failure Condition**: Novel, unclassified, or evasive application signature detected.
- **Containment Mechanism**:
  ```python
  if app_class == "UNKNOWN" or not app_name:
      return "UNKNOWN", "RATE_LIMIT", "Unknown application. Clamping to conservative 10 Mbps RATE_LIMIT."
  ```
- **Error Behavior**: The flow is assigned a deflated priority weight ($W_{\text{UNKNOWN}} = 0.5$) and clamped to $\le 10\text{ Mbps}$, preventing shadow traffic from saturating enterprise queues.

#### Boundary 4: Multi-Tenant RBAC & Authorization Boundary
- **Failure Condition**: User with `viewer` or `external_partner` role attempts a write (`POST`, `PUT`, `DELETE`), or an `organisation_manager` attempts to access/modify a neighboring tenant's policy.
- **Containment Mechanism**:
  ```python
  if user.role not in ALLOWED_WRITE_ROLES:
      raise HTTPException(status_code=403, detail="Role does not have write permissions.")
  if user.role == "organisation_manager" and target_org != user.organisation_id:
      raise HTTPException(status_code=403, detail="Cross-tenant modification prohibited.")
  ```
- **Error Behavior**: Immediate HTTP 403 Forbidden response; administrative audit log generated with user identity, timestamp, and rejected payload.

#### Boundary 5: Database Schema Auto-Migration Boundary
- **Failure Condition**: Newly introduced schema columns (e.g., `jitter_ms`, `burst_factor`) missing from pre-existing SQLite databases.
- **Containment Mechanism**:
  ```python
  def run_migrations():
      with engine.connect() as conn:
          cols = [c["name"] for c in inspect(conn).get_columns("flow_records")]
          if "jitter_ms" not in cols:
              conn.execute(text("ALTER TABLE flow_records ADD COLUMN jitter_ms FLOAT DEFAULT 1.0"))
  ```
- **Error Behavior**: Executed automatically on engine initialization in `app/database.py`. Guarantees backwards compatibility across test sessions without manual SQL script execution.

#### Boundary 6: Telemetry CSV Ingestion & Parsing Boundary
- **Failure Condition**: Outdated or inconsistent CSV schema rows present in `experiments/results.csv`.
- **Containment Mechanism**:
  ```python
  df = pd.read_csv(results_file, on_bad_lines="skip")
  ```
- **Error Behavior**: Incompatible lines are safely skipped, preventing parser termination and returning HTTP 200 with all valid records.

#### Boundary 7: Link Buffer & Queue Overflow Boundary
- **Failure Condition**: Aggregate flow arrival rate exceeds physical capacity ($\Lambda(t) > C$), causing buffer accumulation toward $2500\text{ KB}$.
- **Containment Mechanism**: Token-bucket rate limiting restricts Non-critical flows to $\le 12-15\text{ Mbps}$. Dedicated priority queue servicing drains critical queues ahead of non-critical packets.
- **Error Behavior**: Non-critical flows absorb drops within their bounded queue slice; Critical transactional traffic experiences $< 0.4\%$ drop and $< 22\text{ ms}$ latency.

---

## 3. Verification & CI/CD Command Reference

To run the complete test suite:
```bash
# Run all 41 test cases with verbose output
pytest -v

# Run specific test modules
pytest tests/test_api.py -v
pytest tests/test_policy_engine.py -v
pytest tests/test_fallback.py -v
pytest tests/test_permissions.py -v
pytest tests/test_experiments.py -v

# Run with test coverage report
pytest --cov=app --cov=experiments tests/
```
