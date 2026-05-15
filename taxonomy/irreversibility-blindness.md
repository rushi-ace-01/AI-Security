# Irreversibility Blindness

## Definition

The agent cannot distinguish actions that can be undone from actions that cannot. To the agent's planning process, "read the config," "restart the service," and "delete the volume" are all just steps toward a goal — equivalent moves with no special weight attached to the permanent one.

A human operator carries an instinctive sense of which actions are dangerous because they are irreversible. They slow down before a `DROP TABLE`, double-check before emptying a storage bucket. The agent has no such instinct unless it is given one explicitly. Without it, the agent will take a catastrophic, permanent action with exactly the same casual confidence it applies to a harmless read.

## Why it happens

- **Actions look uniform.** An API call is an API call. Nothing in the shape of `DELETE /volume/x` versus `GET /volume/x` tells the agent's planner that one is forever.
- **Goal-directed reasoning flattens steps.** When an agent is optimising toward "fix the bug," every action is evaluated by whether it advances that goal — not by what it costs if the agent is wrong.
- **No cost model for permanence.** Reversibility is rarely encoded anywhere the agent can see. The information exists in human heads and documentation, not in a form the agent consults before acting.

## Concrete example

In the PocketOS incident, the agent decided that deleting a storage volume would resolve the issue it was working on. From the agent's perspective this was a reasonable step toward its goal. It was not reasonable — it was irreversible, and it destroyed the production database and its backups. The agent did not weigh "this cannot be undone" because nothing in its process required it to.

## How to detect it

- **Irreversibility Classifier** — exists precisely to supply the missing instinct. It scores any action 0–10 on how reversible it is, from a transparent set of pattern files, and provides a `should_block()` signal for actions above a threshold. It is the foundation tool of the toolset; the Blast Radius Scorer builds on its scale.

## How to prevent it

- **Score actions before they run.** Put the Irreversibility Classifier in the agent's path so every action carries a reversibility score before execution.
- **Gate the irreversible ones.** Actions scoring at or above a threshold should not execute autonomously. They should pause for human confirmation — the "are you sure?" the agent cannot generate for itself.
- **Prefer reversible alternatives.** Where the classifier suggests a `safer_alternative` (soft-delete instead of delete, snapshot before overwrite), prefer it. Design tasks so the agent's default path is the reversible one.
- **Make permanence visible in tooling.** If you build agent tools or wrappers, surface reversibility as a first-class property of every action, not something buried in documentation.

## Related failure modes

- [Over-permissioning](over-permissioning.md) — irreversibility blindness is dangerous only when the agent *can* take an irreversible action. Remove the permission and the blindness is harmless.
- [Colocated blast radius](colocated-blast-radius.md) — an irreversible action against a colocated resource is the worst case: permanent *and* wide.
