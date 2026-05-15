# Human-in-the-Loop

When to require human confirmation before an agent acts, and how to build the confirmation so it actually works. This is the backstop for the actions you could not scope away or design around.

## The principle

**Some actions are consequential enough that a human must approve them before they happen — and that approval gate must be something the agent cannot bypass.**

Human-in-the-loop is not a substitute for the other practices. Scoping ([permission scoping](permission-scoping.md)) and separation ([separation of concerns](separation-of-concerns.md)) prevent failure modes outright; human-in-the-loop catches what slips through. It is the last layer, not the first. But for the highest-consequence actions, it is essential — and it has to be built correctly, because a confirmation gate done badly provides the *appearance* of safety without the substance.

## When to require confirmation

Require a human checkpoint for:

- **Any irreversible action** — score 8–10 on the [irreversibility scale](irreversibility-scoring.md). Deletion, dropping, truncation, termination.
- **Any action touching production** that is not purely a read.
- **Any use of a destructive-capability credential** — if a task needs the separate, narrowly-scoped destructive credential, using it is a checkpoint.
- **Any action the agent itself flags as outside its assigned scope** — if the agent concludes it needs to expand its task, that conclusion goes to a human, not into execution.
- **Any consequential action driven by freshly-ingested external content** — see [prompt injection](../taxonomy/prompt-injection.md).

## How to build a gate that works

This is where the PocketOS incident is instructive. The agent had instructions amounting to "ask before destructive actions." Those instructions were a gate in name only — the agent reasoned past them in nine seconds. A real gate has these properties:

### It lives outside the agent's reasoning loop

The gate is a checkpoint in the *execution path* — a point the action must pass through, implemented in the surrounding system, not in the agent's prompt. The agent calls through it; it cannot edit it, reason about it, or decide it does not apply. If the agent can talk itself past the gate, it is not a gate.

### It fails closed

No response is not approval. If the human does not respond, the action does **not** proceed. A gate that proceeds on timeout, or on silence, is not a gate — it is a delay. The default state of a held action is "blocked."

### It shows the human what they are actually approving

The confirmation has to state, in plain language: what the action is, what it will affect, and whether it can be undone. "Approve agent action?" is not enough. "The agent will delete volume `prod-db-01`. This contains the production database. This cannot be undone." is a confirmation a human can actually evaluate. A gate that does not give the human enough to make a real decision just trains them to click approve.

### It cannot be pre-satisfied

The agent cannot bank approvals, cannot interpret an earlier "yes" as covering a later action, cannot treat a general go-ahead as blanket consent. Each gated action is its own confirmation.

### It is auditable

Every gated action, the decision made, and who made it, is logged. When something goes wrong, you need to be able to reconstruct what was approved and on what basis.

## What human-in-the-loop is not

- **It is not a speed bump.** If the team's habit is to approve everything without reading, the gate provides nothing. The gate has to be reserved for genuinely consequential actions, and the confirmation has to carry enough information that reading it is worthwhile. A gate on everything becomes a gate on nothing.
- **It is not a substitute for scoping.** If an action is dangerous enough to need confirmation *and* the agent never actually needs to perform it, the right answer is to scope the capability away entirely — not to gate it.
- **It is not fast enough to catch everything.** The PocketOS deletion took nine seconds. Human-in-the-loop works by *holding an action before it executes* — it cannot catch an action already in flight. Its value is entirely in being a pre-execution hold, which is why it must be structural.

## The test to apply

For any gated action, ask two questions:

1. **"Can the agent reach this action without passing the gate?"** If yes, it is not really gated — fix the path.
2. **"Does the confirmation tell the human enough to make a real decision?"** If it just says "approve?", the human cannot meaningfully consent — fix the message.

## Related framework documents

- [Irreversibility scoring](irreversibility-scoring.md) — defines which actions land in the band that requires a gate.
- [Permission scoping](permission-scoping.md) — the first choice for a dangerous action is to scope it away; human-in-the-loop is for what remains.
- [Pre-execution checks](pre-execution-checks.md) — gating of irreversible actions is checklist item 2.
