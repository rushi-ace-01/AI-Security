"""
Colocated Risk Scanner
======================

Scans an infrastructure description and flags where things that should be
isolated from each other are sharing the same boundary -- the same volume,
account, token, project, or region.

This targets the PocketOS failure mode directly. In that incident, production
data and its backups lived on the same Railway volume. One destructive API
call took out both. No tool was watching for that arrangement. This one is.

It is static analysis: you describe your infrastructure (or generate the
description from your IaC / cloud config), and the scanner checks it against
a ruleset. Nothing is executed and no live credentials are needed.

------------------------------------------------------------------------
INPUT FORMAT
------------------------------------------------------------------------
An "infrastructure description" is a dict with two keys: `resources` and
(optionally) `credentials`.

    {
      "resources": [
        {
          "id": "pg-main",
          "roles": ["production_data"],
          "volume": "vol-01",
          "account": "acct-prod",
          "project": "pocketos",
          "region": "us-east-1"
        },
        {
          "id": "pg-backups",
          "roles": ["backup", "snapshot"],
          "volume": "vol-01",          # <-- same volume as production: COLO-001
          "account": "acct-prod",
          "project": "pocketos",
          "region": "us-east-1"
        }
      ],
      "credentials": [
        {
          "id": "agent-token",
          "roles": ["production_access", "staging_access", "destructive_access"],
          "capabilities": ["deploy", "delete"],
          "scope": "all"
        }
      ]
    }

`roles` is the important field. A resource or credential can carry several
roles. The scanner looks for pairs of roles that the ruleset says must never
share a boundary.

Recognised resource roles:
    production_data, backup, snapshot
Recognised credential roles:
    production_access, staging_access, read_access, destructive_access

A boundary value of None means "not specified" and is never treated as a
match (two unspecified volumes are not "the same volume").
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


RULES_PATH = Path(__file__).parent / "rules" / "separation_rules.json"

SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


@dataclass
class Finding:
    """One detected colocation problem."""

    rule_id: str
    name: str
    severity: str
    why: str
    fix: str
    involved: list = field(default_factory=list)   # ids of the resources/credentials involved
    boundary: str = ""                             # the shared boundary, e.g. "volume: vol-01"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScanReport:
    """The full result of scanning one infrastructure description."""

    findings: list = field(default_factory=list)
    resources_scanned: int = 0
    credentials_scanned: int = 0

    @property
    def passed(self) -> bool:
        """True if nothing of medium severity or above was found."""
        return not any(
            SEVERITY_ORDER[f.severity] >= SEVERITY_ORDER["medium"] for f in self.findings
        )

    @property
    def worst_severity(self) -> Optional[str]:
        if not self.findings:
            return None
        return max(self.findings, key=lambda f: SEVERITY_ORDER[f.severity]).severity

    def count(self, severity: str) -> int:
        return sum(1 for f in self.findings if f.severity == severity)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "worst_severity": self.worst_severity,
            "resources_scanned": self.resources_scanned,
            "credentials_scanned": self.credentials_scanned,
            "findings": [f.to_dict() for f in self.findings],
        }

    def __str__(self) -> str:
        lines = [
            "=" * 64,
            "  COLOCATED RISK SCAN",
            "=" * 64,
            f"  Resources scanned:    {self.resources_scanned}",
            f"  Credentials scanned:  {self.credentials_scanned}",
            f"  Result:               {'PASS' if self.passed else 'FAIL'}"
            + (f"  (worst: {self.worst_severity.upper()})" if self.findings else ""),
        ]
        if not self.findings:
            lines.append("")
            lines.append("  No colocation risks found against the current ruleset.")
            lines.append("=" * 64)
            return "\n".join(lines)

        # Findings, worst first.
        ordered = sorted(
            self.findings, key=lambda f: SEVERITY_ORDER[f.severity], reverse=True
        )
        for f in ordered:
            lines.append("")
            lines.append(f"  [{f.severity.upper()}] {f.rule_id}  {f.name}")
            lines.append(f"    boundary:  {f.boundary}")
            lines.append(f"    involves:  {', '.join(f.involved)}")
            lines.append(f"    why:       {f.why}")
            lines.append(f"    fix:       {f.fix}")
        lines.append("=" * 64)
        return "\n".join(lines)


class ColocatedRiskScanner:
    """Checks an infrastructure description against a colocation ruleset."""

    def __init__(self, rules_path: Path = RULES_PATH):
        with open(rules_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.rules = data["rules"]

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def scan(self, infrastructure: dict) -> ScanReport:
        resources = infrastructure.get("resources", [])
        credentials = infrastructure.get("credentials", [])

        report = ScanReport(
            resources_scanned=len(resources),
            credentials_scanned=len(credentials),
        )

        for rule in self.rules:
            detect = rule["detect"]
            dtype = detect["type"]
            if dtype == "shared_boundary":
                report.findings.extend(
                    self._check_shared_boundary(rule, resources, credentials)
                )
            elif dtype == "capability_combo":
                report.findings.extend(
                    self._check_capability_combo(rule, credentials)
                )
            # Unknown detect types are skipped rather than crashing -- keeps
            # the scanner forward-compatible with newer rule files.

        return report

    # ------------------------------------------------------------------ #
    # Detectors
    # ------------------------------------------------------------------ #
    def _check_shared_boundary(self, rule, resources, credentials) -> list:
        """
        Fire when two items, one carrying role_a and one carrying role_b,
        share the same non-null value for the given boundary field.
        """
        detect = rule["detect"]
        boundary = detect["boundary"]
        role_a = detect["role_a"]
        role_b = detect["role_b"]

        # Boundary fields can live on resources or credentials; check both pools.
        items = []
        for r in resources:
            items.append(("resource", r))
        for c in credentials:
            items.append(("credential", c))

        findings = []
        seen_pairs = set()

        for i, (_, item_a) in enumerate(items):
            for _, item_b in items[i + 1:]:
                roles_a = set(item_a.get("roles", []))
                roles_b = set(item_b.get("roles", []))

                # One item must cover role_a, the other role_b. Try both
                # directions so order in the list does not matter.
                covers = (
                    (role_a in roles_a and role_b in roles_b)
                    or (role_a in roles_b and role_b in roles_a)
                )
                if not covers:
                    continue

                val_a = item_a.get(boundary)
                val_b = item_b.get(boundary)
                if val_a is None or val_b is None:
                    continue
                if val_a != val_b:
                    continue

                pair_key = tuple(sorted([item_a.get("id", "?"), item_b.get("id", "?")]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                findings.append(
                    Finding(
                        rule_id=rule["id"],
                        name=rule["name"],
                        severity=rule["severity"],
                        why=rule["why"],
                        fix=rule["fix"],
                        involved=list(pair_key),
                        boundary=f"{boundary}: {val_a}",
                    )
                )
        return findings

    def _check_capability_combo(self, rule, credentials) -> list:
        """
        Fire when a single credential carries all of a set of capabilities
        at a given scope (e.g. both 'deploy' and 'delete' at scope 'all').
        """
        detect = rule["detect"]
        required = set(detect["capabilities"])
        required_scope = detect.get("scope")

        findings = []
        for cred in credentials:
            caps = set(cred.get("capabilities", []))
            if not required.issubset(caps):
                continue
            if required_scope is not None and cred.get("scope") != required_scope:
                continue
            findings.append(
                Finding(
                    rule_id=rule["id"],
                    name=rule["name"],
                    severity=rule["severity"],
                    why=rule["why"],
                    fix=rule["fix"],
                    involved=[cred.get("id", "?")],
                    boundary=f"{detect['boundary']}: {cred.get('id', '?')}"
                    + (f" (scope: {required_scope})" if required_scope else ""),
                )
            )
        return findings


if __name__ == "__main__":
    # Self-demo. Run: python scanner.py
    scanner = ColocatedRiskScanner()

    print("\n>>> Example 1: the PocketOS arrangement\n")
    pocketos = {
        "resources": [
            {
                "id": "pg-main", "roles": ["production_data"],
                "volume": "vol-01", "account": "acct-prod",
                "project": "pocketos", "region": "us-east-1",
            },
            {
                "id": "pg-backups", "roles": ["backup", "snapshot"],
                "volume": "vol-01", "account": "acct-prod",
                "project": "pocketos", "region": "us-east-1",
            },
        ],
        "credentials": [
            {
                "id": "agent-token",
                "roles": ["production_access", "staging_access", "destructive_access", "read_access"],
                "capabilities": ["deploy", "delete"],
                "scope": "all",
            }
        ],
    }
    print(scanner.scan(pocketos))

    print("\n>>> Example 2: a properly separated setup\n")
    safe = {
        "resources": [
            {
                "id": "pg-main", "roles": ["production_data"],
                "volume": "vol-prod", "account": "acct-prod",
                "project": "app-prod", "region": "us-east-1",
            },
            {
                "id": "pg-backups", "roles": ["backup", "snapshot"],
                "volume": "vol-backup", "account": "acct-backup",
                "project": "app-backup", "region": "us-west-2",
            },
        ],
        "credentials": [
            {
                "id": "agent-read", "roles": ["read_access", "staging_access"],
                "capabilities": ["deploy"], "scope": "single-project",
            },
            {
                "id": "agent-destructive", "roles": ["destructive_access", "production_access"],
                "capabilities": ["delete"], "scope": "single-project",
            },
        ],
    }
    print(scanner.scan(safe))
