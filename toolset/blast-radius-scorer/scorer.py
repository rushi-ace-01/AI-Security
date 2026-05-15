"""
Blast Radius Scorer
===================

Answers one question: if this credential is handed to an AI agent and the
agent goes wrong, how much damage can it do?

You give it a permission/scope DESCRIPTION for a credential (never the live
token itself -- see providers/base.py for why). It expands that into the
concrete set of destructive actions the credential unlocks, then aggregates
them into a single 0-100 blast radius score with a breakdown.

This is static, pre-deployment analysis. It is the check you run BEFORE you
let an agent near your infrastructure -- the check PocketOS did not have.

Typical usage:

    from scorer import BlastRadiusScorer

    scorer = BlastRadiusScorer()

    report = scorer.score("railway", {
        "label": "agent-token",
        "scope": "full",
        "environment": "production",
        "projects": ["*"],
    })

    print(report)                 # full human-readable report
    print(report.score)           # 0-100
    print(report.risk_level)      # CRITICAL / HIGH / MEDIUM / LOW / MINIMAL
    print(report.to_dict())       # JSON-friendly

Score model
-----------
Each capability contributes points based on its irreversibility (0-10):

    irreversibility 10  -> 25 base points   (permanent, unrecoverable)
    irreversibility 8-9 -> 15 base points   (effectively irreversible)
    irreversibility 6-7 -> 7  base points   (hard to reverse)
    irreversibility 3-5 -> 2  base points   (reversible, with side effects)
    irreversibility 0-2 -> 0  base points   (safe / read-only)

Context multipliers are then applied:
    targets production           x1.5
    targets a backup/snapshot    x1.5   (destroying recovery paths is worst-case)
    scoped to "all resources"    x1.2

The raw total is capped and normalised to 0-100. The point of the model is
not false precision -- it is a consistent, explainable ranking so you can
compare two credentials and tell which one is the bigger liability.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

from providers import get_provider, PROVIDERS
from providers.base import Capability, ProviderReport


# Base points per irreversibility band.
def _base_points(irreversibility: int) -> int:
    if irreversibility >= 10:
        return 25
    if irreversibility >= 8:
        return 15
    if irreversibility >= 6:
        return 7
    if irreversibility >= 3:
        return 2
    return 0


# Score at or above which the credential is considered too dangerous to
# hand to an autonomous agent without changes.
CRITICAL_THRESHOLD = 70
HIGH_THRESHOLD = 45
MEDIUM_THRESHOLD = 20
LOW_THRESHOLD = 5


@dataclass
class ScoredCapability:
    """A capability plus the points it contributed and why."""

    action: str
    irreversibility: int
    resource_scope: str
    explanation: str
    base_points: int
    multipliers: list = field(default_factory=list)   # human-readable, e.g. "production x1.5"
    final_points: float = 0.0


@dataclass
class BlastRadiusReport:
    """The full result of scoring one credential."""

    provider: str
    credential_label: str
    score: int                                  # 0-100
    raw_points: float
    scored_capabilities: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)

    @property
    def risk_level(self) -> str:
        if self.score >= CRITICAL_THRESHOLD:
            return "CRITICAL"
        if self.score >= HIGH_THRESHOLD:
            return "HIGH"
        if self.score >= MEDIUM_THRESHOLD:
            return "MEDIUM"
        if self.score >= LOW_THRESHOLD:
            return "LOW"
        return "MINIMAL"

    @property
    def destructive_count(self) -> int:
        return sum(1 for c in self.scored_capabilities if c.irreversibility >= 6)

    @property
    def irreversible_count(self) -> int:
        return sum(1 for c in self.scored_capabilities if c.irreversibility >= 8)

    def safe_to_automate(self, threshold: int = HIGH_THRESHOLD) -> bool:
        """Whether this credential is below the bar for autonomous agent use."""
        return self.score < threshold

    def to_dict(self) -> dict:
        d = asdict(self)
        d["risk_level"] = self.risk_level
        d["destructive_count"] = self.destructive_count
        d["irreversible_count"] = self.irreversible_count
        d["safe_to_automate"] = self.safe_to_automate()
        return d

    def __str__(self) -> str:
        bar_len = 40
        filled = int(round(self.score / 100 * bar_len))
        bar = "#" * filled + "-" * (bar_len - filled)

        lines = [
            "=" * 64,
            f"  BLAST RADIUS REPORT  --  {self.provider}",
            "=" * 64,
            f"  Credential:   {self.credential_label}",
            f"  Score:        {self.score}/100  [{self.risk_level}]",
            f"  [{bar}]",
            f"  Destructive capabilities:   {self.destructive_count}",
            f"  Irreversible capabilities:  {self.irreversible_count}",
            f"  Safe to hand to an agent:   {'yes' if self.safe_to_automate() else 'NO'}",
        ]

        if self.warnings:
            lines.append("")
            lines.append("  WARNINGS")
            lines.append("  " + "-" * 60)
            for w in self.warnings:
                lines.append(f"  ! {w}")

        if self.scored_capabilities:
            lines.append("")
            lines.append("  TOP CONTRIBUTORS")
            lines.append("  " + "-" * 60)
            top = sorted(
                self.scored_capabilities, key=lambda c: c.final_points, reverse=True
            )[:8]
            for c in top:
                mult = f"  ({', '.join(c.multipliers)})" if c.multipliers else ""
                lines.append(
                    f"  {c.final_points:6.1f} pts  "
                    f"[irr {c.irreversibility:>2}]  {c.action}{mult}"
                )

        if self.recommendations:
            lines.append("")
            lines.append("  RECOMMENDATIONS")
            lines.append("  " + "-" * 60)
            for r in self.recommendations:
                lines.append(f"  -> {r}")

        if self.notes:
            lines.append("")
            for n in self.notes:
                lines.append(f"  note: {n}")

        lines.append("=" * 64)
        return "\n".join(lines)


class BlastRadiusScorer:
    """Scores a credential's blast radius using the relevant provider."""

    def __init__(self):
        self._providers = PROVIDERS

    @property
    def supported_providers(self) -> list:
        return sorted(self._providers.keys())

    def score(self, provider_name: str, config: dict) -> BlastRadiusReport:
        """
        provider_name : "railway" | "aws" | "supabase"
        config        : a scope DESCRIPTION dict -- see each provider's docstring.
        """
        provider = get_provider(provider_name)
        provider_report: ProviderReport = provider.analyze(config)
        return self._aggregate(provider_report)

    # ------------------------------------------------------------------ #
    # Aggregation
    # ------------------------------------------------------------------ #
    def _aggregate(self, pr: ProviderReport) -> BlastRadiusReport:
        scored: list = []
        raw_total = 0.0

        for cap in pr.capabilities:
            base = _base_points(cap.irreversibility)
            multipliers = []
            factor = 1.0

            if base > 0:  # multipliers only matter for capabilities that score
                if cap.targets_production:
                    factor *= 1.5
                    multipliers.append("production x1.5")
                if cap.targets_backup:
                    factor *= 1.5
                    multipliers.append("backup/snapshot x1.5")
                if "all" in cap.resource_scope.lower():
                    factor *= 1.2
                    multipliers.append("all-resources x1.2")

            final = base * factor
            raw_total += final

            scored.append(
                ScoredCapability(
                    action=cap.action,
                    irreversibility=cap.irreversibility,
                    resource_scope=cap.resource_scope,
                    explanation=cap.explanation,
                    base_points=base,
                    multipliers=multipliers,
                    final_points=round(final, 1),
                )
            )

        # Normalise. 120 raw points is treated as a full 100 -- a credential
        # with several production-scoped irreversible actions saturates fast,
        # which is the intended behaviour.
        score = min(100, int(round(raw_total / 120 * 100)))

        report = BlastRadiusReport(
            provider=pr.provider,
            credential_label=pr.credential_label,
            score=score,
            raw_points=round(raw_total, 1),
            scored_capabilities=scored,
            warnings=list(pr.warnings),
            notes=list(pr.notes),
        )
        report.recommendations = self._recommend(report)
        return report

    # ------------------------------------------------------------------ #
    # Recommendations
    # ------------------------------------------------------------------ #
    def _recommend(self, report: BlastRadiusReport) -> list:
        recs: list = []

        if report.score >= CRITICAL_THRESHOLD:
            recs.append(
                "Do NOT hand this credential to an autonomous agent as-is. "
                "Its blast radius is in the critical band."
            )
        elif report.score >= HIGH_THRESHOLD:
            recs.append(
                "Reduce this credential's scope before automated use. "
                "It is above the recommended bar for hands-off agent operation."
            )

        if report.irreversible_count > 0:
            recs.append(
                f"{report.irreversible_count} capability(ies) are effectively "
                "irreversible. Remove the ones the agent does not strictly need, "
                "and gate any that remain behind a human-in-the-loop confirmation."
            )

        backup_caps = [c for c in report.scored_capabilities if "backup" in " ".join(c.multipliers)]
        if backup_caps:
            recs.append(
                "This credential can destroy backups or snapshots. Move backups to "
                "an account or project this credential cannot reach, so a single "
                "mistaken call cannot take out both production and its recovery path."
            )

        prod_irreversible = [
            c for c in report.scored_capabilities
            if c.irreversibility >= 8 and "production x1.5" in c.multipliers
        ]
        if prod_irreversible:
            recs.append(
                "Irreversible actions are scoped to production. If the agent's job "
                "is development or testing, point the credential at a non-production "
                "environment instead."
            )

        if not recs:
            recs.append(
                "Blast radius is within a reasonable range. Still apply least "
                "privilege and re-run this check whenever the credential's scope changes."
            )

        return recs


if __name__ == "__main__":
    # Self-demo. Run: python scorer.py
    scorer = BlastRadiusScorer()

    print("\n>>> Example 1: the PocketOS-shaped credential\n")
    print(scorer.score("railway", {
        "label": "cursor-agent-token",
        "scope": "full",
        "environment": "production",
        "projects": ["*"],
    }))

    print("\n>>> Example 2: a properly scoped Railway token\n")
    print(scorer.score("railway", {
        "label": "ci-readonly",
        "scope": "read_only",
        "environment": "staging",
        "projects": ["my-app"],
    }))

    print("\n>>> Example 3: an AWS admin credential handed to an agent\n")
    print(scorer.score("aws", {
        "label": "agent-role",
        "environment": "production",
        "actions": ["*"],
        "resources": ["*"],
    }))

    print("\n>>> Example 4: a Supabase service_role key\n")
    print(scorer.score("supabase", {
        "label": "agent-db-key",
        "key_type": "service_role",
        "environment": "production",
    }))
