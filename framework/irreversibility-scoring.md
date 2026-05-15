# Irreversibility Scoring

How to classify actions by whether they can be undone, and how to use that classification to gate the dangerous ones. This addresses [irreversibility blindness](../taxonomy/irreversibility-blindness.md) — the agent's inability to tell a permanent action from a recoverable one.

## The principle

**Before an agent takes an action, the action's reversibility should be known, and irreversible actions should not execute autonomously.**

A human operator carries an instinct for this. They slow down before `DROP TABLE`. They double-check before emptying a bucket. The agent has no such instinct — to its planner, every action is just a step. So the instinct has to be supplied from outside: every action gets a reversibility score before it runs, and that score determines whether the agent may proceed alone.

## A reversibility scale

The [Irreversibility Classifier](../toolset/irreversibility-classifier/) uses a 0–10 scale. The bands matter more than the exact numbers:

| Score | Band | Meaning | Example |
|-------|------|---------|---------|
| 0–2 | Safe | Read-only or trivially undone | `GET`, `SELECT`, list operations |
| 3–5 | Reversible | Undoable, possibly with effort or side effects | `RENAME`, create operations, config changes |
| 6–7 | Hard to reverse | Recoverable only from a backup, or with significant effort | `UPDATE` without a captured prior state, removing a deployment |
| 8–10 | Irreversible | Permanent. Recoverable only from a separate backup, or not at all | `DELETE`, `DROP`, `TRUNCATE`, volume deletion, instance termination |

The scores come from pattern files — explicit, auditable rules — not from a model's judgement in the moment. This matters: the classification has to be deterministic and inspectable, because it is a safety boundary.

## How to use the score

The score is not just information. It drives a decision:

- **0–5: proceed.** The agent may take these actions autonomously. They are read-only or comfortably recoverable.
- **6–7: proceed with logging and, ideally, a captured prior state.** Before a hard-to-reverse action, capture what is being changed so it *can* be reversed. Then proceed.
- **8–10: do not proceed autonomously.** Irreversible actions pause for human confirmation, every time. No exceptions based on the agent's confidence — the PocketOS agent was confident.

The threshold is a policy choice, but the principle is not: there is some score above which the agent stops and asks. Pick it, and enforce it outside the agent's reasoning loop.

## Where the gate must live

This is the part that the PocketOS incident makes unmissable. The gate cannot be an instruction in the agent's prompt. The PocketOS agent had instructions not to run destructive actions unasked, and it ran one anyway, then listed the instruction it had violated.

The gate has to be **structural** — a checkpoint in the execution path that the agent calls through, that holds the irreversible action and does not release it without an external confirmation. The agent cannot reason its way past a gate it does not control. That is the whole point.

## Prefer the reversible path by design

Beyond gating, design tasks so the agent's default route is the recoverable one:

- Where the platform offers soft-delete or a trash window, use it — and prefer it over hard delete in the agent's available tools.
- Snapshot before overwrite. If an action will replace state, capture the prior state first as a matter of course.
- Give the agent reversible tools where reversible tools exist. If the agent's toolkit only contains the hard-delete operation, it will use the hard-delete operation.

The classifier surfaces a `safer_alternative` for many actions precisely so this is easy to do.

## How to verify it

- The **Irreversibility Classifier** scores any action and provides a `should_block()` signal for actions above the threshold. Put it in the agent's path so the score is computed before execution, not after.

## The test to apply

For every action an agent can take, ask: **"If the agent does this and it was the wrong call, can we undo it — and how?"**

If the answer is "no" or "only from a backup," that action is in the gated band. It does not run without a human.

## Related framework documents

- [Permission scoping](permission-scoping.md) — the cleanest way to handle an irreversible action is to make sure the agent's credential cannot perform it at all.
- [Human-in-the-loop](human-in-the-loop.md) — how to build the confirmation gate so it actually works.
- [Pre-execution checks](pre-execution-checks.md) — irreversibility gating is checklist item 2.
