# Blast Radius Scorer

Answers one question: **if this credential is handed to an AI agent and the agent goes wrong, how much damage can it do?**

You give it a permission/scope *description* for a credential. It expands that into the concrete set of destructive actions the credential unlocks, then aggregates them into a single **0–100 blast radius score** with a full breakdown.

This is **static, pre-deployment analysis** — the check you run *before* you let an agent near your infrastructure. It is the check PocketOS did not have.

## Why this matters

In the PocketOS incident, the agent found a Railway API token with full scope. Nobody had ever asked: *what is the worst this token could do?* If they had, the answer — "delete every volume, database, and project in the account" — would have been the obvious signal to scope it down first.

The Blast Radius Scorer makes that question routine and answerable in seconds.

## A deliberate safety choice: no live tokens

This tool analyses a **scope description**, never your real credential. It does not call cloud APIs with your live token. A security tool should not itself ship a secret to a third party. The providers include a guard that detects when a real token has been pasted into a description field by mistake and refuses to store it.

## Usage

```python
from scorer import BlastRadiusScorer

scorer = BlastRadiusScorer()

report = scorer.score("railway", {
    "label": "agent-token",          # a non-sensitive label, never the token
    "scope": "full",                 # "full" | "read_only" | "custom"
    "environment": "production",
    "projects": ["*"],               # ["*"] = all projects
})

print(report)                        # full human-readable report
print(report.score)                  # 0-100
print(report.risk_level)             # CRITICAL / HIGH / MEDIUM / LOW / MINIMAL
print(report.safe_to_automate())     # bool
print(report.to_dict())              # JSON-friendly dict
```

## Supported providers

| Provider   | Config shape | See |
|------------|--------------|-----|
| `railway`  | `scope`, `environment`, `projects`, `custom_permissions` | `providers/railway.py` |
| `aws`      | `actions` (IAM-style, wildcards expanded), `resources`, `environment` | `providers/aws.py` |
| `supabase` | `key_type` (`anon` / `service_role` / `management` / `db_connection`), `environment` | `providers/supabase.py` |

Each provider's docstring documents its exact expected config shape.

## The score model

Each capability the credential unlocks contributes points based on its irreversibility (the 0–10 scale from the Irreversibility Classifier):

| Irreversibility | Base points | Meaning |
|-----------------|-------------|---------|
| 10              | 25          | Permanent, unrecoverable |
| 8–9             | 15          | Effectively irreversible |
| 6–7             | 7           | Hard to reverse |
| 3–5             | 2           | Reversible, with side effects |
| 0–2             | 0           | Safe / read-only |

Context multipliers are then applied:

- targets **production** → ×1.5
- targets a **backup or snapshot** → ×1.5 (destroying recovery paths is the worst case)
- scoped to **all resources** → ×1.2

The raw total is normalised to 0–100 and bucketed:

| Score   | Risk level |
|---------|-----------|
| 70–100  | CRITICAL  |
| 45–69   | HIGH      |
| 20–44   | MEDIUM    |
| 5–19    | LOW       |
| 0–4     | MINIMAL   |

The goal is not false precision. It is a **consistent, explainable ranking** so you can compare two credentials and tell which one is the bigger liability — and so the same credential always scores the same.

## What you get back

A `BlastRadiusReport` with:

- `score` — 0 to 100
- `risk_level` — CRITICAL / HIGH / MEDIUM / LOW / MINIMAL
- `scored_capabilities` — every unlocked capability, its points, and which multipliers applied
- `destructive_count` / `irreversible_count` — quick counts
- `warnings` — provider-specific red flags (e.g. the PocketOS volume-deletion warning)
- `recommendations` — concrete steps to bring the score down
- `safe_to_automate(threshold=45)` — whether the credential is below the bar for hands-off agent use
- `to_dict()` — JSON-friendly output

## How it connects to the rest of the toolset

- It **consumes** the irreversibility scale defined by the **Irreversibility Classifier**. The per-action scores in each provider are kept in sync with that tool's pattern files.
- It **feeds** the **Infrastructure Protection** tools: a high blast radius score is the trigger to go look at *why* — colocated backups, over-broad tokens, missing environment separation.

## Running the tests

```bash
python tests/test_scorer.py
# or:
python -m pytest tests/ -v
```

## Demo

```bash
python scorer.py
```

Scores four example credentials, including a reconstruction of the PocketOS-shaped token (it scores 100/100 CRITICAL).

## Limitations

- It scores **what a credential can do**, from a description you provide. It cannot detect a credential you forgot to tell it about. Inventory is a separate problem.
- Provider coverage is Railway, AWS, and Supabase to start. Other providers are good first contributions — the `Provider` base class is small and documented.
- The point weights and multipliers are deliberate but not sacred. They are tuned to rank credentials sensibly, not to be an actuarial model. If you adjust them, adjust the tests too.
- Static analysis only. It does not watch a running agent. Runtime interception is a separate, later phase of this repo.
