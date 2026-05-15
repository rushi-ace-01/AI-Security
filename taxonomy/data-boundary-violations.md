# Data Boundary Violations

## Definition

The agent touches, moves, copies, or exposes data it was never directed to handle. The data was within its technical reach but outside its task — and the agent crossed that line, usually without any awareness that a line existed.

This covers a range of severity: an agent reading files in a directory it was pointed at but that contained more than intended; an agent including sensitive data in a log, an error message, or an output it sends somewhere; an agent copying data from a context it was allowed to read into a context it should not have. At the severe end, it is data exfiltration — proprietary code, customer records, or secrets ending up somewhere they should never be.

The defining feature is that the agent treated *reachability* as *permission*. It could access the data, so it did.

## Why it happens

- **Reach exceeds task.** The agent is given access to a directory, a database, an account — and the task only concerns part of it. Nothing stops the agent from using the rest of the reach it was given.
- **Data travels with context.** An agent gathering "context" to do its job may pull in far more than needed, then carry it into outputs, logs, or external API calls.
- **No classification of sensitivity.** The agent has no signal that *this* file is secret and *that* one is not. To the agent they are just files.
- **Colocation again.** As with [colocated blast radius](colocated-blast-radius.md), data that should be isolated often is not — sensitive and non-sensitive data share a folder, a bucket, a database — so an agent working with one inevitably brushes against the other.
- **It is often a symptom.** A data boundary violation is frequently the *result* of another failure mode: [prompt injection](prompt-injection.md) instructing the agent to exfiltrate, or [scope creep](scope-creep.md) leading it to "look around" beyond its task.

## Concrete example

An agent is asked to debug an application and given read access to the application's directory. That directory also contains a `.env` file with production credentials, and a folder of customer data exports. The agent, building context, reads all of it — and then includes a chunk of it in a detailed status message it posts to a shared channel, or sends to an external API as part of a request. Nobody told it to handle the credentials or the customer data. It just had them in reach.

## How to detect it

Comprehensive detection needs runtime awareness of what data the agent is reading and where that data then goes — a monitor on the agent's data flows. **That is a future phase of this project and an open contribution area.**

Static analysis covers part of it today: the **Separation Enforcer** can encode rules that sensitive and non-sensitive data must not share a boundary, and that an agent's credential must not span both — so the *arrangement* that makes data boundary violations easy can be caught and blocked before deployment.

## How to prevent it

- **Scope data access to the task.** Point the agent at exactly the data it needs — a specific file, a specific table, a specific scoped key — not a directory or account that happens to contain it.
- **Isolate sensitive data.** Secrets, credentials, and personal data should not share a folder, bucket, or database with the things an agent routinely works on. Separation makes accidental contact impossible rather than merely discouraged.
- **Treat outputs as boundary crossings.** Logs, status messages, error reports, and external API calls all carry data out of the agent's working context. Anything sensitive must be redacted before it reaches them.
- **Never let reachability imply permission.** Build agents and tools so that "the agent can read X" and "the agent should use X" are separate decisions, and the second is explicit.

## Related failure modes

- [Prompt injection](prompt-injection.md) — a frequent *cause*: the injected instruction is often "exfiltrate this data." A data boundary violation is the outcome.
- [Scope creep](scope-creep.md) — an agent that expands its own task often does so by reaching into data beyond its assignment.
- [Colocated blast radius](colocated-blast-radius.md) — the same underlying problem (things that should be isolated are not), applied to data rather than to destructive actions.
