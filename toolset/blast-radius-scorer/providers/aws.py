"""
AWS provider for the Blast Radius Scorer.
=========================================

Analyses an IAM-style permission description and expands it into concrete
destructive capabilities.

Expected config shape (a description of the policy, NOT live credentials):

    {
        "label": "agent-deploy-role",
        "environment": "production",
        "actions": [                    # IAM-style action strings
            "s3:*",
            "rds:DeleteDBInstance",
            "ec2:DescribeInstances"
        ],
        "resources": ["*"]              # ARNs, or ["*"] for all
    }

Wildcards are expanded: "s3:*" unlocks every known S3 action, "*" unlocks
everything. This mirrors how IAM actually grants access and is where most
over-permissioning hides.

Irreversibility scores are NOT defined here. They come from the
Irreversibility Classifier's pattern files via ScoreBook -- the single
source of truth. This provider decides WHICH actions a policy unlocks; the
score for each one is looked up in one place.
"""

from __future__ import annotations

import fnmatch

from .base import Provider, ProviderReport, Capability
from .scorebook import get_book


class AWSProvider(Provider):
    name = "aws"

    def __init__(self):
        self._book = get_book()
        # The full set of known AWS actions, straight from the source of truth.
        self._known_actions = sorted(self._book.all_cloud(self.name).keys())
        # Service prefixes, for wildcard expansion ("s3:*").
        self._known_services = sorted({a.split(":")[0] for a in self._known_actions})

    def _expand_actions(self, declared: list, report: ProviderReport) -> list:
        """Expand IAM wildcards into concrete known actions."""
        expanded = set()
        for entry in declared:
            entry = entry.strip()
            if entry == "*":
                expanded.update(self._known_actions)
                report.notes.append(
                    "Action '*' grants every known action -- maximum exposure."
                )
                continue
            if entry.endswith(":*"):
                service = entry.split(":")[0]
                matches = [a for a in self._known_actions if a.startswith(service + ":")]
                if matches:
                    expanded.update(matches)
                else:
                    report.notes.append(
                        f"Wildcard '{entry}' matched no known actions for '{service}'."
                    )
                continue
            # Exact or glob match.
            matches = [a for a in self._known_actions if fnmatch.fnmatch(a, entry)]
            if matches:
                expanded.update(matches)
            else:
                # Unknown action -- keep it, it will be scored conservatively.
                expanded.add(entry)
                report.notes.append(
                    f"Action '{entry}' not in the pattern files; scored conservatively."
                )
        return sorted(expanded)

    def analyze(self, config: dict) -> ProviderReport:
        label = self._label(config)
        report = ProviderReport(provider=self.name, credential_label=label)

        environment = (config.get("environment") or "unknown").lower()
        declared = config.get("actions", [])
        resources = config.get("resources", ["*"])

        if not declared:
            report.notes.append("No actions declared; nothing to score.")
            return report

        actions = self._expand_actions(declared, report)
        all_resources = "*" in resources
        scope_desc = (
            "all resources (*)" if all_resources
            else f"resources: {', '.join(resources)}"
        )

        for action in actions:
            # default=True: unknown actions get a conservative score from the
            # source of truth rather than a number invented here.
            entry = self._book.cloud(self.name, action, default=True)
            cap = Capability(
                action=entry.action,
                irreversibility=entry.score,
                resource_scope=scope_desc,
                explanation=entry.explanation,
                reversible=entry.reversible,
                targets_production=(environment in ("production", "unknown")),
                targets_backup=("Snapshot" in action or "DeleteDBInstance" in action),
            )
            report.capabilities.append(cap)

        # AWS-specific warnings.
        if "*" in declared and all_resources:
            report.warnings.append(
                "Policy grants Action '*' on Resource '*'. This is an administrator-"
                "equivalent credential handed to an automated agent. Replace with an "
                "explicit allow-list of the few actions the agent needs."
            )
        for svc_wild in [d for d in declared if d.endswith(":*")]:
            report.warnings.append(
                f"Wildcard '{svc_wild}' grants every action in that service, including "
                "destructive ones. List the specific actions instead."
            )
        if any(c.targets_backup for c in report.capabilities):
            report.warnings.append(
                "Credential can delete database instances or snapshots. Ensure backups "
                "live in a separate account the agent's credential cannot reach."
            )
        if all_resources and any(c.is_destructive for c in report.capabilities):
            report.warnings.append(
                "Destructive actions are scoped to Resource '*'. Narrow them to specific "
                "ARNs so a mistaken call cannot hit production by accident."
            )

        return report
