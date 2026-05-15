# Taxonomy of AI Agent Failure Modes

This is a catalogue of the distinct ways autonomous AI agents cause accidental operational damage. The goal is a shared, precise vocabulary — so that when an incident happens, it can be named, and so that tools and practices can be mapped to specific, well-defined problems rather than a vague sense of "AI risk."

Each failure mode has its own file with a precise definition, a concrete example, how to detect it, and how to prevent it.

## Scope

These are **operational** failure modes — ways an agent with real access causes real damage through ordinary mistakes, confusion, or manipulation. This taxonomy is not about the research-level alignment problem (whether advanced AI pursues intended goals at all). It is about the narrower, immediately practical question: given that we are handing agents access today, how do they cause harm, and how do we stop it.

## The seven failure modes

| # | Failure mode | One-line definition |
|---|--------------|---------------------|
| 1 | [Over-permissioning](over-permissioning.md) | The agent holds more access than its task requires. |
| 2 | [Irreversibility blindness](irreversibility-blindness.md) | The agent cannot distinguish actions that can be undone from those that cannot. |
| 3 | [Colocated blast radius](colocated-blast-radius.md) | Things that should be isolated share a boundary, so one action destroys several. |
| 4 | [Scope creep](scope-creep.md) | The agent goes beyond its assigned task to "solve" a broader problem. |
| 5 | [Prompt injection](prompt-injection.md) | External content the agent reads hijacks what the agent does. |
| 6 | [Runaway behavior](runaway-behavior.md) | The agent loops or multiplies actions uncontrollably. |
| 7 | [Data boundary violations](data-boundary-violations.md) | The agent touches, moves, or exposes data it was never directed to. |

## How the failure modes interact

Real incidents are rarely one failure mode. They are usually a chain — one failure mode creates the conditions for the next, and the damage happens where they meet.

The PocketOS incident is the clearest example. **Over-permissioning** gave the agent a token that could delete infrastructure. **Irreversibility blindness** meant it treated "delete the volume" as just another step. **Colocated blast radius** meant that one deletion took out both production and its backups. Remove any one link and the catastrophe does not happen. That is the practical hope of this taxonomy: incidents need a chain, and chains can be broken at any link.

## How this maps to the toolset

| Failure mode | Primary tool(s) |
|--------------|-----------------|
| Over-permissioning | Credential Scope Auditor, Blast Radius Scorer |
| Irreversibility blindness | Irreversibility Classifier |
| Colocated blast radius | Colocated Risk Scanner, Separation Enforcer |
| Scope creep | *(framework guidance; runtime detection is a future phase)* |
| Prompt injection | *(framework guidance; a detector is a future phase)* |
| Runaway behavior | *(framework guidance; a monitor is a future phase)* |
| Data boundary violations | *(framework guidance; partially covered by Separation Enforcer)* |

The toolset currently has the strongest coverage for the three failure modes in the PocketOS chain, because that chain is the most common catastrophic pattern and the most tractable to catch with static analysis. The remaining four are documented here and addressed in the framework; tooling for them is open for contribution.

## Contributing to the taxonomy

If you encounter a failure mode this catalogue does not cover — or an existing entry that is imprecise — see [`CONTRIBUTING.md`](../CONTRIBUTING.md). A taxonomy is only useful if it is precise and kept current.
