# Over-permissioning

## Definition

The agent holds more access than its assigned task requires. The credential, token, role, or key it operates with grants capabilities the task never needs — and those unused capabilities sit there as latent risk, available for any mistake, confusion, or hijack to reach.

Over-permissioning is not itself a harmful action. It is the *precondition* that turns an ordinary mistake into a serious one. An over-permissioned agent that never makes a mistake causes no damage. But it removes the safety margin: when something does go wrong, the blast radius is whatever the credential allows, not whatever the task needed.

## Why it happens

- **Convenience.** A full-access token "just works" for every task, so one gets created and reused. Scoping a token per task is more work up front.
- **Unclear requirements.** Whoever provisions the credential does not know exactly what the agent will need, so they grant broadly to avoid the agent getting blocked.
- **Inheritance.** The agent reuses a human's credentials, or a CI system's, which were scoped for a much broader range of work.
- **Scope drift over time.** A credential is granted extra permissions for a one-off task and never has them removed.

## Concrete example

In the PocketOS incident, the AI coding agent was working a routine staging task and hit a credential mismatch — the kind of thing a read-and-maybe-restart credential would cover. The Railway API token it found and used instead had full account scope: it could delete volumes, databases, and entire projects. The task needed a sliver of what the token granted. When the agent's reasoning went wrong, it had the full token's power available, and used it.

## How to detect it

- **Credential Scope Auditor** — its core purpose. You declare what a credential is *for* (`stated_purpose`) and what it *can do* (`granted_capabilities`); the auditor reports every capability that exceeds the purpose, and flags destructive excess as a failure.
- **Blast Radius Scorer** — quantifies the consequence of over-permissioning. A credential that scores 100/100 is, almost by definition, far more powerful than any single agent task warrants.

## How to prevent it

- **Least privilege, per task.** Issue a credential scoped to exactly what the task needs. If the task is "read config and restart a service," the credential cannot delete anything.
- **Separate destructive capability.** Keep delete/drop/terminate permissions out of the agent's default credential entirely. If a task genuinely needs a destructive action, load a separate, single-purpose, narrowly-scoped credential for just that step.
- **Time-bound and revoke.** Prefer short-lived credentials. Audit long-lived ones and strip permissions that were granted for past tasks.
- **Audit before deployment.** Run the Credential Scope Auditor on every credential an agent will hold, and treat a FAIL verdict as a blocker.

## Related failure modes

- [Colocated blast radius](colocated-blast-radius.md) — over-permissioning sets how *much* one credential can reach; colocation sets how much *one action* destroys. Together they define the worst case.
- [Scope creep](scope-creep.md) — over-permissioning is about the credential; scope creep is about the agent's behaviour. An over-permissioned credential makes scope creep dangerous instead of merely wrong.
