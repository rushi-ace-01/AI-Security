"""
Credential Scope Auditor
========================

Takes a single credential description and answers a focused question:
"What can this specific credential destroy, and is it more powerful than its
stated job requires?"

Where the Blast Radius Scorer produces a 0-100 number for ranking credentials
against each other, the Auditor is about ONE credential at a time and about
the GAP between what a credential *can* do and what it is *supposed* to do.
That gap -- the over-permissioning -- is what bites you. The PocketOS agent's
token could delete volumes; its actual job was fixing a credential mismatch.
The job needed read and maybe restart. The token granted destruction.

------------------------------------------------------------------------
INPUT FORMAT
------------------------------------------------------------------------
    {
      "id": "agent-token",
      "stated_purpose": "read_only",     # what the credential is FOR
      "granted_capabilities": [          # what it can ACTUALLY do
          "read", "restart", "delete", "deploy"
      ],
      "environment": "production",
      "scope": "all"                     # "all" | "single-project" | "single-resource"
    }

`stated_purpose` is one of a small vocabulary of intent levels:

    read_only      -> should only read
    operate        -> read + non-destructive operations (restart, redeploy)
    modify         -> read + operate + reversible writes
    full_admin     -> everything, including destruction (rarely right for an agent)

Each granted capability is classified by how far beyond the stated purpose it
reaches. Capabilities that exceed the purpose are the audit's findings.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional


# Intent levels, ordered from least to most powerful.
PURPOSE_LEVELS = ["read_only", "operate", "modify", "full_admin"]
PURPOSE_RANK = {name: i for i, name in enumerate(PURPOSE_LEVELS)}

# Every capability the auditor knows about, mapped to the MINIMUM purpose
# level that legitimately includes it.
CAPABILITY_MIN_PURPOSE = {
    # read_only
    "read": "read_only",
    "list": "read_only",
    "describe": "read_only",
    # operate
    "restart": "operate",
    "redeploy": "operate",
    "scale": "operate",
    "deploy": "operate",
    # modify
    "write": "modify",
    "update": "modify",
    "create": "modify",
    "configure": "modify",
    # full_admin (destructive)
    "delete": "full_admin",
    "drop": "full_admin",
    "terminate": "full_admin",
    "truncate": "full_admin",
    "destroy": "full_admin",
}

# Capabilities considered outright destructive / irreversible.
DESTRUCTIVE_CAPABILITIES = {"delete", "drop", "terminate", "truncate", "destroy"}


@dataclass
class CapabilityFinding:
    """One granted capability assessed against the stated purpose."""

    capability: str
    min_purpose: str
    within_purpose: bool
    destructive: bool
    note: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AuditReport:
    """The result of auditing one credential."""

    credential_id: str
    stated_purpose: str
    environment: str
    scope: str
    capability_findings: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)

    @property
    def over_permissioned(self) -> bool:
        return any(not f.within_purpose for f in self.capability_findings)

    @property
    def excess_capabilities(self) -> list:
        return [f.capability for f in self.capability_findings if not f.within_purpose]

    @property
    def destructive_excess(self) -> list:
        return [
            f.capability for f in self.capability_findings
            if not f.within_purpose and f.destructive
        ]

    @property
    def verdict(self) -> str:
        if self.destructive_excess:
            return "FAIL"
        if self.over_permissioned:
            return "WARN"
        return "PASS"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["verdict"] = self.verdict
        d["over_permissioned"] = self.over_permissioned
        d["excess_capabilities"] = self.excess_capabilities
        d["destructive_excess"] = self.destructive_excess
        return d

    def __str__(self) -> str:
        lines = [
            "=" * 64,
            "  CREDENTIAL SCOPE AUDIT",
            "=" * 64,
            f"  Credential:      {self.credential_id}",
            f"  Stated purpose:  {self.stated_purpose}",
            f"  Environment:     {self.environment}",
            f"  Scope:           {self.scope}",
            f"  Verdict:         {self.verdict}",
            "",
            "  CAPABILITIES",
            "  " + "-" * 60,
        ]
        for f in self.capability_findings:
            mark = "ok " if f.within_purpose else "OVER"
            dmark = " [DESTRUCTIVE]" if f.destructive else ""
            lines.append(f"  [{mark}] {f.capability:<12} {f.note}{dmark}")

        if self.warnings:
            lines.append("")
            lines.append("  WARNINGS")
            lines.append("  " + "-" * 60)
            for w in self.warnings:
                lines.append(f"  ! {w}")

        if self.recommendations:
            lines.append("")
            lines.append("  RECOMMENDATIONS")
            lines.append("  " + "-" * 60)
            for r in self.recommendations:
                lines.append(f"  -> {r}")

        lines.append("=" * 64)
        return "\n".join(lines)


class CredentialScopeAuditor:
    """Audits a single credential against its stated purpose."""

    def audit(self, credential: dict) -> AuditReport:
        cred_id = credential.get("id", "unlabelled-credential")
        purpose = (credential.get("stated_purpose") or "read_only").lower()
        environment = (credential.get("environment") or "unknown").lower()
        scope = (credential.get("scope") or "unknown").lower()
        granted = credential.get("granted_capabilities", [])

        if purpose not in PURPOSE_RANK:
            # Unknown purpose -> assume the strictest, so everything looks
            # over-permissioned until the user states a real purpose.
            report = AuditReport(
                credential_id=cred_id,
                stated_purpose=f"{purpose} (unrecognised, treated as read_only)",
                environment=environment,
                scope=scope,
            )
            purpose = "read_only"
        else:
            report = AuditReport(
                credential_id=cred_id,
                stated_purpose=purpose,
                environment=environment,
                scope=scope,
            )

        purpose_rank = PURPOSE_RANK[purpose]

        for cap in granted:
            cap = cap.lower()
            min_purpose = CAPABILITY_MIN_PURPOSE.get(cap)
            destructive = cap in DESTRUCTIVE_CAPABILITIES

            if min_purpose is None:
                # Unknown capability: flag it, treat as exceeding purpose.
                report.capability_findings.append(
                    CapabilityFinding(
                        capability=cap,
                        min_purpose="unknown",
                        within_purpose=False,
                        destructive=destructive,
                        note="not a recognised capability; review manually",
                    )
                )
                continue

            within = PURPOSE_RANK[min_purpose] <= purpose_rank
            if within:
                note = f"within '{purpose}' purpose"
            else:
                note = (
                    f"requires '{min_purpose}' purpose, but credential is "
                    f"only stated as '{purpose}'"
                )

            report.capability_findings.append(
                CapabilityFinding(
                    capability=cap,
                    min_purpose=min_purpose,
                    within_purpose=within,
                    destructive=destructive,
                    note=note,
                )
            )

        self._add_warnings(report)
        self._add_recommendations(report)
        return report

    # ------------------------------------------------------------------ #
    def _add_warnings(self, report: AuditReport) -> None:
        if report.destructive_excess:
            report.warnings.append(
                f"Credential can perform destructive actions "
                f"({', '.join(report.destructive_excess)}) that its stated "
                f"purpose '{report.stated_purpose}' does not call for. This is "
                "the over-permissioning pattern behind the PocketOS incident."
            )
        if report.environment in ("production", "unknown") and report.destructive_excess:
            report.warnings.append(
                f"Destructive excess capabilities are exposed to "
                f"'{report.environment}'. The blast radius is live infrastructure."
            )
        if report.scope == "all" and report.over_permissioned:
            report.warnings.append(
                "Credential scope is 'all'. Excess capabilities are not even "
                "confined to one project or resource."
            )
        unknown_caps = [
            f.capability for f in report.capability_findings
            if f.min_purpose == "unknown"
        ]
        if unknown_caps:
            report.warnings.append(
                f"Unrecognised capabilities present: {', '.join(unknown_caps)}. "
                "The auditor cannot vouch for these; review them by hand."
            )

    def _add_recommendations(self, report: AuditReport) -> None:
        if report.verdict == "PASS":
            report.recommendations.append(
                "Credential is scoped within its stated purpose. Re-audit "
                "whenever the purpose or the granted capabilities change."
            )
            return

        if report.excess_capabilities:
            report.recommendations.append(
                f"Remove these capabilities, or raise the stated purpose only "
                f"if the credential genuinely needs them: "
                f"{', '.join(report.excess_capabilities)}."
            )
        if report.destructive_excess:
            report.recommendations.append(
                "If a destructive capability is genuinely required, move it to "
                "a separate, single-purpose credential that is loaded only for "
                "the specific step that needs it -- not carried by the agent's "
                "default credential."
            )
        if report.scope == "all":
            report.recommendations.append(
                "Narrow the scope from 'all' to a single project or resource."
            )
        if report.environment in ("production", "unknown"):
            report.recommendations.append(
                "If the agent's work is not actually on production, point this "
                "credential at a non-production environment."
            )


if __name__ == "__main__":
    # Self-demo. Run: python auditor.py
    auditor = CredentialScopeAuditor()

    print("\n>>> Example 1: the PocketOS-shaped token\n")
    print(auditor.audit({
        "id": "cursor-agent-token",
        "stated_purpose": "read_only",
        "granted_capabilities": ["read", "restart", "delete", "deploy"],
        "environment": "production",
        "scope": "all",
    }))

    print("\n>>> Example 2: a correctly scoped read-only credential\n")
    print(auditor.audit({
        "id": "metrics-reader",
        "stated_purpose": "read_only",
        "granted_capabilities": ["read", "list", "describe"],
        "environment": "production",
        "scope": "single-project",
    }))

    print("\n>>> Example 3: an 'operate' credential that stayed in its lane\n")
    print(auditor.audit({
        "id": "deploy-bot",
        "stated_purpose": "operate",
        "granted_capabilities": ["read", "restart", "redeploy", "deploy"],
        "environment": "staging",
        "scope": "single-project",
    }))
