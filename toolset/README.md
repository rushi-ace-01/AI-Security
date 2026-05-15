# agent-guardrails / toolset

Working, tested tools for catching AI agent alignment failures **before** they cause damage.

Every tool here is static analysis: it reasons about a *description* of an action, a credential, or an infrastructure setup. Nothing executes anything. No live credentials are needed. The point is to run these *before* an agent is deployed — the checks PocketOS did not have.

## What's here

### 1. Irreversibility Classifier — `irreversibility-classifier/`

Scores a single agent action on how reversible it is, 0 (read-only) to 10 (permanent). Pattern-based and fully auditable — every score traces to a rule in a JSON file. Covers HTTP methods, SQL, shell commands, and cloud APIs (Railway, AWS, Supabase).

This is the **foundation**. The other tools build on its irreversibility scale.

### 2. Blast Radius Scorer — `blast-radius-scorer/`

Takes a credential's *scope description* and answers: if an agent holds this and goes wrong, how much damage can it do? Expands the scope into concrete destructive capabilities and aggregates them into a single 0–100 score. A PocketOS-shaped Railway token scores 100/100 CRITICAL.

### 3. Infrastructure Protection — `infrastructure-protection/`

Three tools for the infrastructure conditions that turn one mistake into a catastrophe:

- **Colocated Risk Scanner** — finds production data and backups sharing a volume/account/region (the PocketOS failure).
- **Credential Scope Auditor** — measures the gap between what one credential *can* do and what its job *needs*.
- **Separation Enforcer** — a machine-readable policy turned into a CI pass/fail gate with real exit codes.

## How they connect

```
  Irreversibility Classifier
        (scores one action: 0-10)
                 |
                 v
  Blast Radius Scorer
        (uses that scale to score a whole credential: 0-100)
                 |
                 v
  Infrastructure Protection
        (is the danger justified? will the setup contain a mistake?)
```

The classifier defines the scale. The scorer applies it to a credential. The infrastructure tools ask whether the surrounding setup amplifies or contains a failure.

## Quick start

Each tool runs standalone with no dependencies beyond the Python standard library (Python 3.8+).

```bash
# See each tool's self-demo:
python irreversibility-classifier/classifier.py
python blast-radius-scorer/scorer.py
python infrastructure-protection/colocated-risk-scanner/scanner.py
python infrastructure-protection/credential-scope-auditor/auditor.py
python infrastructure-protection/separation-enforcer/enforcer.py

# Run a tool's tests:
python irreversibility-classifier/tests/test_classifier.py
```

See `examples/` for short copy-paste scripts that show each tool used end to end, including a full pass over a reconstruction of the PocketOS setup.

## Design principles

These hold across every tool and are what contributions are checked against:

1. **Static and offline.** No tool executes actions or transmits a real credential. A safety tool must not itself be a liability.
2. **Auditable, not magic.** Scores come from rules in JSON files, not opaque models. You can always see *why* something scored the way it did.
3. **Pessimistic defaults.** An unrecognised action, scope, or capability is treated as risky until a human or a pattern says otherwise. Never fail open.
4. **Plain standard library.** Zero install friction. Easy to read, easy to contribute to.
5. **Every tool ships with tests and a self-demo.** An empty test folder is not a contribution.

## Status

Phase 1 — static analysis tools. All three tool areas are implemented and tested.

Later phases (runtime interception, an aggregating CLI, a PyPI package) are noted in the top-level repo README and are open for contribution.
