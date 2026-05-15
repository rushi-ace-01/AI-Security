# Runaway Behavior

## Definition

The agent loops or multiplies its actions uncontrollably. Instead of taking a step, observing the result, and moving on, it repeats an action — or a cycle of actions — far more times than intended, often without ever reaching a stopping condition.

Runaway behavior is distinctive because the *individual* actions are usually harmless. One API call, one file write, one retry is fine. The damage comes from volume: the same harmless action performed thousands of times in a tight loop. It is a quantity problem, not a quality problem.

The consequences are real even when no single action is destructive: exhausted rate limits, enormous cloud bills, downstream systems overwhelmed by traffic, storage filled, services degraded into outage.

## Why it happens

- **Faulty stopping conditions.** The agent's loop depends on a condition that never becomes true — a check that always fails, a goal that is never quite reached — so it never exits.
- **Retry storms.** An action fails, the agent retries, the retry fails the same way, and there is no backoff or attempt limit. The agent retries as fast as it can, forever.
- **Recursive self-triggering.** The agent's action causes a state change that the agent then interprets as requiring another action, which causes another state change. The cycle feeds itself.
- **No global budget.** Nothing tracks total actions, total spend, or total time across the whole agent run. Each individual action looks reasonable in isolation because nothing has the whole picture.

## Concrete example

An agent is tasked with processing items from a queue. A bug means processed items are not removed from the queue, or are re-added. The agent processes the same items again and again — each cycle making real API calls, each call costing money and consuming rate limit. Reports exist of agents generating surprise cloud bills in the tens of thousands of dollars this way. No single call was wrong; there were just millions of them.

## How to detect it

Catching runaway behavior needs a runtime monitor watching the agent's action stream — counting how often a similar action recurs within a time window, and throttling or halting when a threshold is crossed. **Such a monitor is a future phase of this project and an open contribution area.** It is low-complexity and high-value: of the not-yet-built tools, a runaway monitor is among the most tractable.

Static analysis cannot catch a loop that only manifests at runtime, but it can ensure the *individual* actions in the loop are well-scoped, so a runaway agent burns budget rather than destroying infrastructure.

## How to prevent it

- **Hard action budgets.** Give every agent run a global cap — maximum total actions, maximum spend, maximum wall-clock time. When the budget is exhausted, the run stops, full stop.
- **Backoff and attempt limits on retries.** No action should be retried indefinitely. Exponential backoff plus a fixed maximum attempt count turns a retry storm into a bounded, brief failure.
- **Loop detection.** Track recent actions. If the same or a near-identical action recurs more than N times in M seconds, treat that as a signal to halt and alert, not continue.
- **Idempotency where possible.** Design the actions an agent takes so that repeating one is harmless. An idempotent action performed a thousand times is wasteful; a non-idempotent one is destructive.

## Related failure modes

- [Scope creep](scope-creep.md) — both are the agent doing more than intended. Scope creep is a reasoned expansion of *what* to do; runaway behavior is an uncontrolled repetition of *how much*.
- [Over-permissioning](over-permissioning.md) — runaway behavior's damage is bounded by what each looping action can do. A tightly scoped credential means a runaway agent wastes money instead of causing irreversible harm.
