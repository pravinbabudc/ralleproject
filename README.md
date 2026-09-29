# HybridFlowGuard: Application-Aware Bandwidth Policy & Telemetry Engine

HybridFlowGuard is a resilient, multi-tenant bandwidth management, policy enforcement, and telemetry orchestration platform designed for enterprise hybrid cloud networks. It dynamically evaluates application flows, isolates tenants, mitigates network bufferbloat, and enforces strict QoS guarantees during peak congestion and adverse edge conditions.

---

## 📚 Technical Documentation Directory

- **[Active Congestion Simulation Pipeline Documentation](docs/congestion_simulation_pipeline.md)**: Mathematical queue formulations, M/M/1/K derivations, token-bucket shaping models, and benchmark results.
- **[Unit Testing Architecture & Error Boundaries Specification](docs/unit_testing_and_error_boundaries.md)**: Granular documentation of the 41-case test suite, 7 failure boundaries, and fault-tolerance containment mechanisms.
- **[Project Defense & Architecture Report (Section IV–VII)](docs/project_report_part2.md)**: System architecture, multi-tenant isolation, priority scoring equations, and edge case telemetry analysis.

---

## 📡 Complete REST API Endpoints Reference

The FastAPI backend exposes RESTful endpoints with OpenAPI 3.0 documentation available at `http://localhost:8000/docs`.

### Authentication & Role Headers
RBAC context is passed via HTTP request headers:
- `X-User-Role`: User role (`admin`, `network_manager`, `organisation_manager`, `external_partner`, `viewer`). Default: `admin`.
- `X-Organisation-ID`: Active tenant scope (e.g. `org_chennai_hq`). Default: `org_chennai_hq`.
- `X-Username`: Caller username for audit logs (e.g. `admin_user`).

---

### 1. Health & Fallback Telemetry Status

#### `GET /health`
- **Description**: Basic service health and uptime check.
- **Response** (`200 OK`):
  ```json
  {
    "status": "healthy",
    "service": "HybridFlowGuard Policy Engine",
    "version": "1.0.0",
    "timestamp": "2026-09-29T08:35:00.000Z"
  }
  ```

#### `GET /failures/status`
- **Description**: Real-time telemetry health monitor. Inspects stale flow timestamps ($>30\text{s}$), missing link utilisation sensors, and unclassified shadow traffic.
- **Response** (`200 OK`): `TelemetryStatus` schema.
  ```json
  {
    "status": "operational",
    "last_flow_timestamp": "2026-09-29T08:34:45.123Z",
    "last_utilisation_timestamp": "2026-09-29T08:35:00.000Z",
    "stale_flow_detected": false,
    "missing_link_utilisation_detected": false,
    "unknown_applications_count": 0,
    "fallback_active": false,
    "message": "All telemetry data sources online and healthy."
  }
  ```

---

### 2. Organisations & Infrastructure

#### `GET /organisations`
- **Description**: Lists tenant organisations with tenant isolation applied based on caller role.
- **Headers**: `X-User-Role`, `X-Organisation-ID`
- **Response** (`200 OK`): `List[OrganisationOut]` (`id`, `name`, `status`).

#### `GET /links`
- **Description**: Lists all physical and cloud link infrastructures, rated capacities (Mbps), and instantaneous utilisation.
- **Response** (`200 OK`): `List[LinkOut]` (`id`, `name`, `source`, `destination`, `capacity_mbps`, `utilisation_pct`, `status`).

#### `GET /applications`
- **Description**: Returns registered application catalog with default priority ratings and application classes.
- **Response** (`200 OK`): `List[ApplicationOut]` (`id`, `name`, `application_class`, `default_priority`).

#### `GET /users`
- **Description**: Lists user accounts (global for Admins/Network Managers, tenant-scoped for Org Managers).
- **Headers**: `X-User-Role`, `X-Organisation-ID`
- **Response** (`200 OK`): `List[UserOut]` (`id`, `username`, `organisation_id`, `role`).

---

### 3. Bandwidth Policies (CRUD & RBAC)

#### `GET /policies`
- **Description**: Retrieves bandwidth policies filtered according to caller's tenant permissions.
- **Response** (`200 OK`): `List[PolicyOut]`.

