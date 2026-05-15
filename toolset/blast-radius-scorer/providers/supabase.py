"""
Supabase provider for the Blast Radius Scorer.
==============================================

Analyses a Supabase access description and expands it into concrete
destructive capabilities.

Supabase credentials come in distinct tiers, and the tier matters more than
anything else for blast radius:

    - "anon"            : public client key, RLS-limited
    - "service_role"    : bypasses Row Level Security entirely -- full data access
    - "management"      : Management API token -- can delete whole projects
    - "db_connection"   : direct Postgres connection string -- full SQL

Expected config shape:

    {
        "label": "agent-db-key",
        "key_type": "service_role",     # anon | service_role | management | db_connection
        "environment": "production",
        "project_ref": "abcdefgh"       # optional, informational
    }

Irreversibility scores are NOT defined here. The mapping from key type to
the set of operations it unlocks is provider logic and lives here; the
score for each operation is read from the Irreversibility Classifier's
pattern files via ScoreBook -- the single source of truth.
"""

from __future__ import annotations

from .base import Provider, ProviderReport, Capability
from .scorebook import get_book


# Which operations each key type unlocks. These are the canonical match keys
# from the classifier's supabase.json pattern file. No scores here -- only
# the question of WHICH operations a key tier can perform.
KEY_TYPE_OPERATIONS = {
    "anon": [
        "database.query.select",
        "storage.object.read",
    ],
    "service_role": [
        "database.query.select",
        "database.query.insert",
        "database.query.update",
        "database.query.delete",
        "storage.object.delete",
        "auth.user.delete",
    ],
    "management": [
        "project.delete",
        "storage.bucket.delete",
        "secrets.delete",
        "function.deploy",
        "project.get",
    ],
    "db_connection": [
        "database.query.select",
        "database.query.update",
        "database.query.delete",
        "database.query.drop",
        "database.query.truncate",
    ],
}


class SupabaseProvider(Provider):
    name = "supabase"

    def __init__(self):
        self._book = get_book()

    def analyze(self, config: dict) -> ProviderReport:
        label = self._label(config)
        report = ProviderReport(provider=self.name, credential_label=label)

        key_type = (config.get("key_type") or "").lower()
        environment = (config.get("environment") or "unknown").lower()

        if self._looks_like_secret(config.get("key_type", "")):
            report.warnings.append(
                "Value in 'key_type' looks like a real key. Expected one of: "
                "anon, service_role, management, db_connection. Nothing was stored."
            )
            return report

        operations = KEY_TYPE_OPERATIONS.get(key_type)
        if operations is None:
            report.notes.append(
                f"key_type '{key_type}' not recognised. Expected: "
                "anon, service_role, management, db_connection."
            )
            return report

        is_prod = environment in ("production", "unknown")
        project_ref = config.get("project_ref", "unspecified")

        for op in operations:
            # default=True: if an operation is somehow not in the pattern
            # files, it still gets a conservative score from the source of
            # truth rather than a number invented here.
            entry = self._book.cloud(self.name, op, default=True)
            cap = Capability(
                action=f"supabase:{entry.action}",
                irreversibility=entry.score,
                resource_scope=f"entire project ({project_ref})",
                explanation=entry.explanation,
                reversible=entry.reversible,
                targets_production=is_prod,
                targets_backup=False,  # Supabase backups are managed separately
            )
            report.capabilities.append(cap)

        # Supabase-specific warnings.
        if key_type == "service_role":
            report.warnings.append(
                "This is a service_role key. It bypasses Row Level Security completely -- "
                "every table is fully readable and writable. Never give this to an agent "
                "that only needs scoped access. Use an anon key with RLS policies instead."
            )
        if key_type == "management":
            report.warnings.append(
                "This is a Management API token. It can DELETE THE ENTIRE PROJECT in one "
                "call. An autonomous agent almost never needs project-management scope. "
                "Restrict it to a human-operated context."
            )
        if key_type == "db_connection":
            report.warnings.append(
                "This is a direct Postgres connection string. It allows arbitrary SQL "
                "including DROP and TRUNCATE. Prefer the scoped REST API over raw DB access "
                "for agents, and keep DDL permissions out of the agent's role."
            )
        if is_prod and key_type in ("service_role", "management", "db_connection"):
            report.warnings.append(
                f"A high-privilege key is pointed at '{environment}'. If the agent only "
                "needs to develop or test, point it at a separate non-production project."
            )

        return report
