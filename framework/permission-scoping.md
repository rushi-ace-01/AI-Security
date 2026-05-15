# Permission Scoping

How to scope credentials so an agent's access matches its task. This is the direct antidote to [over-permissioning](../taxonomy/over-permissioning.md), and it is the single highest-leverage thing you can do — because a correctly scoped credential makes most other failure modes survivable.

## The principle

**An agent should hold the minimum access its current task requires, and nothing more.**

This is least privilege, which is not a new idea. What is new is the cost of getting it wrong. A human with an over-broad credential is moderated by human judgement — the pause before a dangerous command, the instinct that something is off. An agent has no such pause. With an agent, the credential's scope *is* the safety boundary. Whatever the token can do, the agent can do.

## What good scoping looks like

### Scope to the task, not the project, not the account

The unit of scoping is the task. "This agent run needs to read the service config and restart one service" defines a credential: read on that config, restart on that service, nothing else. Not "access to the project." Not "an account token." The narrower the better, every time.

### Separate destructive capability completely

The credential an agent uses for routine work should not be able to cause irreversible loss — at all. Delete, drop, terminate, truncate: these do not belong in the agent's default credential.

If a task genuinely requires a destructive action, that is a separate credential: single-purpose, narrowly scoped to the one resource, loaded only for the one step that needs it, and ideally requiring a human-in-the-loop confirmation to use. The default state of the agent is "cannot destroy anything."

### Prefer short-lived credentials

A credential that expires in an hour is a smaller liability than one that lives forever. Where the platform supports it, prefer just-in-time, short-lived, automatically-revoked credentials over standing tokens. A standing token sitting in a file is exactly what the PocketOS agent found and used.

### Pin the environment

If the agent's work is on staging, its credential reaches staging and *only* staging. An agent must not be able to reach production with a credential provisioned for a non-production task. Environment is part of scope.

### Never reuse human or CI credentials

A human's credentials are scoped for the broad range of things a human does. A CI system's credentials are scoped for the broad range of things CI does. Handing either to an agent inherits all of that breadth for a task that needs almost none of it. Agents get their own credentials, scoped to their own tasks.

## What bad scoping looks like

These are the patterns to hunt for and eliminate:

- A single token that works for everything, reused across tasks because it is convenient.
- A credential created for one narrow purpose (e.g. domain management) that was actually granted account-wide authority — the PocketOS token exactly.
- "All" / wildcard scope on anything destructive.
- One credential that spans production and staging.
- Standing, long-lived tokens stored in files in the codebase.
- Destructive capability bundled into the same credential used for routine reads.

## How to verify it

- The **Credential Scope Auditor** takes a credential's stated purpose and granted capabilities and reports every capability that exceeds the purpose — flagging destructive excess as a failure.
- The **Blast Radius Scorer** takes a credential's scope and produces a 0–100 score for how much damage an agent holding it could do. Use it to compare credentials and to set a maximum acceptable score for autonomous use.

Run both before an agent is deployed. Treat a failing audit or a critical blast radius score as a blocker, not a warning.

## The test to apply

For any credential you are about to give an agent, ask: **"If this agent's reasoning goes completely wrong, what is the worst it can do with this credential?"**

If the answer is worse than the task could possibly justify, the credential is over-scoped. Narrow it until the worst case matches the task.

## Related framework documents

- [Separation of concerns](separation-of-concerns.md) — scoping is about what one credential can reach; separation is about making sure no credential can reach two things that should be isolated.
- [Human-in-the-loop](human-in-the-loop.md) — the destructive actions you cannot scope away should be gated behind confirmation.
- [Pre-execution checks](pre-execution-checks.md) — permission scoping is checklist item 1.