#### `POST /policies`
- **Description**: Creates a new bandwidth policy rule.
- **Permissions**: Requires write role (`admin`, `network_manager`, `organisation_manager`). Enforces tenant isolation.
- **Request Body** (`PolicyCreate`):
  ```json
  {
    "organisation_id": "org_chennai_hq",
    "application": "ERP",
    "application_class": "Critical",
    "priority": 90,
    "minimum_bandwidth_mbps": 40.0,
    "maximum_bandwidth_mbps": 100.0,
    "action": "PRIORITISE"
  }
  ```
- **Response** (`201 Created`): `PolicyOut`.
- **Error Codes**: `403 Forbidden` (read-only role or cross-tenant modification).

#### `PUT /policies/{policy_id}`
- **Description**: Updates an existing bandwidth policy rule and generates an audit log entry.
- **Request Body** (`PolicyUpdate`): Optional update fields (`priority`, `minimum_bandwidth_mbps`, `maximum_bandwidth_mbps`, `action`).
- **Response** (`200 OK`): `PolicyOut`.
- **Error Codes**: `403 Forbidden`, `404 Not Found`.

#### `DELETE /policies/{policy_id}`
- **Description**: Deletes a bandwidth policy rule and writes an audit log.
- **Response** (`200 OK`): `{"status": "success", "message": "Policy 'pol_xxx' successfully removed."}`.
- **Error Codes**: `403 Forbidden`, `404 Not Found`.

#### `GET /policy/decisions`
- **Description**: Returns recent policy engine decision records with computed priority scores and reasoning.
- **Query Params**: `limit: int = 100`.
- **Response** (`200 OK`): `List[PolicyDecisionOut]`.

#### `GET /audit-logs`
- **Description**: Retrieves administrative audit logs (Restricted to Managers and Admins).
- **Query Params**: `limit: int = 100`.
- **Response** (`200 OK`): `List[AuditLogOut]`.
- **Error Codes**: `403 Forbidden` (if caller is `viewer` or `external_partner`).

---

### 4. Flows & Real-Time Evaluation

#### `GET /flows`
- **Description**: Retrieves recent flow telemetry records filtered by caller tenant scope.
- **Query Params**: `limit: int = 200`.
- **Response** (`200 OK`): `List[FlowRecordOut]`.

#### `POST /flows`
- **Description**: Ingests a new flow record, classifies application, and synchronously evaluates policy action.
- **Request Body** (`FlowRecordCreate`):
  ```json
  {
    "organisation_id": "org_chennai_hq",
    "source_location": "Chennai Office",
    "destination": "Datacenter-A",
    "user_id": "usr_1001",
    "user_type": "Employee",
    "application": "ERP",
    "protocol": "TCP",
    "source_ip": "10.1.2.3",
    "destination_ip": "172.16.1.1",
    "bytes": 500000.0,
    "packets": 400,
    "latency_ms": 12.5,
    "packet_loss_pct": 0.0,
    "jitter_ms": 1.5,
    "burst_factor": 1.0,
    "link_id": "link_chennai_cloud",
    "link_capacity_mbps": 100.0,
    "link_utilisation_pct": 88.5,
    "service_priority": 85
  }
  ```
- **Response** (`201 Created`): `FlowRecordOut` with assigned `policy_action`.

#### `POST /policy/evaluate`
- **Description**: Direct evaluation endpoint. Returns policy action, priority score, bandwidth bounds, and rationale without saving to DB.
- **Request Body** (`PolicyEvalRequest`):
  ```json
  {
    "flow_id": "sim_001",
    "organisation_id": "org_chennai_hq",
    "application": "ERP",
    "application_class": "Critical",
    "link_id": "link_chennai_cloud",
    "link_utilisation_pct": 96.0,
    "service_priority": 90
  }
  ```
- **Response** (`200 OK`): `PolicyEvalResult` (`decision`, `priority_score`, `minimum_bandwidth_mbps`, `maximum_bandwidth_mbps`, `reason`, `stale_telemetry`, `warning`).

---

### 5. Experiments & Benchmarks

#### `POST /experiments/run`
- **Description**: Executes active congestion simulation pipeline comparing baseline FIFO vs HybridFlowGuard.
- **Request Body** (`ExperimentRunRequest`):
  ```json
  {
    "scenario": "Bursty traffic spike",
    "num_flows": 500
  }
  ```
