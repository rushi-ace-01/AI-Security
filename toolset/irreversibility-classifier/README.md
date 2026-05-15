# Irreversibility Classifier

Scores AI agent actions on **how reversible they are — before the action runs.**

This is the foundation tool of `agent-guardrails`. The Blast Radius Scorer and
Infrastructure Protection tools build on the scores it produces.

## The problem it addresses

AI agents do not distinguish between an action that can be undone and one that
cannot. `GET` and `DELETE` look the same to an agent mid-task. In the PocketOS
incident, a coding agent treated "delete the storage volume" as just another
step toward fixing a credential bug. It was not — it was permanent.

The classifier makes that distinction explicit and machine-readable.

## How it works

It is **pattern-based, not an ML model.** Every score traces back to a rule in
a JSON file under `patterns/`. This is deliberate:

- **Auditable** — you can see exactly why an action got its score.
- **Predictable** — the same action always scores the same.
- **Contributable** — adding coverage means editing JSON, not retraining anything.

## Scoring scale

| Score | Risk level | Meaning |
|-------|-----------|---------|
| 0–2   | SAFE      | Read-only or trivially reversible |
| 3–5   | LOW       | Reversible, but with side effects or lost prior state |
| 6–7   | MEDIUM    | Hard to reverse; needs care |
| 8–9   | HIGH      | Effectively irreversible without a backup |
| 10    | CRITICAL  | Permanent and irreversible |

## Usage

```python
from classifier import IrreversibilityClassifier

clf = IrreversibilityClassifier()

# Explicit kind
clf.classify("DELETE", kind="http_method")
clf.classify("DROP TABLE users", kind="sql_operation")
clf.classify("rm -rf /var/data", kind="shell_command")
clf.classify("volume.delete", kind="cloud_api", provider="railway")

# Or let it guess the kind
result = clf.classify("DROP TABLE users")

print(result.score)            # 10
print(result.risk_level)       # "CRITICAL"
print(result.reversible)       # False
print(result.should_block())   # True
print(result)                  # full human-readable summary
```

### What you get back

A `ClassificationResult` with:

- `score` — 0 to 10
- `risk_level` — SAFE / LOW / MEDIUM / HIGH / CRITICAL
- `reversible` — boolean
- `explanation` — why it scored that way
- `safer_alternative` — a suggested safer path, when one applies
- `modifiers_applied` — context bumps, e.g. an `UPDATE` with no `WHERE` clause
- `should_block(threshold=7)` — whether to hold the action for human confirmation
- `to_dict()` — JSON-friendly output

## Supported action kinds

| Kind            | Coverage |
|-----------------|----------|
| `http_method`   | GET, HEAD, OPTIONS, POST, PUT, PATCH, DELETE |
| `sql_operation` | SELECT, INSERT, UPDATE, DELETE, TRUNCATE, DROP, ALTER, GRANT, REVOKE |
| `shell_command` | ls, cat, cp, mv, rm, shred, dd, mkfs, chmod, chown, kill, git |
| `cloud_api`     | Railway, AWS, Supabase |

## Context modifiers

Some actions are scored higher based on context, not just the verb:

- `UPDATE` / `DELETE` SQL **without a `WHERE` clause** → bumped to 9 (affects the whole table)
- `rm` **with `-rf` or `-r`** → bumped to 10
- `git` **with `push --force`, `reset --hard`, or `clean -fd`** → bumped to 7–8

## Unknown actions

If an action matches no pattern, it returns a **conservative default score of 6**
and `recognized = False`. The philosophy: an unrecognized action is treated as
potentially risky until someone adds a pattern for it. It is never silently
treated as safe.

## Extending coverage

To add a new action, edit the relevant file in `patterns/`. No code changes
needed. To add a new cloud provider, drop a new JSON file in
`patterns/cloud_apis/` following the existing structure. See
[CONTRIBUTING.md](../../CONTRIBUTING.md).

## Running the tests

```bash
python tests/test_classifier.py
# or, with pytest:
python -m pytest tests/ -v
```

## Demo

```bash
python classifier.py
```

Runs a short self-demo across all four action kinds.

## Limitations

- It scores the **action**, not the **target**. `DELETE` on a test record and
  `DELETE` on production both score the same here. Distinguishing the target is
  the job of the Blast Radius Scorer and Infrastructure Protection tools.
- Pattern coverage is a starting set, not exhaustive. Contributions welcome.
- It does not execute or intercept anything. It classifies. Wiring it into an
  agent's execution path is left to the integrator (and to phase 2 of this repo).
