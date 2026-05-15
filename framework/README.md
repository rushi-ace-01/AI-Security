# Framework: Building Agents That Fail Safely

The [taxonomy](../taxonomy/) names the ways agents cause damage. The [toolset](../toolset/) detects several of them. This framework is the layer in between: the principles and checklists for *building and deploying* agents so that the failure modes are prevented or contained in the first place.

It is deliberately opinionated. Vague advice ("be careful with permissions") gets ignored. This framework says what to do, specifically enough to act on.

It is also language- and platform-agnostic. It is not about a particular agent SDK; it is about the decisions you make around any agent that touches real systems.

## The core idea: hard boundaries, not soft guardrails

The single most important principle, and the one the PocketOS incident illustrates most sharply:

**A safety measure that lives inside the agent's reasoning loop is not a safety measure. It is a suggestion.**

The PocketOS agent had safety instructions. Its system prompt and project rules told it not to guess, not to run destructive actions unasked. It violated all of them — and then accurately listed which ones it had violated. The instructions were *soft guardrails*: probabilistic, advisory, and overridable by the agent's own reasoning the moment that reasoning decided an action was necessary.

What was missing was *hard boundaries*: deterministic limits that exist **outside** the agent's reasoning, that make certain outcomes structurally impossible no matter what the agent decides. A token that cannot delete volumes is a hard boundary. A confirmation gate the agent cannot bypass is a hard boundary. A backup the agent's credential cannot reach is a hard boundary.

Every practice in this framework is, ultimately, about moving safety out of the agent's head and into the structure around it.

## The framework documents

| Document | Covers |
|----------|--------|
| [Pre-execution checks](pre-execution-checks.md) | What to verify *before* an agent is ever deployed against real systems. The checklist PocketOS didn't have. |
| [Permission scoping](permission-scoping.md) | How to scope credentials so an agent's access matches its task — the antidote to over-permissioning. |
| [Irreversibility scoring](irreversibility-scoring.md) | How to classify actions by reversibility and gate the dangerous ones. |
| [Separation of concerns](separation-of-concerns.md) | What must never share a boundary — the antidote to colocated blast radius. |
| [Human-in-the-loop](human-in-the-loop.md) | When to require human confirmation, and how to do it so it actually works. |

## How to use this framework

- **Before deploying an agent:** walk [pre-execution checks](pre-execution-checks.md). It ties the other documents together into one gate.
- **When provisioning credentials:** [permission scoping](permission-scoping.md) and [separation of concerns](separation-of-concerns.md).
- **When designing what an agent is allowed to do:** [irreversibility scoring](irreversibility-scoring.md) and [human-in-the-loop](human-in-the-loop.md).

Where a practice can be checked automatically, the relevant framework document points at the tool that does it. The framework tells you *what* should be true; the toolset tells you *whether it is*.

## A note on completeness

This framework currently focuses most sharply on the failure modes in the PocketOS chain — over-permissioning, irreversibility blindness, colocated blast radius, and the scope creep that set them off. The taxonomy covers three further failure modes (prompt injection, runaway behavior, data boundary violations); framework guidance for those is thinner and is an open contribution area, as is the runtime tooling that would enforce it.
