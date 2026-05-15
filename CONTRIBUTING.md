# Contributing to agent-guardrails

Thanks for considering a contribution. This project is meant to be built on. This document explains how the pieces fit together and what contributions are checked against, so your work lands cleanly.

## Ground rules the whole project follows

Every tool and every contribution is held to these. They are not negotiable, because they are what makes the project trustworthy:

1. **Static and offline.** No tool executes actions, and no tool transmits a real credential anywhere. A safety tool that is itself a liability is worse than no tool. Contributions that call live cloud APIs with user tokens will not be merged.
2. **Auditable, not magic.** Scores and verdicts come from rules in JSON files or explicit, readable logic — never from opaque models. Anyone must be able to see *why* something scored the way it did.
3. **Pessimistic defaults.** An unrecognised action, scope, or capability is treated as risky until a human or a pattern says otherwise. Never fail open.
4. **Standard library only.** Python 3.8+, no third-party dependencies. Zero install friction is a feature.
5. **Every tool ships with tests and a self-demo.** An empty `tests/` folder is not a contribution. New behaviour needs a test that would fail without it.

## The single source of truth for scores

This matters and is easy to get wrong.

**Irreversibility scores live in exactly one place:** the Irreversibility Classifier's pattern files, at `toolset/irreversibility-classifier/patterns/`. Every other tool that needs a score reads it from there via the `scores.py` module (`ScoreBook`).

If you are working on the Blast Radius Scorer or any other tool and you find yourself wanting to write a number like `("volume.delete", 10)` in your code — **stop.** That number belongs in a pattern file. Add it there, then look it up. A pull request that hardcodes irreversibility scores outside the pattern files will be asked to change before review.

There are tests that enforce this (`test_scores.py`, and the source-of-truth tests in `test_scorer.py`). If you change scores, those tests keep everything honest.

## Common contributions, and how to make them

### Add a cloud provider

This is the highest-value contribution and touches two tools. GCP and Azure are the obvious gaps.

1. **Classifier pattern file.** Add `toolset/irreversibility-classifier/patterns/cloud_apis/<provider>.json`, following the structure of the existing `railway.json` / `aws.json` / `supabase.json`. Every operation needs a `match` key, a `score` (0–10), `reversible`, an `explanation`, and a `safer_alternative`. This is the source of truth — get the scores right and justify them in the explanation.
2. **Blast Radius Scorer provider.** Add `toolset/blast-radius-scorer/providers/<provider>.py` with a class extending `Provider`. It decides *which* operations a given credential scope unlocks; it must read the *scores* from `ScoreBook`, not define them. Register it in `providers/__init__.py`.
3. **Tests for both.** The classifier's pattern file is exercised by `test_classifier.py` and `test_scores.py`; add cases. The new provider needs cases in `test_scorer.py`, including one that asserts its scores match the source of truth.

### Document an incident

A well-documented incident database is valuable entirely on its own — it is what gets cited and shared.

1. Copy `incidents/template.md` to `incidents/<short-name>-<year>.md`.
2. Fill every section. Be factual and neutral — this is a flight-recorder entry, not an opinion piece. Cite sources.
3. Map the incident to the taxonomy: which named failure modes were involved?
4. If the incident reveals a failure mode the taxonomy does not cover, that is itself a finding — propose a taxonomy addition alongside it.

### Add or deepen a taxonomy entry

Each failure mode lives in its own file under `taxonomy/`. A good entry defines the failure mode precisely, distinguishes it from neighbouring ones, gives a concrete example, and points at the tools and framework practices that address it. Vague entries get ignored; precise ones get cited.

### Extend a ruleset

The colocation rules (`toolset/infrastructure-protection/colocated-risk-scanner/rules/`) and separation rules (`toolset/infrastructure-protection/separation-enforcer/rulesets/`) are JSON and meant to grow. Add a rule following the existing structure, give it a clear `id`, `rationale`, and `remediation`, and add a test that proves it fires when it should and stays quiet when it should not.

## Pull request checklist

Before you open a PR, confirm:

- [ ] All existing tests still pass. Run every suite — see `toolset/README.md` for the commands.
- [ ] New behaviour has a test that would fail without your change.
- [ ] No third-party dependencies were added.
- [ ] No irreversibility score is hardcoded outside the classifier's pattern files.
- [ ] No tool executes anything or transmits a real credential.
- [ ] If you added a tool or provider, it has a self-demo (`if __name__ == "__main__"`) and a README section.
- [ ] Explanations and rationales are written for a human who has to act on them — concrete, not generic.

## Running the full test suite

```bash
# From the repo root:
python toolset/irreversibility-classifier/tests/test_classifier.py
python toolset/irreversibility-classifier/tests/test_scores.py
python toolset/blast-radius-scorer/tests/test_scorer.py
python toolset/infrastructure-protection/colocated-risk-scanner/tests/test_scanner.py
python toolset/infrastructure-protection/credential-scope-auditor/tests/test_auditor.py
python toolset/infrastructure-protection/separation-enforcer/tests/test_enforcer.py
```

Each runs standalone and prints a pass/fail summary. They also work under `pytest` if you prefer.

## Questions and discussion

Open an issue. For a substantial change — a new tool, a structural change, anything touching the source-of-truth model — open an issue to discuss it *before* writing the code. It saves everyone time.

## Code of conduct

Be straightforward, be kind, assume good faith. This is a project about preventing harm; the way we work together should reflect that.
