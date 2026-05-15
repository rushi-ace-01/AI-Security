# Incident: [Short descriptive title]

> Copy this file to `incidents/<short-name>-<year>.md` and fill in every section.
> Keep it factual and neutral. Cite sources. If information is not public, say so
> rather than guessing.

## Summary

A two-to-four sentence plain-language description of what happened. Someone should
be able to read just this section and understand the incident.

## At a glance

| Field | Value |
|-------|-------|
| Date | When it happened (or "reported [date]" if the incident date is unknown) |
| Organisation | The affected organisation, if public |
| Agent / system | What AI agent or system was involved (model, platform, tool) |
| Trigger | The task or situation the agent was handling when it went wrong |
| Damage | What was actually lost or harmed |
| Downtime / impact | Duration and scope of the impact |
| Recovery | Whether and how the damage was recovered |

## Timeline

A factual, ordered account of what happened. Bullet points are fine. Stick to what
sources support; mark anything uncertain.

- ...
- ...

## Root cause analysis

What actually allowed this to happen — not just the proximate action, but the chain
of conditions behind it. Most incidents are a chain, not a single fault.

- ...
- ...

## Taxonomy mapping

Which [failure modes](../taxonomy/) were involved, and how each one showed up in
this specific incident.

| Failure mode | How it appeared here |
|--------------|----------------------|
| [e.g. Over-permissioning](../taxonomy/over-permissioning.md) | ... |
| ... | ... |

## What would have prevented it

Concrete preventions, mapped where possible to the chain above. Ideally note which
ones are addressable by tools or practices in this repository.

- ...
- ...

## Sources

- [Source title](url)
- ...

> Note any points where sources conflict or where key details are not publicly known.
