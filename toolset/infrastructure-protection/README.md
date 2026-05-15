# Infrastructure Protection

Three static-analysis tools that target the *infrastructure* side of AI agent safety — the conditions that turn a single agent mistake into a catastrophe.

This is the layer the PocketOS incident exposed. The agent's mistake was bad, but what made it *catastrophic* was the infrastructure around it: backups on the same volume as production, one token that could reach everything, no separation between what could read and what could destroy. These three tools find exactly those conditions, before an agent is ever deployed.

All three are static. They analyse a description of your infrastructure. Nothing is executed, no live credentials are needed.

## The three tools

### 1. Colocated Risk Scanner (`colocated-risk-scanner/`)

Finds where things that should be isolated are sharing a boundary — the same volume, account, token, project, or region.

It *describes* the problem. It answers "what is dangerously colocated here?" and explains why each arrangement is risky and how to fix it. Run it to understand your exposure.

```python
from scanner import ColocatedRiskScanner
report = ColocatedRiskScanner().scan(infrastructure)
print(report.passed)          # False if anything medium+ was found
```

The PocketOS arrangement (production + backups on one volume) fires `COLO-001`, the critical rule.

### 2. Credential Scope Auditor (`credential-scope-auditor/`)

Takes **one credential** and measures the gap between what it *can* do and what its stated job *requires*.

That gap is over-permissioning, and over-permissioning is what bites you. The PocketOS token could delete volumes; its job was fixing a credential mismatch. Run it on every credential an agent will hold.

```python
from auditor import CredentialScopeAuditor
report = CredentialScopeAuditor().audit(credential)
print(report.verdict)         # PASS / WARN / FAIL
```

A `read_only` credential that has been granted `delete` returns `FAIL`.

### 3. Separation Enforcer (`separation-enforcer/`)

The enforcement counterpart to the scanner. Takes a machine-readable separation **policy** and turns it into a **pass/fail gate** with real exit codes. Drop it in CI; a dangerous arrangement stops the pipeline.

Where the scanner describes, the enforcer *blocks*.

```bash
python enforcer.py infra.json
echo $?        # 0 = passed, 1 = blocking violation, 2 = bad input
```

Rules carry an `enforce` level: `block` fails the check, `warn` reports but passes. Copy `rulesets/default_rules.json`, tune it, and version it with your infrastructure.

## How they fit together

| Tool | Question it answers | When you run it |
|------|---------------------|-----------------|
| Colocated Risk Scanner | "What is dangerously colocated?" | While reviewing / understanding your setup |
| Credential Scope Auditor | "Is this one credential more powerful than its job?" | On every credential, before handing it to an agent |
| Separation Enforcer | "Does this setup pass our policy — yes or no?" | In CI, on every change, as a hard gate |

Scanner and Auditor are for **humans investigating**. The Enforcer is for **automation blocking**. Most teams will use the scanner and auditor to understand their exposure, then encode the conclusions into an enforcer ruleset so regressions can't slip back in.

## Shared input format

The Colocated Risk Scanner and Separation Enforcer share one infrastructure-description format:

```json
{
  "resources": [
    {"id": "pg-main", "roles": ["production_data"],
     "volume": "vol-01", "account": "acct-prod",
     "project": "app", "region": "us-east-1"}
  ],
  "credentials": [
    {"id": "agent-token", "roles": ["agent_default", "read_access"],
     "capabilities": ["read", "deploy"], "scope": "single-project"}
  ]
}
```

The Credential Scope Auditor takes a single credential with a slightly richer shape (`stated_purpose`, `granted_capabilities`). See `credential-scope-auditor/auditor.py` for the exact fields.

**Recognised roles** — resources: `production_data`, `backup`, `snapshot`. Credentials: `production_access`, `staging_access`, `read_access`, `destructive_access`, `agent_default`.

## Connection to the rest of the toolset

These tools sit downstream of the **Blast Radius Scorer**. A high blast radius score tells you a credential is dangerous; the Credential Scope Auditor tells you *whether that danger is justified by the job*, and the Colocated Risk Scanner and Separation Enforcer tell you *whether the infrastructure around it will contain a mistake or amplify it*.

## Running the tests

```bash
python colocated-risk-scanner/tests/test_scanner.py
python credential-scope-auditor/tests/test_auditor.py
python separation-enforcer/tests/test_enforcer.py
```

## Limitations

- Static analysis only. These tools reason about a *description* of infrastructure. They cannot see a resource or credential you did not describe. Generating that description accurately from your real cloud config / IaC is a separate problem and a good contribution area.
- The rulesets are starting points, deliberately opinionated but not exhaustive. They are JSON; extend them.
- The `role` vocabulary is small on purpose. It is enough to catch the common catastrophic patterns. Richer modelling can come later without breaking the format.
- None of these intercept a running agent. Runtime interception is a separate, later phase of this repo.
