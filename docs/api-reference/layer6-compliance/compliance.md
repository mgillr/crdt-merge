# crdt_merge.compliance — Regulatory Compliance Auditing

> **Module**: `crdt_merge/compliance.py`
> **Layer**: 6 — Verification & Compliance
> **LOC**: 932
> **Version**: 0.9.2
---

## Overview

The `crdt_merge.compliance` module provides regulatory compliance auditing and
reporting for CRDT merge operations. It validates merge, unmerge, and access
events against four major compliance frameworks:

| Framework     | Focus Area                                 |
|---------------|--------------------------------------------|
| **EU AI Act** | AI system transparency, risk management    |
| **GDPR**      | Data privacy, right to erasure, consent    |
| **HIPAA**     | Healthcare data access, encryption, audit  |
| **SOX**       | Financial data integrity, change management|

The module records operational events (merge, unmerge, access) and evaluates
them against framework-specific rules. Each rule check produces a
`ComplianceFinding`, and a full `ComplianceReport` aggregates all findings
with an overall compliance status (`compliant`, `partial`, or `non_compliant`).

**Key design points:**

- **Dynamic dispatch** — Rule definitions in `_FRAMEWORK_RULES` map a `check`
  string to a `_check_{name}` method on `ComplianceAuditor` via `getattr`.
  This allows framework rules to be extended without modifying the `validate()`
  loop.
- **Standalone capable** — All integration imports (`audit`, `provenance`,
  `unmerge`, `rbac`) are wrapped in `try/except` blocks, so the module works
  even when peer modules are unavailable.