- **Supported Scenarios**: `"90% congestion"`, `"98% congestion"`, `"Bursty traffic spike"`, `"High-jitter link"`, `"Bursty spike + High-jitter"`, `"Normal network"`.
- **Response** (`200 OK`): `ExperimentResultOut` with comparative metrics, KPI validations, and automated analysis report.

#### `GET /experiments/results`
- **Description**: Retrieves historical benchmark experiment runs stored in `experiments/results.csv`.
- **Response** (`200 OK`): List of historical experiment benchmark records.

---

## 🗄️ Relational Database Schema Specification

The database is built on SQLAlchemy and supports SQLite (default: `hybridflowguard.db`) and PostgreSQL via `DATABASE_URL`.

### Entity Schemas & Column DDL

#### 1. `organisations` Table
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | VARCHAR | PRIMARY KEY, INDEX | Unique tenant organization identifier (e.g. `org_chennai_hq`) |
| `name` | VARCHAR | NOT NULL | Human-readable organization name |
| `status` | VARCHAR | DEFAULT 'active' | Operational status: `active`, `suspended` |
- **Relationships**: One-to-Many with `users`, `flow_records`, `policies` (with cascade delete).

#### 2. `users` Table
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | VARCHAR | PRIMARY KEY, INDEX | Unique user account identifier |
| `username` | VARCHAR | UNIQUE, NOT NULL, INDEX | User login username |
| `organisation_id`| VARCHAR | FOREIGN KEY (`organisations.id`), NOT NULL | Associated tenant organization |
| `role` | VARCHAR | NOT NULL | RBAC role: `admin`, `network_manager`, `organisation_manager`, `external_partner`, `viewer` |

#### 3. `links` Table
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | VARCHAR | PRIMARY KEY, INDEX | Unique link identifier (e.g. `link_chennai_cloud`) |
| `name` | VARCHAR | NOT NULL | Descriptive link name |
| `source` | VARCHAR | NOT NULL | Source enterprise site or branch |
| `destination` | VARCHAR | NOT NULL | Terminating datacenter or cloud peering |
| `capacity_mbps`| FLOAT | NOT NULL, DEFAULT 100.0 | Total physical/virtual capacity in Mbps |
| `utilisation_pct`| FLOAT | NOT NULL, DEFAULT 0.0 | Instantaneous link saturation percentage ($0 - 100$) |
| `status` | VARCHAR | DEFAULT 'active' | Link status: `active`, `degraded`, `offline` |

#### 4. `applications` Table
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | VARCHAR | PRIMARY KEY, INDEX | Unique application slug identifier |
| `name` | VARCHAR | UNIQUE, NOT NULL | Standardized application name (e.g. ERP, VoIP) |
| `application_class`| VARCHAR | NOT NULL | QoS Tier: `Critical`, `Important`, `Normal`, `Non-critical` |
| `default_priority` | INTEGER | DEFAULT 50 | Baseline service priority weight ($1 - 100$) |

#### 5. `policies` Table
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | VARCHAR | PRIMARY KEY, INDEX | Unique policy identifier (e.g. `pol_12345678`) |
| `organisation_id`| VARCHAR | FOREIGN KEY (`organisations.id`), NOT NULL | Tenant organization scoping |
| `application` | VARCHAR | NULLABLE | Specific application name (or `None` for class default) |
| `application_class`| VARCHAR | NOT NULL | Target application tier |
| `priority` | INTEGER | DEFAULT 50 | Policy priority weight ($1 - 100$) |
| `minimum_bandwidth_mbps` | FLOAT | DEFAULT 0.0 | Guaranteed minimum bandwidth reservation floor (Mbps) |
| `maximum_bandwidth_mbps` | FLOAT | DEFAULT 100.0 | Maximum allowed rate-limit ceiling (Mbps) |
| `action` | VARCHAR | DEFAULT 'NORMAL' | Action: `PRIORITISE`, `RATE_LIMIT`, `GUARANTEE_MINIMUM`, `NORMAL` |

