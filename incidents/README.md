# Incident Database

A catalogue of real-world incidents where an autonomous AI agent caused operational damage.

The purpose is the same as an aviation incident database: not blame, but learning. Each entry records what happened, what the root causes were, and which [taxonomy](../taxonomy/) failure modes were involved — factually and neutrally — so that patterns become visible and prevention becomes concrete.

## Principles

Entries in this database follow a few rules, and contributions are held to them:

- **Factual and neutral.** This is a flight recorder, not an opinion column. Record what happened and what caused it. Do not editorialise, do not assign blame to individuals, do not speculate beyond what sources support.
- **Sourced.** Every factual claim should be traceable to a cited source. Where details are uncertain or disputed, say so explicitly.
- **Mapped to the taxonomy.** Each incident is analysed in terms of the named failure modes it involved. This is what makes the database more than a list of stories — it turns incidents into evidence about which failure modes recur.
- **Constructive.** Every entry ends with what would have prevented it. The point is prevention, not a hall of shame.

## How to contribute an incident

1. Copy [`template.md`](template.md) to `incidents/<short-name>-<year>.md` — for example `pocketos-2026.md`.
2. Fill in every section of the template. If a section genuinely does not apply or the information is not public, write that explicitly rather than leaving it blank.
3. Map the incident to the taxonomy. If it involves a failure mode the taxonomy does not yet cover, propose a taxonomy addition alongside your incident entry — a new pattern is itself a valuable finding.
4. Cite your sources.

See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for the full process.

## Current entries

| Incident | Year | Primary failure modes |
|----------|------|----------------------|
| [PocketOS database deletion](pocketos-2026.md) | 2026 | Scope creep, over-permissioning, irreversibility blindness, colocated blast radius |

As agentic AI is deployed more widely, this list will grow. A well-documented incident database is one of the most useful things this repository can offer — it is the evidence base the rest of the project is built on.