- **No thread-safety guarantees** — Event lists (`_merge_events`,
  `_unmerge_events`, `_access_events`) are plain Python lists with no locking.
  Concurrent writes from multiple threads may cause data races. See
  [Known Issues](#known-issues) for details.

---

## Quick Start

### Example 1 — GDPR Compliance Audit

```python
from crdt_merge.compliance import ComplianceAuditor

# 1. Create an auditor targeting GDPR
auditor = ComplianceAuditor(framework="gdpr", node_id="eu-west-1")

# 2. Record merge events with metadata
auditor.record_merge(
    operation="merge",
    input_hash="sha256:abc123",
    output_hash="sha256:def456",
    metadata={"consent": True, "lawful_basis": "Art. 6(1)(a)"},
)

# 3. Record an unmerge (erasure) event
auditor.record_unmerge(
    subject_id="user-42",
    fields_removed=["email", "phone"],
    metadata={"reason": "GDPR Art. 17 request"},
)

# 4. Record access control events
auditor.record_access(
    user_id="admin-1",
    operation="read",
    resource="user-42",
    granted=True,
)

# 5. Validate and inspect report
report = auditor.validate()
print(report.status)       # "compliant"
print(report.to_text())    # Human-readable summary
print(report.summary())    # Quick dict overview
```

### Example 2 — HIPAA Compliance Audit

```python
from crdt_merge.compliance import ComplianceAuditor

auditor = ComplianceAuditor(framework="hipaa", node_id="us-east-1")

# Record encrypted merge operations
auditor.record_merge(
    operation="merge",
    input_hash="sha256:aaa111",
    output_hash="sha256:bbb222",
    metadata={"encrypted": True, "user_id": "dr-smith"},
)

# Record access controls
auditor.record_access(
    user_id="dr-smith",
    operation="read",
    resource="patient-record-99",
    granted=True,
)
auditor.record_access(
    user_id="intern-2",
    operation="write",
    resource="patient-record-99",
    granted=False,
)

report = auditor.validate()
print(report.status)  # "compliant" — audit trail, encryption, access controls present
```

### Example 3 — EU AI Act Full Report

```python
from crdt_merge.compliance import ComplianceAuditor, EUAIActReport

auditor = ComplianceAuditor(framework="eu_ai_act", node_id="model-v3")

# Record merge events with provenance and oversight
auditor.record_merge(
    operation="merge",
    input_hash="sha256:111",
    output_hash="sha256:222",
    metadata={
        "has_provenance": True,
        "reviewed": True,
        "risk_level": "limited",
        "description": "Merged training dataset v3",
    },
)

# Generate specialised EU AI Act report
eu_report = EUAIActReport(auditor)
risk = eu_report.risk_classification(
    system_description="Federated training data merger",
    is_high_risk=False,
)
print(risk["risk_level"])         # "minimal"
print(risk["classification"])     # "Minimal-risk AI system — voluntary codes of conduct"

transparency = eu_report.transparency_report()
print(transparency["transparency_score"])  # 1.0

# Full combined report
full = eu_report.generate()
print(full.status)                # "compliant"
print(full.metadata.keys())       # includes risk_classification, transparency, data_governance
```

---

## Module-Level Constants

### `_VALID_FRAMEWORKS`

```python
_VALID_FRAMEWORKS = frozenset({"eu_ai_act", "gdpr", "hipaa", "sox"})
```

Set of supported compliance frameworks. Passed to `ComplianceAuditor(framework=...)`.
An invalid value raises `ValueError`.

### `_VALID_SEVERITIES`

```python
_VALID_SEVERITIES = frozenset({"critical", "warning", "info"})
```

Allowed severity levels for compliance findings. Used in rule definitions.

### `_VALID_STATUSES`

```python
_VALID_STATUSES = frozenset({"pass", "fail", "not_applicable"})
```

Allowed statuses for individual findings. Note: the overall report status uses a
different vocabulary (`"compliant"`, `"non_compliant"`, `"partial"`).

### `_FRAMEWORK_RULES`

```python
_FRAMEWORK_RULES: types.MappingProxyType  # immutable mapping
```

Master registry of compliance rules keyed by framework name. Each rule is a dict
with the following keys:

| Key              | Type   | Description                                     |
|------------------|--------|-------------------------------------------------|
| `rule_id`        | `str`  | Unique identifier (e.g., `"EU_AI_ACT_ART_10"`)  |
| `severity`       | `str`  | `"critical"` \| `"warning"` \| `"info"`          |
| `description`    | `str`  | Human-readable explanation of the rule           |
| `check`          | `str`  | Suffix for dynamic dispatch → `_check_{check}`   |
| `recommendation` | `str`  | Remediation guidance (shown only on `"fail"`)    |

The `validate()` method iterates over the rules for the active framework,
looks up `_check_{rule["check"]}` via `getattr`, and calls it. If no method
is found, the finding defaults to `"not_applicable"`.

See [Compliance Rules Reference](#compliance-rules-reference) for the full
table of all 17 rules.

---

## Classes

---

### `CheckResult` (NamedTuple)

```python
class CheckResult(NamedTuple):
```

Typed result from internal compliance check methods. Returned by all
`_check_*` methods on `ComplianceAuditor`. Backward-compatible with
bare `(status, evidence)` tuples from earlier versions.

#### Fields

| Field     | Type               | Description                                              |
|-----------|--------------------|----------------------------------------------------------|
| `passed`  | `str`              | `"pass"`, `"fail"`, or `"not_applicable"`                |
| `message` | `str`              | Human-readable explanation of the check outcome          |
| `details` | `Dict[str, Any]`   | Supporting data (counts, reasons, evidence)              |

#### Example

```python
from crdt_merge.compliance import CheckResult

# Construct directly
result = CheckResult(passed="pass", message="Check passed", details={"count": 5})

print(result.passed)   # "pass"
print(result.message)  # "Check passed"
print(result.details)  # {"count": 5}

# Tuple unpacking still works (backward-compatible)
status, msg, info = result
print(status)  # "pass"
```

---

### `ComplianceFinding` (dataclass)

```python
@dataclass
class ComplianceFinding:
```

Represents a single compliance rule evaluation result.

#### Fields

| Field            | Type               | Default | Description                                          |
|------------------|--------------------|---------|------------------------------------------------------|
| `rule_id`        | `str`              | —       | Rule identifier (e.g., `"GDPR_ART_17"`)             |
| `severity`       | `str`              | —       | `"critical"` \| `"warning"` \| `"info"`              |
| `status`         | `str`              | —       | `"pass"` \| `"fail"` \| `"not_applicable"`           |
| `description`    | `str`              | —       | Human-readable explanation of the rule               |
| `recommendation` | `str`              | `""`    | Remediation guidance (empty string if passing)       |
| `evidence`       | `Dict[str, Any]`   | `{}`    | Supporting data for the finding                      |

#### Methods

##### `to_dict`

```python
def to_dict(self) -> Dict[str, Any]
```

Serialise the finding to a plain dictionary.

**Returns:** `Dict[str, Any]` — Dictionary with keys `rule_id`, `severity`,
`status`, `description`, `recommendation`, `evidence`.

**Example:**

```python
from crdt_merge.compliance import ComplianceFinding

finding = ComplianceFinding(
    rule_id="GDPR_ART_17",
    severity="critical",
    status="pass",
    description="Right to erasure — ability to remove personal data on request.",
    recommendation="",
    evidence={"unmerge_events": 3},
)

d = finding.to_dict()
print(d)
# {
#     "rule_id": "GDPR_ART_17",
#     "severity": "critical",
#     "status": "pass",
#     "description": "Right to erasure — ability to remove personal data on request.",
#     "recommendation": "",
#     "evidence": {"unmerge_events": 3},
# }
```

---

### `ComplianceReport` (dataclass)

```python
@dataclass
class ComplianceReport:
```

Full compliance report for a specific framework. Generated by
`ComplianceAuditor.validate()`.

#### Fields

| Field          | Type                       | Default | Description                                                |
|----------------|----------------------------|---------|------------------------------------------------------------|
| `framework`    | `str`                      | —       | Framework name (e.g., `"gdpr"`, `"hipaa"`)                 |
| `generated_at` | `float`                    | —       | Unix timestamp of report generation                        |
| `status`       | `str`                      | —       | `"compliant"` \| `"non_compliant"` \| `"partial"`          |
| `findings`     | `List[ComplianceFinding]`  | —       | Individual rule evaluation results                         |
| `metadata`     | `Dict[str, Any]`           | `{}`    | Extra contextual information (node_id, event counts, etc.) |

**Status derivation logic** (in `ComplianceAuditor.validate()`):

| Condition                                      | Overall status    |
|------------------------------------------------|-------------------|
| Any finding with `status="fail"` AND `severity="critical"` | `"non_compliant"` |
| Any finding with `status="fail"` (non-critical only)       | `"partial"`        |
| All findings pass or are not_applicable                     | `"compliant"`      |

#### Methods

##### `to_dict`

```python
def to_dict(self) -> Dict[str, Any]
```

Serialise the full report to a plain dictionary. Each `ComplianceFinding` in
`findings` is also serialised via its own `to_dict()`.

**Returns:** `Dict[str, Any]` — Dictionary with keys `framework`,
`generated_at`, `status`, `findings` (list of dicts), `metadata`.

**Example:**

```python
from crdt_merge.compliance import ComplianceAuditor

auditor = ComplianceAuditor(framework="sox", node_id="finance-node")
auditor.record_merge(
    operation="journal_entry",
    input_hash="sha256:aaa",
    output_hash="sha256:bbb",
    metadata={"user_id": "cfo-1"},
)
report = auditor.validate()
d = report.to_dict()
print(d["framework"])  # "sox"
print(d["status"])     # "compliant" or "partial" depending on rules
print(len(d["findings"]))  # 4 (SOX has 4 rules)
```

##### `to_text`

```python
def to_text(self) -> str
```

Render a human-readable summary report. Each finding is shown with an icon
(`` for pass, `` for fail, `—` for not_applicable), its rule ID, severity,
and description. Failed findings also show the recommendation.

Ends with a summary line: `"Summary: X passed, Y failed, Z n/a"`.

**Returns:** `str` — Multi-line formatted text.

**Example:**

```python
from crdt_merge.compliance import ComplianceAuditor

auditor = ComplianceAuditor(framework="gdpr", node_id="node-1")
auditor.record_merge(operation="merge", input_hash="sha256:abc", output_hash="sha256:def")
auditor.record_unmerge(subject_id="user-1", fields_removed=["email"])
report = auditor.validate()
print(report.to_text())
# Compliance Report — GDPR
# ============================================================
# Status:       partial
# Generated at: 1743426000.123
# Findings:     4
#
#   [] GDPR_ART_17 (critical): Right to erasure — ...
#   [] GDPR_ART_30 (critical): Records of processing activities — ...
#   [] GDPR_ART_7 (warning): Consent tracking — ...
#       → Record consent or lawful basis for each data processing operation.
#   [] GDPR_ART_25 (info): Data protection by design — ...
#       → Document data protection measures in system design.
#
# Summary: 2 passed, 2 failed, 0 n/a
```

##### `summary`

```python
def summary(self) -> Dict[str, Any]
```

Generate a quick status overview dictionary.

**Returns:** `Dict[str, Any]` with keys:

| Key                 | Type   | Description                                      |
|---------------------|--------|--------------------------------------------------|
| `framework`         | `str`  | Framework name                                   |
| `status`            | `str`  | Overall compliance status                        |
| `total_findings`    | `int`  | Total number of findings                         |
| `passed`            | `int`  | Count of `"pass"` findings                       |
| `failed`            | `int`  | Count of `"fail"` findings                       |
| `not_applicable`    | `int`  | Count of `"not_applicable"` findings             |
| `critical_failures` | `int`  | Count of findings that are both `"fail"` AND `"critical"` |

**Example:**

```python
from crdt_merge.compliance import ComplianceAuditor

auditor = ComplianceAuditor(framework="hipaa", node_id="hospital-1")
auditor.record_merge(operation="merge", input_hash="sha256:aaa", output_hash="sha256:bbb")
auditor.record_access(user_id="nurse-1", operation="read", resource="patient-10", granted=True)
report = auditor.validate()

s = report.summary()
print(s)
# {
#     "framework": "hipaa",
#     "status": "partial",
#     "total_findings": 4,
#     "passed": 3,
#     "failed": 1,
#     "not_applicable": 0,
#     "critical_failures": 1,
# }
```

---

### `ComplianceAuditor`

```python
class ComplianceAuditor:
```

Main compliance auditor. Records merge, unmerge, and access events, then
validates them against the rules of a target compliance framework.

#### Constructor

```python
def __init__(self, framework: str = "eu_ai_act", node_id: str = "default") -> None
```

**Parameters:**

| Parameter   | Type  | Default       | Description                                                           |
|-------------|-------|---------------|-----------------------------------------------------------------------|
| `framework` | `str` | `"eu_ai_act"` | Target compliance framework. Must be in `_VALID_FRAMEWORKS`.          |
| `node_id`   | `str` | `"default"`   | Identifier for the node being audited.                                |

**Raises:** `ValueError` — If `framework` is not in `_VALID_FRAMEWORKS`.

**Instance attributes set:**

| Attribute          | Type                     | Description                      |
|--------------------|--------------------------|----------------------------------|
| `framework`        | `str`                    | Active framework name            |
| `node_id`          | `str`                    | Node identifier                  |
| `_merge_events`    | `List[Dict[str, Any]]`   | Internal list of merge events    |
| `_unmerge_events`  | `List[Dict[str, Any]]`   | Internal list of unmerge events  |
| `_access_events`   | `List[Dict[str, Any]]`   | Internal list of access events   |

**Example:**

```python
from crdt_merge.compliance import ComplianceAuditor

# Default: EU AI Act
auditor = ComplianceAuditor()

# Explicit framework and node
auditor = ComplianceAuditor(framework="hipaa", node_id="us-east-1")

# Invalid framework raises ValueError
try:
    ComplianceAuditor(framework="pci_dss")
except ValueError as e:
    print(e)  # "Unknown framework 'pci_dss'. Supported: ['eu_ai_act', 'gdpr', 'hipaa', 'sox']"
```

---

#### Public Methods

##### `record_merge`

```python
def record_merge(
    self,
    operation: str,
    input_hash: str = "",
    output_hash: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None
```

Record a merge event. Events are stored in `_merge_events` and inspected
during validation.

**Parameters:**

| Parameter     | Type                         | Default | Description                                           |
|---------------|------------------------------|---------|-------------------------------------------------------|
| `operation`   | `str`                        | —       | Name of the merge operation (e.g., `"merge"`, `"encrypt"`) |
| `input_hash`  | `str`                        | `""`    | Cryptographic hash of the input data                  |
| `output_hash` | `str`                        | `""`    | Cryptographic hash of the output data                 |
| `metadata`    | `Optional[Dict[str, Any]]`   | `None`  | Arbitrary metadata (provenance, consent, etc.)        |

**Returns:** `None`

**Internal event format** (stored in `_merge_events`):

```python
{
    "operation": operation,
    "input_hash": input_hash,
    "output_hash": output_hash,
    "metadata": metadata or {},
    "timestamp": time.time(),
}
```

**Example:**

```python
auditor = ComplianceAuditor(framework="gdpr")

auditor.record_merge(
    operation="merge",
    input_hash="sha256:abc123",
    output_hash="sha256:def456",
    metadata={
        "consent": True,
        "lawful_basis": "Art. 6(1)(a)",
        "has_provenance": True,
    },
)
```

---

##### `record_unmerge`

```python
def record_unmerge(
    self,
    subject_id: str,
    fields_removed: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None
```

Record an unmerge (erasure / forget) event. Used for GDPR Art. 17 compliance.

**Parameters:**

| Parameter        | Type                         | Default | Description                                           |
|------------------|------------------------------|---------|-------------------------------------------------------|
| `subject_id`     | `str`                        | —       | Identifier of the data subject whose data was removed |
| `fields_removed` | `Optional[List[str]]`        | `None`  | List of field names that were erased                  |
| `metadata`       | `Optional[Dict[str, Any]]`   | `None`  | Arbitrary metadata about the erasure                  |

**Returns:** `None`

**Internal event format** (stored in `_unmerge_events`):

```python
{
    "subject_id": subject_id,
    "fields_removed": fields_removed or [],
    "metadata": metadata or {},
    "timestamp": time.time(),
}
```

**Example:**

```python
auditor = ComplianceAuditor(framework="gdpr")

auditor.record_unmerge(
    subject_id="user-42",
    fields_removed=["email", "phone", "address"],
    metadata={"reason": "GDPR Art. 17 request", "requested_by": "user-42"},
)
```

---

##### `record_access`

```python
def record_access(
    self,
    user_id: str,
    operation: str,
    resource: str,
    granted: bool,
    metadata: Optional[Dict[str, Any]] = None,
) -> None
```

Record an access control event. Used for HIPAA, SOX, and GDPR Art. 25 checks.

**Parameters:**

| Parameter   | Type                         | Default | Description                                            |
|-------------|------------------------------|---------|--------------------------------------------------------|
| `user_id`   | `str`                        | —       | Identifier of the user requesting access               |
| `operation` | `str`                        | —       | Requested operation (e.g., `"read"`, `"write"`)        |
| `resource`  | `str`                        | —       | Resource being accessed                                |
| `granted`   | `bool`                       | —       | Whether access was granted (`True`) or denied (`False`)|
| `metadata`  | `Optional[Dict[str, Any]]`   | `None`  | Arbitrary metadata about the access decision           |

**Returns:** `None`

**Internal event format** (stored in `_access_events`):

```python
{
    "user_id": user_id,
    "operation": operation,
    "resource": resource,
    "granted": granted,
    "metadata": metadata or {},
    "timestamp": time.time(),
}
```

**Example:**

```python
auditor = ComplianceAuditor(framework="hipaa")

auditor.record_access(
    user_id="dr-smith",
    operation="read",
    resource="patient-record-99",
    granted=True,
    metadata={"role": "attending_physician"},
)

auditor.record_access(
    user_id="intern-2",
    operation="write",
    resource="patient-record-99",
    granted=False,
    metadata={"role": "intern", "denial_reason": "insufficient_privileges"},
)
```

---

##### `validate`

```python
def validate(self) -> ComplianceReport
```

Validate all recorded events against the framework rules. This is the core
method that produces a compliance report.

**Dispatch mechanism:**

1. Looks up rules from `_FRAMEWORK_RULES[self.framework]`.
2. For each rule, resolves `_check_{rule["check"]}` via `getattr(self, ...)`.
3. If the checker method exists, calls it — expects return of `(status, evidence)`.
4. If no checker is found, defaults to `("not_applicable", {"reason": "No checker implemented for '{check}'"})`.
5. Sets `recommendation` from the rule dict only when `status == "fail"`.
6. Derives overall status from findings (see [ComplianceReport status derivation](#fields-1)).

**Returns:** `ComplianceReport`

**Example:**

```python
auditor = ComplianceAuditor(framework="eu_ai_act", node_id="node-1")

auditor.record_merge(
    operation="merge",
    input_hash="sha256:aaa",
    output_hash="sha256:bbb",
    metadata={"has_provenance": True, "reviewed": True, "risk_level": "minimal"},
)

report = auditor.validate()
print(report.status)              # "compliant"
print(len(report.findings))       # 5 (EU AI Act has 5 rules)
print(report.metadata["node_id"]) # "node-1"
print(report.metadata["merge_events"])   # 1
print(report.metadata["unmerge_events"]) # 0
print(report.metadata["access_events"])  # 0

for f in report.findings:
    print(f"{f.rule_id}: {f.status} ({f.severity})")
# EU_AI_ACT_ART_10: pass (critical)
# EU_AI_ACT_ART_12: pass (critical)
# EU_AI_ACT_ART_13: pass (warning)
# EU_AI_ACT_ART_14: pass (warning)
# EU_AI_ACT_ART_9: pass (info)
```

---

##### `generate_report`

```python
def generate_report(self) -> ComplianceReport
```

Alias for `validate()`. Provided for API convenience.

**Returns:** `ComplianceReport`

**Example:**

```python
auditor = ComplianceAuditor(framework="sox")
auditor.record_merge(operation="update", input_hash="sha256:aaa", output_hash="sha256:bbb")
report = auditor.generate_report()  # identical to auditor.validate()
```

---

##### `clear`

```python
def clear(self) -> None
```

Reset all recorded events. Clears `_merge_events`, `_unmerge_events`, and
`_access_events`.

**Returns:** `None`

**Example:**

```python
auditor = ComplianceAuditor(framework="gdpr")
auditor.record_merge(operation="merge")
print(len(auditor._merge_events))  # 1

auditor.clear()
print(len(auditor._merge_events))  # 0
print(len(auditor._unmerge_events))  # 0
print(len(auditor._access_events))  # 0
```

---

#### Class Methods

##### `from_audit_log`

```python
@classmethod
def from_audit_log(
    cls,
    audit_log: Any,
    framework: str = "eu_ai_act",
) -> ComplianceAuditor
```

Create a `ComplianceAuditor` pre-populated from an `AuditLog` instance.
Iterates over the audit log's entries and records each as a merge event.

**Parameters:**

| Parameter   | Type  | Default       | Description                                            |
|-------------|-------|---------------|--------------------------------------------------------|
| `audit_log` | `Any` | —             | An `AuditLog` object (or any iterable of entry-like objects) |
| `framework` | `str` | `"eu_ai_act"` | Target framework                                       |

**Entry resolution logic:**

1. Reads `node_id` from `audit_log.node_id` via `getattr` (default: `"default"`).
2. If `audit_log` has an `entries` attribute, uses that.
3. Otherwise, if `audit_log` is iterable, converts to list.
4. For each entry, extracts `operation`, `input_hash`, `output_hash`, `metadata`
   via `getattr` with safe defaults.

**Returns:** `ComplianceAuditor`

**Example:**

```python
from crdt_merge.compliance import ComplianceAuditor

# Using a mock audit log
class MockEntry:
    def __init__(self, operation, input_hash, output_hash, metadata):
        self.operation = operation
        self.input_hash = input_hash
        self.output_hash = output_hash
        self.metadata = metadata

class MockAuditLog:
    def __init__(self):
        self.node_id = "audit-node-1"
        self.entries = [
            MockEntry("merge", "sha256:aaa", "sha256:bbb", {"user_id": "admin"}),
            MockEntry("merge", "sha256:ccc", "sha256:ddd", {}),
        ]

log = MockAuditLog()
auditor = ComplianceAuditor.from_audit_log(log, framework="sox")
print(auditor.node_id)                  # "audit-node-1"
print(len(auditor._merge_events))       # 2

report = auditor.validate()
print(report.status)  # depends on event content
```

---

##### `from_provenance_log`

```python
@classmethod
def from_provenance_log(
    cls,
    provenance_log: Any,
    framework: str = "eu_ai_act",
) -> ComplianceAuditor
```

Create a `ComplianceAuditor` pre-populated from a `ProvenanceLog` instance.
Iterates over the log's records and records each as a merge event with
provenance metadata.

**Parameters:**

| Parameter        | Type  | Default       | Description                                            |
|------------------|-------|---------------|--------------------------------------------------------|
| `provenance_log` | `Any` | —             | A `ProvenanceLog` object (or any iterable of record-like objects) |
| `framework`      | `str` | `"eu_ai_act"` | Target framework                                       |

**Record resolution logic:**

1. Sets `node_id` to `"default"` (does **not** read from the provenance log).
2. If `provenance_log` has a `records` attribute, uses that.
3. Otherwise, if iterable, converts to list.
4. For each record, extracts `key`, `origin`, `conflict_count` via `getattr`.
5. Records merge events with `metadata={"key": ..., "origin": ..., "conflict_count": ..., "has_provenance": True}`.

**Returns:** `ComplianceAuditor`

**Example:**

```python
from crdt_merge.compliance import ComplianceAuditor

class MockRecord:
    def __init__(self, key, origin, conflict_count):
        self.key = key
        self.origin = origin
        self.conflict_count = conflict_count

class MockProvenanceLog:
    def __init__(self):
        self.records = [
            MockRecord("field_a", "node-1", 0),
            MockRecord("field_b", "node-2", 2),
        ]

plog = MockProvenanceLog()
auditor = ComplianceAuditor.from_provenance_log(plog, framework="eu_ai_act")
print(auditor.node_id)                  # "default"
print(len(auditor._merge_events))       # 2

# Provenance-tracked events pass EU AI Act Art. 10
report = auditor.validate()
for f in report.findings:
    if f.rule_id == "EU_AI_ACT_ART_10":
        print(f.status)  # "pass"
```

---

#### Private `_check_*` Methods

These methods implement the compliance rule checks. They are called via dynamic
dispatch from `validate()` — the `check` field in a rule definition maps to
`_check_{check}` on the `ComplianceAuditor` instance.

All `_check_*` methods share the same signature:

```python
def _check_{name}(self) -> CheckResult
```

**Returns:** `CheckResult` — a `NamedTuple` with fields `passed` (`str`),
`message` (`str`), and `details` (`Dict[str, Any]`). The `passed` field is
one of `"pass"`, `"fail"`, or `"not_applicable"`.

---

##### `_check_has_merge_provenance`

```python
def _check_has_merge_provenance(self) -> tuple
```

Check if merge events contain provenance metadata. A merge event passes if
it has `metadata.has_provenance == True`, a non-empty `input_hash`, or a
non-empty `output_hash`.

**Used by:** `EU_AI_ACT_ART_10`

**Logic:**

| Condition                                  | Status  | Evidence                                     |
|--------------------------------------------|---------|----------------------------------------------|
| No merge events recorded                   | `fail`  | `{"reason": "No merge events recorded."}`    |
| All events have provenance                 | `pass`  | `{"events_with_provenance": N, "total": N}`  |
| Some (but not all) have provenance         | `fail`  | `{"events_with_provenance": M, "total": N, "reason": "..."}`|
| No events have provenance data             | `fail`  | `{"reason": "No merge events have provenance data."}` |

---

##### `_check_has_audit_trail`

```python
def _check_has_audit_trail(self) -> tuple
```

Check if there is an audit trail — merge events with `input_hash` or
`output_hash` set.

**Used by:** `EU_AI_ACT_ART_12`, `HIPAA_AUDIT_TRAIL`

**Logic:**

| Condition                                  | Status  | Evidence                                     |
|--------------------------------------------|---------|----------------------------------------------|
| No merge events recorded                   | `fail`  | `{"reason": "No merge events recorded."}`    |
| All events have hashes                     | `pass`  | `{"events_with_hashes": N, "total": N}`      |
| Some (but not all) have hashes             | `fail`  | `{"events_with_hashes": M, "total": N, "reason": "..."}`|
| Events recorded but lack hashes            | `fail`  | `{"total": N, "reason": "..."}`              |

---

##### `_check_has_transparency_metadata`

```python
def _check_has_transparency_metadata(self) -> tuple
```

Check if merge events contain descriptive metadata. Passes if ≥ 50% of
events have non-empty metadata dicts.

**Used by:** `EU_AI_ACT_ART_13`

**Logic:**

| Condition                                       | Status  | Evidence                                      |
|-------------------------------------------------|---------|-----------------------------------------------|
| No merge events recorded                        | `fail`  | `{"reason": "No merge events recorded."}`     |
| ≥ 50% of events have metadata                   | `pass`  | `{"events_with_metadata": M, "total": N}`     |
| < 50% of events have metadata                   | `fail`  | `{"events_with_metadata": M, "total": N, "reason": "..."}` |

---

##### `_check_has_human_oversight`

```python
def _check_has_human_oversight(self) -> tuple
```

Check for evidence of human oversight in metadata. Looks for keys:
`"reviewed"`, `"approved"`, `"human_oversight"`, `"reviewer"`.

**Used by:** `EU_AI_ACT_ART_14`

**Logic:**

| Condition                                       | Status            | Evidence                                  |
|-------------------------------------------------|-------------------|-------------------------------------------|
| At least one event has oversight keys           | `pass`            | `{"events_with_oversight": N}`            |
| No merge events recorded                        | `not_applicable`  | `{"reason": "No merge events to check."}` |
| Events exist but no oversight evidence          | `fail`            | `{"reason": "No evidence of human oversight..."}` |

---

##### `_check_has_risk_classification`

```python
def _check_has_risk_classification(self) -> tuple
```

Check for risk classification metadata. Looks for `"risk_level"` or
`"risk_classification"` keys in event metadata.

**Used by:** `EU_AI_ACT_ART_9`

**Logic:**

| Condition                                       | Status            | Evidence                                  |
|-------------------------------------------------|-------------------|-------------------------------------------|
| Any event has risk classification               | `pass`            | `{"risk_documented": True}`               |
| No merge events recorded                        | `not_applicable`  | `{"reason": "No merge events to check."}` |
| Events exist but no risk classification         | `fail`            | `{"reason": "No risk classification documented."}` |

---

##### `_check_has_unmerge_capability`

```python
def _check_has_unmerge_capability(self) -> tuple
```

Check if unmerge / erasure capability has been exercised or recorded.

**Used by:** `GDPR_ART_17`

**Logic:**

| Condition                                       | Status  | Evidence                                              |
|-------------------------------------------------|---------|-------------------------------------------------------|
| Unmerge events exist                            | `pass`  | `{"unmerge_events": N, "subjects": [...]}`            |
| No unmerge events but provenance-tracked merges | `pass`  | `{"reason": "Provenance-tracked merges enable..."}` |
| No unmerge events and no provenance             | `fail`  | `{"reason": "No unmerge events recorded..."}`         |

---

##### `_check_has_processing_records`

```python
def _check_has_processing_records(self) -> tuple
```

Check if data processing (merge) activities are recorded.

**Used by:** `GDPR_ART_30`

**Logic:**

| Condition                | Status  | Evidence                                    |
|--------------------------|---------|---------------------------------------------|
| Merge events exist       | `pass`  | `{"merge_events": N}`                       |
| No merge events          | `fail`  | `{"reason": "No data processing records found."}` |

---

##### `_check_has_consent_tracking`

```python
def _check_has_consent_tracking(self) -> tuple
```

Check for consent / lawful basis metadata. Looks for keys: `"consent"`,
`"lawful_basis"`, `"legal_basis"`, `"consent_id"`.

**Used by:** `GDPR_ART_7`

**Logic:**

| Condition                                       | Status            | Evidence                                    |
|-------------------------------------------------|-------------------|---------------------------------------------|
| At least one event has consent keys             | `pass`            | `{"events_with_consent": N}`                |
| No merge events recorded                        | `not_applicable`  | `{"reason": "No merge events to check."}`   |
| Events exist but no consent data                | `fail`            | `{"reason": "No consent or lawful basis recorded."}` |

---

##### `_check_has_data_protection_design`

```python
def _check_has_data_protection_design(self) -> tuple
```

Check for data protection by design evidence. Passes if access events exist,
or if any merge events have `operation` in `("encrypt", "decrypt")` or
`metadata.encrypted == True`.

**Used by:** `GDPR_ART_25`

**Logic:**

| Condition                                       | Status            | Evidence                                    |
|-------------------------------------------------|-------------------|---------------------------------------------|
| Access events exist                             | `pass`            | `{"access_controls_present": True}`         |
| Encryption events found                         | `pass`            | `{"encryption_events": N}`                  |
| No merge events recorded                        | `not_applicable`  | `{"reason": "No events to check."}`         |
| Events exist but no protection evidence         | `fail`            | `{"reason": "No data protection measures documented."}` |

---

##### `_check_has_access_controls`

```python
def _check_has_access_controls(self) -> tuple
```

Check if access control events have been recorded.

**Used by:** `HIPAA_ACCESS_CONTROL`, `SOX_ACCESS_CONTROL`

**Logic:**

| Condition                | Status  | Evidence                                                        |
|--------------------------|---------|-----------------------------------------------------------------|
| Access events exist      | `pass`  | `{"total_access_events": N, "granted": G, "denied": D}`        |
| No access events         | `fail`  | `{"reason": "No access control events recorded."}`              |

---

##### `_check_has_encryption`

```python
def _check_has_encryption(self) -> tuple
```

Check for encryption usage evidence. Looks for merge events with
`operation` in `("encrypt", "decrypt")` or `metadata.encrypted == True`.

**Used by:** `HIPAA_ENCRYPTION`

**Logic:**

| Condition                                       | Status            | Evidence                                   |
|-------------------------------------------------|-------------------|--------------------------------------------|
| Encryption events found                         | `pass`            | `{"encryption_events": N}`                 |
| No merge events recorded                        | `not_applicable`  | `{"reason": "No events to check."}`        |
| Events exist but no encryption evidence         | `fail`            | `{"reason": "No encryption usage evidence found."}` |

---

##### `_check_has_data_integrity`

```python
def _check_has_data_integrity(self) -> tuple
```

Check for cryptographic integrity verification. Passes if any merge event
has **both** `input_hash` and `output_hash` set.

**Used by:** `HIPAA_INTEGRITY`, `SOX_DATA_INTEGRITY`

**Logic:**

| Condition                                       | Status  | Evidence                                          |
|-------------------------------------------------|---------|---------------------------------------------------|
| Events with both hashes found                   | `pass`  | `{"events_with_integrity_hashes": N}`             |
| Events exist but lack hashes                    | `fail`  | `{"reason": "Merge events lack integrity hashes."}` |
| No merge events recorded                        | `fail`  | `{"reason": "No merge events recorded."}`         |

---

##### `_check_has_change_management`

```python
def _check_has_change_management(self) -> tuple
```

Check for change management audit trail — events with user/node attribution.
Passes if any event has `metadata.user_id`, `metadata.node_id`, or
`input_hash`.

**Used by:** `SOX_CHANGE_MGMT`

**Logic:**

| Condition                                       | Status  | Evidence                                            |
|-------------------------------------------------|---------|-----------------------------------------------------|
| No merge events recorded                        | `fail`  | `{"reason": "No change events recorded."}`          |
| Events with attribution found                   | `pass`  | `{"events_with_attribution": N, "total": M}`        |
| Events exist but lack attribution               | `fail`  | `{"reason": "Change events lack user/node attribution."}` |

---

##### `_check_has_retention_policy`

```python
def _check_has_retention_policy(self) -> tuple
```

Check for retention policy metadata. Looks for `"retention_days"` or
`"retention_policy"` keys in event metadata.

**Used by:** `SOX_RETENTION`

**Logic:**

| Condition                                       | Status            | Evidence                                    |
|-------------------------------------------------|-------------------|---------------------------------------------|
| Any event has retention metadata                | `pass`            | `{"retention_documented": True}`            |
| No merge events recorded                        | `not_applicable`  | `{"reason": "No events to check."}`         |
| Events exist but no retention policy            | `fail`            | `{"reason": "No retention policy documented."}` |

---

### `EUAIActReport`

```python
class EUAIActReport:
```

Specialised EU AI Act compliance report generator. Provides methods for
Art. 6 risk classification, Art. 13 transparency reporting, and Art. 10
data governance documentation.

#### Constructor

```python
def __init__(self, auditor: ComplianceAuditor) -> None
```

**Parameters:**

| Parameter | Type                | Description                                              |
|-----------|---------------------|----------------------------------------------------------|
| `auditor` | `ComplianceAuditor` | Any auditor instance — used for event data regardless of its configured framework |

**Instance attributes set:**

| Attribute  | Type                | Description           |
|------------|---------------------|-----------------------|
| `_auditor` | `ComplianceAuditor` | Reference to auditor  |

**Example:**

```python
from crdt_merge.compliance import ComplianceAuditor, EUAIActReport

auditor = ComplianceAuditor(framework="gdpr")  # framework does not matter
eu_report = EUAIActReport(auditor)
```

---

#### Methods

##### `risk_classification`

```python
def risk_classification(
    self,
    system_description: str = "",
    is_high_risk: bool = False,
) -> Dict[str, Any]
```

Classify the system per EU AI Act Art. 6 risk categories.

**Parameters:**

| Parameter             | Type   | Default | Description                                              |
|-----------------------|--------|---------|----------------------------------------------------------|
| `system_description`  | `str`  | `""`    | Free-text description of the AI system                   |
| `is_high_risk`        | `bool` | `False` | If `True`, force high-risk classification                |

**Returns:** `Dict[str, Any]` with keys:

| Key                     | Type         | Description                                     |
|-------------------------|--------------|-------------------------------------------------|
| `risk_level`            | `str`        | `"high"` \| `"limited"` \| `"minimal"` \| `"unclassified"` |
| `classification`        | `str`        | Human-readable classification label             |
| `system_description`    | `str`        | Echo of input parameter                         |
| `obligations`           | `List[str]`  | Applicable EU AI Act obligations                |
| `merge_events_analysed` | `int`        | Number of merge events used in analysis         |
| `timestamp`             | `float`      | Unix timestamp                                  |

**Classification heuristic** (when `is_high_risk=False`):

| Condition                                          | Risk Level     | Classification                                         |
|----------------------------------------------------|----------------|--------------------------------------------------------|
| `is_high_risk=True`                                | `"high"`       | Annex III high-risk AI system                          |
| `merge_count > 100` or `has_access_controls`       | `"limited"`    | Limited-risk AI system — transparency obligations apply|
| `merge_count > 0`                                  | `"minimal"`    | Minimal-risk AI system — voluntary codes of conduct    |
| `merge_count == 0`                                 | `"unclassified"` | Insufficient data to classify                        |

**Example:**

```python
from crdt_merge.compliance import ComplianceAuditor, EUAIActReport

auditor = ComplianceAuditor(framework="eu_ai_act")
for i in range(150):
    auditor.record_merge(operation="merge")

eu = EUAIActReport(auditor)

# Automatic classification — limited risk (>100 events)
risk = eu.risk_classification(system_description="Data merger v2")
print(risk["risk_level"])       # "limited"
print(risk["obligations"])      # ["Art. 13 — Transparency obligations", "Art. 52 — Disclosure requirements"]

# Force high-risk
risk_hr = eu.risk_classification(is_high_risk=True)
print(risk_hr["risk_level"])    # "high"
print(len(risk_hr["obligations"]))  # 7
```

---

##### `transparency_report`

```python
def transparency_report(self) -> Dict[str, Any]
```

Generate an Art. 13 transparency report. Documents what data was used, how
it was processed, and what metadata is available for interpretability.

**Returns:** `Dict[str, Any]` with keys:

| Key                          | Type             | Description                                    |
|------------------------------|------------------|------------------------------------------------|
| `article`                    | `str`            | Always `"Art. 13 — Transparency"`              |
| `total_operations`           | `int`            | Total merge events                             |
| `operations_with_metadata`   | `int`            | Events with non-empty metadata dicts           |
| `operations_with_hashes`     | `int`            | Events with `input_hash` or `output_hash`      |
| `operation_types`            | `Dict[str, int]` | Count of events by operation name              |
| `transparency_score`         | `float`          | `operations_with_metadata / total_operations` (0.0 if no events) |
| `timestamp`                  | `float`          | Unix timestamp                                 |

**Example:**

```python
from crdt_merge.compliance import ComplianceAuditor, EUAIActReport

auditor = ComplianceAuditor()
auditor.record_merge(operation="merge", input_hash="sha256:aaa", metadata={"desc": "test"})
auditor.record_merge(operation="merge", input_hash="sha256:bbb")
auditor.record_merge(operation="encrypt", metadata={"encrypted": True})

eu = EUAIActReport(auditor)
t = eu.transparency_report()

print(t["total_operations"])          # 3
print(t["operations_with_metadata"])  # 2
print(t["operations_with_hashes"])    # 2
print(t["operation_types"])           # {"merge": 2, "encrypt": 1}
print(t["transparency_score"])        # 0.6666666666666666
```

---

##### `data_governance`

```python
def data_governance(self) -> Dict[str, Any]
```

Generate Art. 10 data governance documentation. Documents data quality and
provenance tracking measures.

**Returns:** `Dict[str, Any]` with keys:

| Key                       | Type    | Description                                         |
|---------------------------|---------|-----------------------------------------------------|
| `article`                 | `str`   | Always `"Art. 10 — Data and data governance"`       |
| `total_merge_operations`  | `int`   | Total merge events                                  |
| `provenance_tracked`      | `int`   | Events with `metadata.has_provenance` or both hashes|
| `erasure_operations`      | `int`   | Total unmerge events                                |
| `data_quality_score`      | `float` | `provenance_tracked / total_merge_operations` (0.0 if no events) |
| `timestamp`               | `float` | Unix timestamp                                      |

**Example:**

```python
from crdt_merge.compliance import ComplianceAuditor, EUAIActReport

auditor = ComplianceAuditor()
auditor.record_merge(
    operation="merge",
    input_hash="sha256:aaa",
    output_hash="sha256:bbb",
    metadata={"has_provenance": True},
)
auditor.record_merge(operation="merge")
auditor.record_unmerge(subject_id="user-1")

eu = EUAIActReport(auditor)
dg = eu.data_governance()

print(dg["total_merge_operations"])  # 2
print(dg["provenance_tracked"])      # 1
print(dg["erasure_operations"])      # 1
print(dg["data_quality_score"])      # 0.5
```

---

##### `generate`

```python
def generate(self) -> ComplianceReport
```

Generate a full structured EU AI Act compliance report. Combines risk
classification, transparency, and data governance checks into a single
`ComplianceReport`.

**Behaviour:**

1. Creates a shallow copy of the auditor via `copy.copy()` (the original
   auditor is **never mutated**).
2. Sets the copy's framework to `"eu_ai_act"`.
3. Calls `validate()` on the copy to get the base report.
4. Enriches `report.metadata` with sub-reports:
   - `metadata["risk_classification"]` ← `self.risk_classification()`
   - `metadata["transparency"]` ← `self.transparency_report()`
   - `metadata["data_governance"]` ← `self.data_governance()`

> **Note:** The shallow copy shares the same event lists as the original
> auditor. Events added to the original after the copy is created will be
> visible to the copy (and vice versa), since the lists are shared references.

**Returns:** `ComplianceReport` — with `framework="eu_ai_act"` and enriched metadata.

**Example:**

```python
from crdt_merge.compliance import ComplianceAuditor, EUAIActReport

auditor = ComplianceAuditor(framework="gdpr", node_id="my-node")
auditor.record_merge(
    operation="merge",
    input_hash="sha256:abc",
    output_hash="sha256:def",
    metadata={"has_provenance": True, "reviewed": True, "risk_level": "minimal"},
)

eu = EUAIActReport(auditor)
report = eu.generate()

print(report.framework)                                # "eu_ai_act"
print(report.status)                                   # "compliant"
print(report.metadata["risk_classification"]["risk_level"])  # "minimal"
print(report.metadata["transparency"]["transparency_score"]) # 1.0
print(report.metadata["data_governance"]["data_quality_score"]) # 1.0

# Original auditor framework is never modified (copy.copy used internally)
print(auditor.framework)  # "gdpr"
```

---

## Compliance Rules Reference

All 17 compliance rules across 4 frameworks:

### EU AI Act (5 rules)

| # | Rule ID             | Severity   | Description                                              | Check Method                        |
|---|---------------------|------------|----------------------------------------------------------|-------------------------------------|
| 1 | `EU_AI_ACT_ART_10`  | `critical` | Data governance — provenance and quality documentation   | `_check_has_merge_provenance`       |
| 2 | `EU_AI_ACT_ART_12`  | `critical` | Record-keeping — automatic logging of system operations  | `_check_has_audit_trail`            |
| 3 | `EU_AI_ACT_ART_13`  | `warning`  | Transparency — outputs must be interpretable/documented  | `_check_has_transparency_metadata`  |
| 4 | `EU_AI_ACT_ART_14`  | `warning`  | Human oversight — documented human review processes      | `_check_has_human_oversight`        |
| 5 | `EU_AI_ACT_ART_9`   | `info`     | Risk management — system risk classification             | `_check_has_risk_classification`    |

### GDPR (4 rules)

| # | Rule ID          | Severity   | Description                                              | Check Method                          |
|---|------------------|------------|----------------------------------------------------------|---------------------------------------|
| 1 | `GDPR_ART_17`    | `critical` | Right to erasure — remove personal data on request       | `_check_has_unmerge_capability`       |
| 2 | `GDPR_ART_30`    | `critical` | Records of processing activities                         | `_check_has_processing_records`       |
| 3 | `GDPR_ART_7`     | `warning`  | Consent tracking — evidence of lawful basis              | `_check_has_consent_tracking`         |
| 4 | `GDPR_ART_25`    | `info`     | Data protection by design — privacy safeguards           | `_check_has_data_protection_design`   |

### HIPAA (4 rules)

| # | Rule ID                | Severity   | Description                                              | Check Method                    |
|---|------------------------|------------|----------------------------------------------------------|---------------------------------|
| 1 | `HIPAA_ACCESS_CONTROL` | `critical` | Role-based access to protected health information        | `_check_has_access_controls`    |
| 2 | `HIPAA_AUDIT_TRAIL`    | `critical` | Immutable log of all access and modifications            | `_check_has_audit_trail`        |
| 3 | `HIPAA_ENCRYPTION`     | `critical` | Data at rest and in transit must be encrypted            | `_check_has_encryption`         |
| 4 | `HIPAA_INTEGRITY`      | `warning`  | Mechanisms to ensure data not improperly altered         | `_check_has_data_integrity`     |

### SOX (4 rules)

| # | Rule ID              | Severity   | Description                                              | Check Method                    |
|---|----------------------|------------|----------------------------------------------------------|---------------------------------|
| 1 | `SOX_DATA_INTEGRITY` | `critical` | Cryptographic proof of data consistency                  | `_check_has_data_integrity`     |
| 2 | `SOX_CHANGE_MGMT`    | `critical` | All changes logged with attribution                      | `_check_has_change_management`  |
| 3 | `SOX_ACCESS_CONTROL`  | `critical` | Segregation of duties and role-based access              | `_check_has_access_controls`    |
| 4 | `SOX_RETENTION`       | `warning`  | Audit logs retained for required period                  | `_check_has_retention_policy`   |

### Shared Check Methods

Several check methods are reused across frameworks:

| Check Method                   | Frameworks                          |
|--------------------------------|-------------------------------------|
| `_check_has_audit_trail`       | EU AI Act (ART_12), HIPAA (AUDIT_TRAIL) |
| `_check_has_access_controls`   | HIPAA (ACCESS_CONTROL), SOX (ACCESS_CONTROL) |
| `_check_has_data_integrity`    | HIPAA (INTEGRITY), SOX (DATA_INTEGRITY) |

---

## Integration Patterns

### With `crdt_merge.audit`

```python
from crdt_merge.audit import AuditLog
from crdt_merge.compliance import ComplianceAuditor

# Build auditor from an existing AuditLog
audit_log = AuditLog(node_id="node-1")
# ... populate audit_log with entries ...

auditor = ComplianceAuditor.from_audit_log(audit_log, framework="sox")
report = auditor.validate()
```

The `from_audit_log` class method reads `audit_log.entries` (or iterates the
object) and extracts `operation`, `input_hash`, `output_hash`, `metadata`
from each entry via `getattr`.

### With `crdt_merge.provenance`

```python
from crdt_merge.provenance import ProvenanceLog
from crdt_merge.compliance import ComplianceAuditor

# Build auditor from a ProvenanceLog
prov_log = ProvenanceLog()
# ... populate prov_log with records ...

auditor = ComplianceAuditor.from_provenance_log(prov_log, framework="eu_ai_act")
report = auditor.validate()
```

The `from_provenance_log` class method reads `provenance_log.records` (or
iterates the object) and extracts `key`, `origin`, `conflict_count` from each
record. All events get `metadata.has_provenance = True`.

### With `crdt_merge.unmerge`

Unmerge operations should be recorded via `record_unmerge()` after using the
`UnmergeEngine` or `GDPRForget` classes:

```python
from crdt_merge.compliance import ComplianceAuditor

auditor = ComplianceAuditor(framework="gdpr")

# After performing an unmerge operation:
auditor.record_unmerge(
    subject_id="user-42",
    fields_removed=["email", "phone"],
    metadata={"engine": "GDPRForget", "ticket": "GDPR-2026-001"},
)
```

### With `crdt_merge.rbac`

Access control decisions from `RBACController` should be recorded via
`record_access()`:

```python
from crdt_merge.compliance import ComplianceAuditor

auditor = ComplianceAuditor(framework="hipaa")

# After each RBAC decision:
auditor.record_access(
    user_id="nurse-1",
    operation="read",
    resource="patient-42",
    granted=True,
    metadata={"role": "nurse", "permission": "read_patient_data"},
)
```

### Full Pipeline Example

```python
from crdt_merge.compliance import ComplianceAuditor, EUAIActReport

# Create auditor
auditor = ComplianceAuditor(framework="eu_ai_act", node_id="pipeline-v2")

# Record merge with full metadata
auditor.record_merge(
    operation="merge",
    input_hash="sha256:abc123",
    output_hash="sha256:def456",
    metadata={
        "has_provenance": True,
        "reviewed": True,
        "risk_level": "limited",
        "consent": True,
        "retention_days": 365,
        "user_id": "data-eng-1",
    },
)

# Record access
auditor.record_access(
    user_id="data-eng-1", operation="write", resource="dataset-v3", granted=True
)

# Record unmerge
auditor.record_unmerge(subject_id="user-99", fields_removed=["pii_field"])

# Standard validation
report = auditor.validate()
print(report.to_text())

# EU AI Act specialised report
eu_report = EUAIActReport(auditor)
full_report = eu_report.generate()
print(full_report.metadata["risk_classification"]["risk_level"])
```

---

## Known Issues

### 1. Thread-Safety

All event lists (`_merge_events`, `_unmerge_events`, `_access_events`) are
plain Python `list` objects with **no locking**. Concurrent writes from
multiple threads may cause:

- Lost events (race conditions on `list.append`)
- Inconsistent counts during `validate()` if events are added mid-validation

> **Note:** `EUAIActReport.generate()` now uses `copy.copy()` instead of
> mutating the auditor's framework, so the earlier framework-corruption
> issue has been resolved.

**Mitigation:** Use a dedicated auditor per thread, or synchronise externally
with `threading.Lock`.

### 2. ~~Bare `tuple` Return Types~~ (Resolved)

All `_check_*` methods now return `CheckResult` — a `NamedTuple` with typed
fields `passed`, `message`, and `details`. This replaces the earlier bare
`tuple` returns and provides full IDE / type-checker support.

```python
# Current
def _check_has_merge_provenance(self) -> CheckResult:
    ...
    return CheckResult(passed="pass", message="Check passed", details={...})
```

### 3. `getattr` Fallback in Dynamic Dispatch

The `validate()` method uses `getattr(self, f"_check_{check_name}", None)` to
resolve check methods. If a rule's `check` field has a typo, the finding
silently defaults to `"not_applicable"` instead of raising an error. This
could mask configuration bugs.

### 4. `from_provenance_log` Ignores `node_id`

Unlike `from_audit_log` which reads `node_id` from the audit log,
`from_provenance_log` always sets `node_id="default"`, even if the provenance
log has a `node_id` attribute.

### 5. ~~`EUAIActReport.generate()` Temporary Framework Swap~~ (Resolved)

The `generate()` method now uses `copy.copy()` to create a temporary auditor
with `framework="eu_ai_act"`, leaving the original auditor untouched. The
earlier mutation-based approach and its exception-safety issue have been fixed.

### 6. Broad `except Exception` on Imports

The optional import blocks (lines 38–62) catch `Exception` rather than
`ImportError`, which could silently swallow unexpected errors during module
loading.


