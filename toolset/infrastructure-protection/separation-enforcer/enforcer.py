"""
Separation Enforcer
===================

The enforcement counterpart to the Colocated Risk Scanner.

The scanner *describes* what is colocated. The enforcer takes a
machine-readable separation policy (a ruleset) and turns it into a
pass/fail gate: it checks an infrastructure config against the policy and
exits non-zero if any blocking rule is violated. Drop it in CI and a
dangerous arrangement stops the pipeline before an agent is ever deployed
on top of it.

Rules live in rulesets/default_rules.json. Each rule has an `enforce`
level:

    block  -> a violation fails the whole check (exit code 1)
    warn   -> a violation is reported but the check still passes

Teams are expected to copy the default ruleset, tighten or relax levels,
and version it alongside their infrastructure.

------------------------------------------------------------------------
INPUT FORMAT
------------------------------------------------------------------------
Same infrastructure description shape used by the Colocated Risk Scanner:

    {
      "resources": [
        {"id": "...", "roles": [...], "volume": "...", "account": "...", ...}
      ],
      "credentials": [
        {"id": "...", "roles": [...], "capabilities": [...], "scope": "..."}
      ]
    }

------------------------------------------------------------------------
USAGE
------------------------------------------------------------------------
As a library:

    from enforcer import SeparationEnforcer

    enforcer = SeparationEnforcer()                 # uses default ruleset
    result = enforcer.enforce(infrastructure)
    print(result)
    if not result.passed:
        ...

As a CLI (the CI use case):

    python enforcer.py infra.json
    python enforcer.py infra.json --ruleset custom_rules.json
    echo $?        # 0 = passed, 1 = blocking violation, 2 = bad input
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


DEFAULT_RULESET = Path(__file__).parent / "rulesets" / "default_rules.json"

# Process exit codes.
EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_BAD_INPUT = 2


@dataclass
class Violation:
    """One rule violated by the infrastructure config."""

    rule_id: str
    name: str
    enforce: str                       # "block" | "warn"
    rationale: str
    remediation: str
    detail: str                        # what specifically tripped the rule
    involved: list = field(default_factory=list)

    @property
    def blocking(self) -> bool:
        return self.enforce == "block"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["blocking"] = self.blocking
        return d


@dataclass
class EnforcementResult:
    """The outcome of enforcing a ruleset against an infrastructure config."""

    violations: list = field(default_factory=list)
    rules_checked: int = 0
    resources_scanned: int = 0
    credentials_scanned: int = 0

    @property
    def blocking_violations(self) -> list:
        return [v for v in self.violations if v.blocking]

    @property
    def warnings(self) -> list:
        return [v for v in self.violations if not v.blocking]

    @property
    def passed(self) -> bool:
        """The gate passes if there are no BLOCKING violations."""
        return len(self.blocking_violations) == 0

    @property
    def exit_code(self) -> int:
        return EXIT_OK if self.passed else EXIT_VIOLATION

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "exit_code": self.exit_code,
            "rules_checked": self.rules_checked,
            "resources_scanned": self.resources_scanned,
            "credentials_scanned": self.credentials_scanned,
            "blocking_violations": [v.to_dict() for v in self.blocking_violations],
            "warnings": [v.to_dict() for v in self.warnings],
        }

    def __str__(self) -> str:
        lines = [
            "=" * 64,
            "  SEPARATION ENFORCEMENT",
            "=" * 64,
            f"  Rules checked:        {self.rules_checked}",
            f"  Resources scanned:    {self.resources_scanned}",
            f"  Credentials scanned:  {self.credentials_scanned}",
            f"  Blocking violations:  {len(self.blocking_violations)}",
            f"  Warnings:             {len(self.warnings)}",
            f"  RESULT:               {'PASS' if self.passed else 'FAIL'}"
            f"  (exit {self.exit_code})",
        ]

        if self.blocking_violations:
            lines.append("")
            lines.append("  BLOCKING VIOLATIONS")
            lines.append("  " + "-" * 60)
            for v in self.blocking_violations:
                lines.append(f"  [BLOCK] {v.rule_id}  {v.name}")
                lines.append(f"    detail:       {v.detail}")
                lines.append(f"    involves:     {', '.join(v.involved)}")
                lines.append(f"    rationale:    {v.rationale}")
                lines.append(f"    remediation:  {v.remediation}")
                lines.append("")

        if self.warnings:
            lines.append("  WARNINGS")
            lines.append("  " + "-" * 60)
            for v in self.warnings:
                lines.append(f"  [warn]  {v.rule_id}  {v.name}")
                lines.append(f"    detail:       {v.detail}")
                lines.append(f"    remediation:  {v.remediation}")
                lines.append("")

        if not self.violations:
            lines.append("")
            lines.append("  No violations. Infrastructure satisfies the separation policy.")

        lines.append("=" * 64)
        return "\n".join(lines)


class SeparationEnforcer:
    """Enforces a separation ruleset against an infrastructure config."""

    def __init__(self, ruleset_path: Path = DEFAULT_RULESET):
        with open(ruleset_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.ruleset_name = data.get("_meta", {}).get("name", "unnamed-ruleset")
        self.rules = data["rules"]

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def enforce(self, infrastructure: dict) -> EnforcementResult:
        resources = infrastructure.get("resources", [])
        credentials = infrastructure.get("credentials", [])

        result = EnforcementResult(
            rules_checked=len(self.rules),
            resources_scanned=len(resources),
            credentials_scanned=len(credentials),
        )

        for rule in self.rules:
            check = rule["check"]
            ctype = check["type"]
            handler = self._HANDLERS.get(ctype)
            if handler is None:
                # Forward-compatible: unknown check types are skipped.
                continue
            violations = handler(self, rule, resources, credentials)
            result.violations.extend(violations)

        return result

    # ------------------------------------------------------------------ #
    # Check handlers
    # ------------------------------------------------------------------ #
    def _make_violation(self, rule, detail, involved) -> Violation:
        return Violation(
            rule_id=rule["id"],
            name=rule["name"],
            enforce=rule["enforce"],
            rationale=rule["rationale"],
            remediation=rule["remediation"],
            detail=detail,
            involved=involved,
        )

    def _check_no_shared_boundary(self, rule, resources, credentials) -> list:
        """Violation if a role_a item and a role_b item share a boundary value."""
        check = rule["check"]
        boundary = check["boundary"]
        role_a = check["role_a"]
        role_b = check["role_b"]

        items = list(resources) + list(credentials)
        violations = []
        seen = set()

        for i, item_a in enumerate(items):
            for item_b in items[i + 1:]:
                roles_a = set(item_a.get("roles", []))
                roles_b = set(item_b.get("roles", []))
                covers = (
                    (role_a in roles_a and role_b in roles_b)
                    or (role_a in roles_b and role_b in roles_a)
                )
                if not covers:
                    continue
                va, vb = item_a.get(boundary), item_b.get(boundary)
                if va is None or vb is None or va != vb:
                    continue
                pair = tuple(sorted([item_a.get("id", "?"), item_b.get("id", "?")]))
                if pair in seen:
                    continue
                seen.add(pair)
                violations.append(
                    self._make_violation(
                        rule,
                        detail=f"{role_a} and {role_b} both on {boundary} '{va}'",
                        involved=list(pair),
                    )
                )
        return violations

    def _check_no_role_combo_on_credential(self, rule, resources, credentials) -> list:
        """Violation if a single credential carries all of the named roles."""
        required = set(rule["check"]["roles"])
        violations = []
        for cred in credentials:
            if required.issubset(set(cred.get("roles", []))):
                violations.append(
                    self._make_violation(
                        rule,
                        detail=f"credential carries roles {sorted(required)} together",
                        involved=[cred.get("id", "?")],
                    )
                )
        return violations

    def _check_no_capability_on_role(self, rule, resources, credentials) -> list:
        """Violation if a credential with the named role has any forbidden capability."""
        check = rule["check"]
        target_role = check["role"]
        forbidden = set(check["forbidden_capabilities"])
        violations = []
        for cred in credentials:
            if target_role not in set(cred.get("roles", [])):
                continue
            present = forbidden.intersection(set(cred.get("capabilities", [])))
            if present:
                violations.append(
                    self._make_violation(
                        rule,
                        detail=(
                            f"credential with role '{target_role}' has forbidden "
                            f"capabilities: {sorted(present)}"
                        ),
                        involved=[cred.get("id", "?")],
                    )
                )
        return violations

    def _check_no_capability_at_scope(self, rule, resources, credentials) -> list:
        """Violation if a credential has a forbidden capability at a forbidden scope."""
        check = rule["check"]
        forbidden = set(check["forbidden_capabilities"])
        bad_scope = check["forbidden_scope"]
        violations = []
        for cred in credentials:
            if cred.get("scope") != bad_scope:
                continue
            present = forbidden.intersection(set(cred.get("capabilities", [])))
            if present:
                violations.append(
                    self._make_violation(
                        rule,
                        detail=(
                            f"credential at scope '{bad_scope}' has forbidden "
                            f"capabilities: {sorted(present)}"
                        ),
                        involved=[cred.get("id", "?")],
                    )
                )
        return violations

    def _check_role_requires_counterpart(self, rule, resources, credentials) -> list:
        """
        Violation if any resource has `role` but NO resource anywhere has
        `counterpart_role`. (A coarse check -- it does not match counterparts
        one-to-one, only confirms at least one exists.)
        """
        check = rule["check"]
        role = check["role"]
        counterpart = check["counterpart_role"]

        has_role = [r for r in resources if role in set(r.get("roles", []))]
        has_counterpart = any(
            counterpart in set(r.get("roles", [])) for r in resources
        )
        if has_role and not has_counterpart:
            return [
                self._make_violation(
                    rule,
                    detail=(
                        f"{len(has_role)} resource(s) with role '{role}' but no "
                        f"resource declares '{counterpart}'"
                    ),
                    involved=[r.get("id", "?") for r in has_role],
                )
            ]
        return []

    # Registry of check type -> handler method.
    _HANDLERS = {
        "no_shared_boundary": _check_no_shared_boundary,
        "no_role_combo_on_credential": _check_no_role_combo_on_credential,
        "no_capability_on_role": _check_no_capability_on_role,
        "no_capability_at_scope": _check_no_capability_at_scope,
        "role_requires_counterpart": _check_role_requires_counterpart,
    }


# ---------------------------------------------------------------------- #
# CLI entry point -- the CI use case
# ---------------------------------------------------------------------- #
def _main(argv: list) -> int:
    args = [a for a in argv if not a.startswith("--")]
    flags = [a for a in argv if a.startswith("--")]

    if not args:
        print("usage: python enforcer.py <infra.json> [--ruleset <rules.json>] [--json]")
        return EXIT_BAD_INPUT

    infra_path = Path(args[0])
    if not infra_path.is_file():
        print(f"error: infrastructure file not found: {infra_path}")
        return EXIT_BAD_INPUT

    ruleset_path = DEFAULT_RULESET
    for i, f in enumerate(flags):
        if f == "--ruleset" and i + 1 < len(flags):
            pass  # handled below
    # --ruleset takes the next positional-style token; parse simply.
    if "--ruleset" in argv:
        idx = argv.index("--ruleset")
        if idx + 1 < len(argv):
            ruleset_path = Path(argv[idx + 1])
            if not ruleset_path.is_file():
                print(f"error: ruleset file not found: {ruleset_path}")
                return EXIT_BAD_INPUT

    try:
        with open(infra_path, "r", encoding="utf-8") as fh:
            infrastructure = json.load(fh)
    except json.JSONDecodeError as e:
        print(f"error: could not parse {infra_path}: {e}")
        return EXIT_BAD_INPUT

    enforcer = SeparationEnforcer(ruleset_path)
    result = enforcer.enforce(infrastructure)

    if "--json" in argv:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result)

    return result.exit_code


if __name__ == "__main__":
    # If run with no args, show a self-demo instead of the usage error.
    if len(sys.argv) == 1:
        enforcer = SeparationEnforcer()

        print("\n>>> Example 1: the PocketOS arrangement\n")
        pocketos = {
            "resources": [
                {"id": "pg-main", "roles": ["production_data"],
                 "volume": "vol-01", "account": "acct-prod"},
                {"id": "pg-backups", "roles": ["backup"],
                 "volume": "vol-01", "account": "acct-prod"},
            ],
            "credentials": [
                {"id": "agent-token",
                 "roles": ["production_access", "staging_access", "agent_default", "read_access", "destructive_access"],
                 "capabilities": ["read", "deploy", "delete"],
                 "scope": "all"},
            ],
        }
        result = enforcer.enforce(pocketos)
        print(result)
        print(f"\n  -> process would exit {result.exit_code}\n")

        print("\n>>> Example 2: a separated, policy-compliant setup\n")
        compliant = {
            "resources": [
                {"id": "pg-main", "roles": ["production_data"],
                 "volume": "vol-prod", "account": "acct-prod"},
                {"id": "pg-backups", "roles": ["backup"],
                 "volume": "vol-backup", "account": "acct-backup"},
            ],
            "credentials": [
                {"id": "agent-default", "roles": ["agent_default", "read_access", "staging_access"],
                 "capabilities": ["read", "deploy"], "scope": "single-project"},
                {"id": "destructive-cred", "roles": ["destructive_access", "production_access"],
                 "capabilities": ["delete"], "scope": "single-resource"},
            ],
        }
        result = enforcer.enforce(compliant)
        print(result)
        print(f"\n  -> process would exit {result.exit_code}\n")
        sys.exit(EXIT_OK)

    sys.exit(_main(sys.argv[1:]))