#### 6. `flow_records` Table
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | VARCHAR | PRIMARY KEY, INDEX | Unique flow identifier |
| `timestamp` | DATETIME | DEFAULT utcnow, INDEX | Ingestion timestamp |
| `organisation_id`| VARCHAR | FOREIGN KEY (`organisations.id`), NOT NULL | Tenant organization ID |
| `source_location`| VARCHAR | NOT NULL | Originating site |
| `destination` | VARCHAR | NOT NULL | Destination endpoint |
| `user_id` | VARCHAR | NOT NULL | Originating user identifier |
| `user_type` | VARCHAR | NOT NULL | User profile tier: Employee, Executive, etc. |
| `application` | VARCHAR | NOT NULL | Application name |
| `application_class`| VARCHAR | NOT NULL | QoS Tier |
| `protocol` | VARCHAR | DEFAULT 'TCP' | Protocol: TCP, UDP, HTTPS, SRTP, QUIC |
| `source_ip` | VARCHAR | NOT NULL | Source IPv4 address |
| `destination_ip` | VARCHAR | NOT NULL | Destination IPv4 address |
| `bytes` | FLOAT | DEFAULT 0.0 | Transfer volume in bytes |
| `packets` | INTEGER | DEFAULT 0 | Transmitted packet count |
| `latency_ms` | FLOAT | DEFAULT 10.0 | Observed latency in ms |
| `packet_loss_pct`| FLOAT | DEFAULT 0.0 | Observed packet loss percentage |
| `jitter_ms` | FLOAT | DEFAULT 1.0 | Packet Delay Variation (PDV) in ms |
| `burst_factor` | FLOAT | DEFAULT 1.0 | Micro-burst scaling factor |
| `link_id` | VARCHAR | FOREIGN KEY (`links.id`), NOT NULL | Link traversed |
| `link_capacity_mbps`| FLOAT | DEFAULT 100.0 | Link capacity in Mbps |
| `link_utilisation_pct`| FLOAT | DEFAULT 50.0 | Link saturation percentage |
| `service_priority`| INTEGER | DEFAULT 50 | Priority rating ($1 - 100$) |
| `policy_action` | VARCHAR | DEFAULT 'NORMAL' | Enforced policy action |

#### 7. `policy_decisions` Table
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | VARCHAR | PRIMARY KEY, INDEX | Unique decision record identifier |
| `flow_id` | VARCHAR | FOREIGN KEY (`flow_records.id`), NOT NULL | Related flow identifier |
| `decision` | VARCHAR | NOT NULL | Enforced action |
| `priority_score` | FLOAT | NOT NULL | Calculated multi-factor priority score |
| `reason` | TEXT | NOT NULL | Detailed human-readable evaluation rationale |
| `timestamp` | DATETIME | DEFAULT utcnow | Decision timestamp |

#### 8. `audit_logs` Table
| Column | Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | VARCHAR | PRIMARY KEY, INDEX | Unique audit log entry identifier |
| `timestamp` | DATETIME | DEFAULT utcnow | Audit event timestamp |
| `user_id` | VARCHAR | NOT NULL | Actor username |
| `action` | VARCHAR | NOT NULL | Action: `CREATE_POLICY`, `UPDATE_POLICY`, `DELETE_POLICY` |
| `details` | TEXT | NOT NULL | Tamper-evident details of modification |

---

## 🛠️ Verification & Test Suite Execution

HybridFlowGuard includes a comprehensive test suite of **41 automated unit and integration tests**:

```bash
# Execute entire test suite
pytest -v

# Run with coverage analysis
pytest --cov=app --cov=experiments tests/

# Execute individual suites
pytest tests/test_api.py -v           # API contracts & HTTP status codes
pytest tests/test_policy_engine.py -v # Rule evaluation & priority formulas
pytest tests/test_fallback.py -v      # Telemetry stale & missing metric fallback
pytest tests/test_permissions.py -v   # Multi-tenant RBAC enforcement
pytest tests/test_experiments.py -v   # Active congestion benchmark pipeline
```

---

## 🚀 Running the System Locally

1. **Launch Streamlit Interactive Dashboard**:
   ```bash
   streamlit run dashboard.py
   ```
2. **Launch FastAPI Backend**:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
3. **Run Standalone Active Congestion Benchmarks via CLI**:
   ```bash
   python -m experiments.run_experiment
   ```