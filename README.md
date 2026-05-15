<div align="center">

# 🛡️ agent-guardrails

### Catching AI agent failures *before* they cause damage

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-115%20passing-brightgreen.svg)](#-project-status)
[![Dependencies](https://img.shields.io/badge/dependencies-none-brightgreen.svg)](#)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-orange.svg)](CONTRIBUTING.md)

*An AI coding agent deleted a production database — and every backup — in 9 seconds.*
*This is the set of checks that would have caught it.*

[Quick start](#-quick-start) · [The toolset](#-the-toolset) · [How it works](#-how-it-works) · [Contributing](#-contributing)

</div>

---

> [!WARNING]
> **This happened in April 2026.** A Cursor agent running Claude Opus 4.6 was given a routine staging task. It hit a snag, decided on its own that deleting a storage volume would fix it, found an over-powered API token in an unrelated file, and issued one destructive call. Nine seconds later, PocketOS — a company serving car rental businesses — had lost its production database and every co-located backup. Customers reconstructed their data by hand.
>
> None of the prevention required clever AI. It required *checks nobody ran.*

## 💡 What this is

Autonomous AI agents are being handed real access to real infrastructure — production databases, cloud accounts, deployment pipelines, payment APIs. When an agent makes a mistake with that access, the result isn't a bad paragraph. It's a deleted database, a terminated server, a drained account.

**`agent-guardrails` is a practical response.** Three parts, one repository:

| | | |
|---|---|---|
| 📖 **Taxonomy** | The named ways agents cause operational damage | [`taxonomy/`](taxonomy/) |
| 🧭 **Framework** | Principles & checklists for building agents that fail safely | [`framework/`](framework/) |
| 🔧 **Toolset** | Working, tested tools that catch these failures before deployment | [`toolset/`](toolset/) |

Open source. Zero dependencies. Built to be contributed to.

## ⚙️ The toolset

Every tool is **static analysis** — it reasons about a *description* of an action, a credential, or an infrastructure setup. Nothing is executed. No live credentials ever touch it. Python 3.8+, standard library only.

| Tool | What it answers |
|------|-----------------|
| 🎯 **Irreversibility Classifier** | "Can this action be undone?" — scores any agent action 0–10. *The foundation; defines the scale the others use.* |
| 💥 **Blast Radius Scorer** | "If an agent holds this credential and goes wrong, how bad is it?" — scores 0–100. |
| 🔍 **Colocated Risk Scanner** | "Are production data and its backups sharing a boundary?" — finds the PocketOS arrangement. |
| 📋 **Credential Scope Auditor** | "Is this credential more powerful than its job needs?" — measures the over-permissioning gap. |
| 🚦 **Separation Enforcer** | "Does this setup pass our safety policy?" — a CI gate with real exit codes. |

> [!NOTE]
> Irreversibility scores live in **exactly one place** — the classifier's pattern files — and every other tool reads from there. No drift, no duplication. See [`toolset/README.md`](toolset/README.md).

## 🚀 Quick start

```bash
git clone https://github.com/YOUR_USERNAME/agent-guardrails.git
cd agent-guardrails

# Run the full toolset against a reconstruction of the PocketOS incident
python examples/pocketos_full_scan.py
```

<!-- TODO: replace with a real terminal recording or screenshot of the scan output. -->
<!-- A GIF here dramatically increases engagement. Tools: asciinema, terminalizer, vhs -->
<div align="center">
<i>▶️ All five checks flag the incident — before the agent would ever have run.</i>
</div>

```bash
# Try an individual tool's self-demo
python toolset/blast-radius-scorer/scorer.py

# Run a tool's tests
python toolset/irreversibility-classifier/tests/test_classifier.py
```

## 🧠 How it works

The tools aren't five separate things — they're a pipeline, each building on the last:

```
  🎯 Irreversibility Classifier
       scores one action            0–10
                │
                ▼
  💥 Blast Radius Scorer
       applies that scale to a      0–100
       whole credential
                │
                ▼
  🔍 Scanner   📋 Auditor   🚦 Enforcer
       is the danger justified?
       will the setup contain a mistake — or amplify it?
```

The classifier defines the scale. The scorer applies it to a credential. The infrastructure tools ask whether the surrounding setup turns one mistake into a catastrophe.

### The PocketOS chain — and where each link breaks

| What went wrong | Failure mode | Caught by |
|-----------------|--------------|-----------|
| Token far more powerful than the task | [Over-permissioning](taxonomy/over-permissioning.md) | Credential Scope Auditor, Blast Radius Scorer |
| Agent couldn't tell "delete" was permanent | [Irreversibility blindness](taxonomy/irreversibility-blindness.md) | Irreversibility Classifier |
| Backups shared a volume with production | [Colocated blast radius](taxonomy/colocated-blast-radius.md) | Colocated Risk Scanner, Separation Enforcer |
| Agent expanded a staging task into infra deletion | [Scope creep](taxonomy/scope-creep.md) | *Framework guidance* |

**Break any one link and the catastrophe doesn't happen.** That's the whole thesis.

## 📂 Repository structure

```
agent-guardrails/
├── 📖 taxonomy/     The 7 named failure modes, each in its own file
├── 📁 incidents/    Documented real-world incidents, in a consistent format
├── 🧭 framework/    Principles & checklists for building agents that fail safely
├── 🔧 toolset/      Working, tested tools — see toolset/README.md
└── ▶️  examples/     Copy-paste scripts showing the tools used end to end
```

New here? Start with [`taxonomy/README.md`](taxonomy/README.md) to understand the failure modes, then [`toolset/README.md`](toolset/README.md) for the tools that detect them.

## 📊 Project status

> [!IMPORTANT]
> **Phase 1 — static analysis. Complete and tested.**
> All five tools implemented · **115 passing tests** · single source of truth for scores · zero dependencies.

Phase 1 deliberately does **not** include runtime interception — nothing here watches a *running* agent. That's a separate, harder phase, and it's open for contribution. So is an aggregating CLI across all tools, and a packaged PyPI distribution.

## 🎯 A note on scope and naming

This project is about **AI agent safety in the operational sense** — preventing autonomous agents from causing accidental, real-world damage through the access they're given.

It is **not** a contribution to "the alignment problem" as that term is used in AI safety research — the hard, open question of making advanced AI reliably pursue intended goals. That's a different and much harder problem, and conflating the two would overclaim. What this repo does is narrower, achievable, and useful *today*: it makes a class of agent failures preventable with checks you can run in seconds.

## 🤝 Contributing

This is built to be contributed to. **Good first contributions:**

- 🌩️ **Add a cloud provider** — a new pattern file for the classifier + a provider class for the scorer. *GCP and Azure are the obvious gaps.*
- 📁 **Document an incident** — use [`incidents/template.md`](incidents/template.md). A well-documented incident database is valuable on its own.
- 📖 **Add or deepen a failure mode** in the taxonomy.
- 🚦 **Extend a ruleset** — the colocation and separation rules are JSON and meant to grow.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for how the pieces fit together and what contributions are checked against.

## 📜 License

[MIT](LICENSE) — use it, fork it, build on it.

---

<div align="center">
<sub>Built because "the appearance of safety is not safety" — and nine seconds is all it takes.</sub>
</div>
