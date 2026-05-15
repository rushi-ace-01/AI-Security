# Pre-Execution Checks

The checklist to walk **before** an autonomous agent is deployed against real systems. This is the gate PocketOS did not have. Every item here is something that can be verified ahead of time, with no agent running and no live credentials in play.

Treat this as a hard gate: if an item fails, the agent does not get deployed until it is fixed.

## The checklist

### 1. Credential scope matches the task

- [ ] Every credential the agent will hold has a **stated purpose** written down.
- [ ] Every credential has been audited against that purpose — its capabilities do not exceed what the task needs.
- [ ] No credential the agent uses for routine work carries destructive capability (delete, drop, terminate, truncate).
- [ ] No credential is scoped to "all" / account-wide when the task concerns one project or resource.

*Tool: the **Credential Scope Auditor** checks a credential against its stated purpose. The **Blast Radius Scorer** quantifies the worst case.*

### 2. Irreversible actions are gated

- [ ] You have enumerated which actions in the agent's reach are irreversible.
- [ ] Every irreversible action either is removed from the agent's reach, or pauses for human confirmation before executing.
- [ ] The confirmation gate lives **outside** the agent's reasoning loop — the agent cannot decide to skip it.

*Tool: the **Irreversibility Classifier** scores actions and signals which should be blocked.*

### 3. Infrastructure is separated

- [ ] Production data and its backups do not share a volume.
- [ ] Production data and its backups do not share an account.
- [ ] Backups exist in at least one location the agent's credential cannot reach.
- [ ] Production and staging do not share a credential.

*Tool: the **Colocated Risk Scanner** finds violations; the **Separation Enforcer** blocks them in CI.*

### 4. The agent's boundary is defined, not just its task

- [ ] The agent has been given an explicit scope: what it should do **and** what is out of bounds.
- [ ] The out-of-bounds actions are prevented by access control, not only by instruction.
- [ ] If the agent concludes it needs to act outside its scope, that conclusion pauses for human review rather than becoming an action.

### 5. There is a budget and a kill switch

- [ ] The agent run has a hard cap — maximum actions, maximum spend, maximum wall-clock time.
- [ ] Retries have backoff and a maximum attempt count. Nothing retries indefinitely.
- [ ] There is a way to halt the agent immediately, and someone is positioned to use it.

### 6. External content is treated as data, not instructions

- [ ] Content the agent reads to do its job (web pages, files, tickets, API responses) is treated as untrusted data — never obeyed as instructions.
- [ ] Operator instructions and ingested content are kept in structurally distinct parts of the agent's input where possible.
- [ ] Consequential actions driven by freshly-ingested external content pause for review.

## How the checklist maps to failure modes

| Check | Failure mode it addresses |
|-------|--------------------------|
| 1. Credential scope | [Over-permissioning](../taxonomy/over-permissioning.md) |
| 2. Irreversible actions gated | [Irreversibility blindness](../taxonomy/irreversibility-blindness.md) |
| 3. Infrastructure separated | [Colocated blast radius](../taxonomy/colocated-blast-radius.md) |
| 4. Boundary defined | [Scope creep](../taxonomy/scope-creep.md) |
| 5. Budget and kill switch | [Runaway behavior](../taxonomy/runaway-behavior.md) |
| 6. External content as data | [Prompt injection](../taxonomy/prompt-injection.md), [Data boundary violations](../taxonomy/data-boundary-violations.md) |

## Why "before" matters

Every check here is a *pre-execution* check by design. Once an autonomous agent is running against production, the window for prevention is gone — you are in detection and response. The PocketOS deletion took nine seconds; no human-in-the-loop response is fast enough to catch a nine-second mistake. The leverage is entirely in what you verify beforehand.

Checks 1–3 are substantially automatable today with the toolset. Checks 4–6 are currently framework-level practice; the runtime tooling to enforce them is an open contribution area.
