# Colocated Blast Radius

## Definition

Things that should be isolated from each other share a boundary — the same storage volume, the same cloud account, the same access token, the same project, the same region. Because they share that boundary, a single action against the boundary affects all of them at once.

The most dangerous form is when a resource and its own safety net are colocated: production data and the backups that exist to recover it. The backups exist precisely so that destroying production is survivable. If they share a volume with production, they share its fate, and the safety net is gone exactly when it is needed.

Colocated blast radius is an *infrastructure arrangement*, not an action. It does nothing on its own. But it determines whether a single mistake is a contained incident or a catastrophe.

## Why it happens

- **Defaults.** Provisioning a database and "adding a backup" in the same project, same account, same volume is often the path of least resistance. Separation requires deliberate effort.
- **Invisible until tested.** A colocated backup looks fine — it exists, it runs, it appears in listings. Its fatal flaw only shows up at the moment of recovery, which is the worst possible time to discover it.
- **Cost and convenience.** Cross-account, cross-region separation costs more and is more complex to manage. Under pressure, colocation wins.
- **No one checks.** There is rarely a step in setup that explicitly asks "could one action destroy both of these?"

## Concrete example

The PocketOS incident is the defining case. The production database and its backups were on the same Railway storage volume. When the agent deleted that volume, it was not deleting "the database" — it was deleting the database *and every backup of it* in one operation. A correctly separated setup would have lost production and recovered from backups quickly. The colocation turned a recoverable mistake into a major data-loss event, with the most recent independently recoverable backup roughly three months old.

## How to detect it

- **Colocated Risk Scanner** — describes the problem. You give it an infrastructure description; it finds every place a resource and its backup, or production and staging, share a volume / account / project / region, and explains why each is dangerous.
- **Separation Enforcer** — blocks the problem. It turns separation requirements into a machine-readable policy with a pass/fail gate and real exit codes, so a colocated arrangement fails CI before an agent is ever deployed on top of it.

## How to prevent it

- **Backups live elsewhere.** Production data and its backups must not share a volume, and ideally not an account. A dedicated backup account with its own credentials — credentials the agent cannot reach — is the standard safeguard.
- **Separate environments fully.** Production and staging should not share a credential. An agent told to operate on staging must be unable to reach production at all.
- **Replicate across regions.** Backups in the same region as production share a region-level failure or a region-scoped mistaken action. At least one copy belongs elsewhere.
- **Encode it as policy.** Use the Separation Enforcer with a ruleset versioned alongside your infrastructure, so separation is checked on every change and regressions cannot slip back in.

## Related failure modes

- [Over-permissioning](over-permissioning.md) — over-permissioning sets how much *one credential* can reach; colocation sets how much *one action* destroys. The PocketOS catastrophe needed both.
- [Irreversibility blindness](irreversibility-blindness.md) — a colocated resource hit by an irreversible action is the worst case: the damage is both permanent and wide.
