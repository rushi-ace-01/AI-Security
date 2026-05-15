"""
Railway provider for the Blast Radius Scorer.
=============================================

Railway is the platform involved in the PocketOS incident, so it is the
reference implementation.

Expected config shape (a description of the token's scope, NOT the token):

    {
        "label": "ci-deploy-token",
        "scope": "full",                # "full" | "read_only" | "custom"
        "environment": "production",    # "production" | "staging" | "shared" | "unknown"
        "projects": ["pocketos-api"],   # or ["*"] for all projects
        "custom_permissions": [         # only consulted when scope == "custom"
            "deployment.create",
            "service.get"
        ]
    }

Irreversibility scores are NOT defined here. They are read from the
Irreversibility Classifier's pattern files via ScoreBook -- the single
source of truth. This provider only decides WHICH Railway operations a
given scope unlocks; how irreversible each one is comes from one place.
"""

from __future__ import annotations

from .base import Provider, ProviderReport, Capability
from .scorebook import get_book


# Which Railway operations each scope level unlocks. These are the canonical
# match keys from the classifier's railway.json pattern file. The scores for
# them are looked up at runtime, not stored here.
ALL_RAILWAY_OPS = [
    "project.delete",
    "volume.delete",
    "database.delete",
    "service.delete",
    "variable.delete",
    "deployment.delete",
    "variable.upsert",
    "deployment.create",
    "service.get",
    "project.list",
]


class RailwayProvider(Provider):
    name = "railway"

    def __init__(self):
        self._book = get_book()
        # Read-only ops are those the source of truth scores at 0.
        self._read_only_ops = [
            op for op in ALL_RAILWAY_OPS
            if self._book.cloud(self.name, op).score == 0
        ]

    def analyze(self, config: dict) -> ProviderReport:
        label = self._label(config)
        report = ProviderReport(provider=self.name, credential_label=label)

        scope = (config.get("scope") or "full").lower()
        environment = (config.get("environment") or "unknown").lower()
        projects = config.get("projects", ["*"])

        # Guard: did someone paste a real token into a scope field?
        for key in ("scope", "environment"):
            if self._looks_like_secret(str(config.get(key, ""))):
                report.warnings.append(
                    f"Value in '{key}' looks like a real secret. "
                    "This tool expects a scope DESCRIPTION, not the token itself. "
                    "Nothing was stored."
                )

        # Resolve which operations this credential unlocks.
        if scope == "read_only":
            ops = self._read_only_ops
        elif scope == "custom":
            ops = config.get("custom_permissions", [])
            unknown = [
                o for o in ops
                if self._book.cloud(self.name, o) is None
            ]
            if unknown:
                report.notes.append(
                    f"Custom permissions not in the pattern files, scored "
                    f"conservatively: {unknown}"
                )
        else:  # "full" or anything unrecognised -> assume full (safe-pessimistic)
            ops = ALL_RAILWAY_OPS
            if scope != "full":
                report.notes.append(
                    f"Scope '{scope}' not recognised; treated as 'full' "
                    "(pessimistic default)."
                )

        all_projects = "*" in projects
        scope_desc = (
            "all projects in account" if all_projects
            else f"projects: {', '.join(projects)}"
        )

        for op in ops:
            # default=True: an unrecognised custom permission still gets a
            # conservative score rather than being silently dropped.
            entry = self._book.cloud(self.name, op, default=True)
            cap = Capability(
                action=f"railway:{entry.action}",
                irreversibility=entry.score,
                resource_scope=scope_desc,
                explanation=entry.explanation,
                reversible=entry.reversible,
                targets_production=(environment in ("production", "shared", "unknown")),
                targets_backup=("volume" in op or "database" in op),
            )
            report.capabilities.append(cap)

        # Railway-specific warnings.
        if scope == "full" and all_projects:
            report.warnings.append(
                "Token has FULL scope across ALL projects. A single mistaken call "
                "can destroy unrelated projects. Scope it to one project and the "
                "minimum permission set the agent actually needs."
            )
        if environment in ("shared", "unknown"):
            report.warnings.append(
                f"Token environment is '{environment}'. It may reach production. "
                "Pin it to a named non-production environment if the agent does "
                "not need prod."
            )
        if any(c.action == "railway:volume.delete" for c in report.capabilities):
            report.warnings.append(
                "Token can delete storage volumes. If production data and backups "
                "share a volume, one call destroys both -- this is exactly how the "
                "PocketOS outage happened. Verify volume separation and remove this "
                "permission unless the agent genuinely needs it."
            )

        return report
