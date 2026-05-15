# Separation of Concerns

What must never share a boundary. This is the antidote to [colocated blast radius](../taxonomy/colocated-blast-radius.md) — the failure mode that turned the PocketOS mistake from recoverable into catastrophic.

## The principle

**Things whose simultaneous loss would be catastrophic must not share a boundary that a single action can destroy.**

A "boundary" here is a volume, an account, a token, a project, or a region — any unit that one operation can act on as a whole. The question for any two things is: *can a single action take out both?* If yes, and if losing both is catastrophic, they are dangerously colocated.

The most important instance: **a resource and its own backup**. The backup exists so that destroying the resource is survivable. If the backup shares a boundary with the resource, it shares the resource's fate, and the safety net is gone at the exact moment it is needed.

## The separations that matter

### Production data and its backups

This is the one PocketOS got wrong, and it is the most important. Backups must not share a volume with the data they protect. Ideally they do not share an account either. The strongest version: backups live in a dedicated account with its own credentials — credentials the agent cannot reach — so no agent-held token can touch both production and its recovery path.

### Production and staging

These must not share a credential. An agent told to operate on staging must be structurally unable to reach production. If one token spans both, a confused agent or a wrong environment variable crosses from a safe environment into a live one.

### Read access and destructive access

The credential used for routine reads should not also carry destructive capability. When they are bundled, every harmless read step the agent takes is carrying unused destructive power. Split them: a default read-only credential, and a separate destructive credential loaded only for the specific step that needs it.

### Backups across regions

Backups in the same region as production share a region-level outage and a region-scoped mistaken action. At least one copy of a backup belongs in a different region.

### Sensitive and non-sensitive data

Secrets, credentials, and personal data should not share a folder, bucket, or database with the things an agent routinely works on. When they are colocated, an agent doing ordinary work inevitably brushes against data it was never meant to handle — see [data boundary violations](../taxonomy/data-boundary-violations.md).

## Soft separation is not separation

A separation that depends on the agent choosing to respect it is not a separation. "The backups are in the same account but the agent knows not to touch them" is a soft guardrail, and soft guardrails fail.

Real separation is structural: the agent's credential genuinely cannot reach the other side of the boundary. The test is not "would the agent touch it?" — it is "*could* it?"

## How to verify it

- The **Colocated Risk Scanner** takes a description of your infrastructure and finds every place two things that should be isolated share a volume, account, project, or region. It explains why each arrangement is dangerous and how to fix it.
- The **Separation Enforcer** turns separation requirements into a machine-readable policy with a pass/fail gate and real exit codes. Run it in CI; a colocated arrangement fails the build before an agent is ever deployed on top of it.

The intended workflow: use the scanner to *understand* your exposure, then encode the conclusions into an enforcer ruleset, versioned alongside your infrastructure, so the separations cannot silently regress.

## The test to apply

For any two things in your infrastructure, ask: **"Could one action destroy both of these — and if it did, would that be a catastrophe?"**

If both answers are yes, they need to be separated onto different boundaries, structurally, before an agent is given access to either.

## Related framework documents

- [Permission scoping](permission-scoping.md) — scoping limits what one credential can reach; separation makes sure no credential can reach two things that must stay isolated. They work together.
- [Pre-execution checks](pre-execution-checks.md) — separation is checklist item 3.
