"""
scores.py -- the single source of truth for irreversibility scores.
====================================================================

The Irreversibility Classifier's pattern files (patterns/*.json) define the
canonical irreversibility score for every action this project knows about.
Other tools in the toolset -- the Blast Radius Scorer especially -- need
those same scores. They must NOT keep their own copies; that is how the
numbers drift apart.

This module exposes the classifier's pattern data as a plain, importable
lookup so every other tool reads from one place.

Usage from another tool:

    from scores import ScoreBook

    book = ScoreBook()                       # loads the pattern files once

    book.cloud("railway", "volume.delete")   # -> ScoreEntry(score=10, ...)
    book.cloud("aws", "s3:DeleteBucket")     # -> ScoreEntry(score=10, ...)
    book.sql("DROP")                         # -> ScoreEntry(score=10, ...)
    book.http("DELETE")                      # -> ScoreEntry(score=9,  ...)
    book.shell("rm")                         # -> ScoreEntry(score=9,  ...)

    # When an action is not in the pattern files:
    book.cloud("railway", "made.up")         # -> None
    book.cloud("railway", "made.up", default=True)  # -> conservative ScoreEntry

Aliases declared in the pattern files are resolved automatically, so
book.cloud("railway", "deleteVolume") and book.cloud("railway", "volume.delete")
return the same entry.

If a tool needs a score for an action that genuinely is not in the pattern
files, the correct fix is to ADD A PATTERN to the relevant JSON file -- not
to hardcode a number in the consuming tool. That keeps this module the only
source of truth.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


PATTERNS_DIR = Path(__file__).parent / "patterns"
CLOUD_API_DIR = PATTERNS_DIR / "cloud_apis"

# Score returned for an unrecognised action when default=True is requested.
# Matches IrreversibilityClassifier.UNKNOWN_SCORE -- deliberately conservative.
UNKNOWN_SCORE = 6


@dataclass(frozen=True)
class ScoreEntry:
    """A single canonical score, as read from the pattern files."""

    action: str                  # the canonical match key, e.g. "volume.delete"
    score: int                   # 0-10 irreversibility
    reversible: bool
    explanation: str
    safer_alternative: Optional[str] = None
    provider: Optional[str] = None       # set for cloud_api entries
    recognized: bool = True              # False when this is a default fallback

    @property
    def is_destructive(self) -> bool:
        return self.score >= 6

    @property
    def is_irreversible(self) -> bool:
        return self.score >= 8


class ScoreBook:
    """
    A read-only lookup over the classifier's pattern files.

    Construct it once and share it. It does no classification logic of its
    own -- it just exposes the canonical numbers so nothing else has to
    hardcode them.
    """

    def __init__(self, patterns_dir: Path = PATTERNS_DIR):
        self.patterns_dir = Path(patterns_dir)
        self._http: dict = {}
        self._sql: dict = {}
        self._shell: dict = {}
        self._cloud: dict = {}        # provider -> {key_or_alias: ScoreEntry}
        self._load()

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #
    def _read(self, path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _entry_from_pattern(self, p: dict, provider: Optional[str] = None) -> ScoreEntry:
        return ScoreEntry(
            action=p["match"],
            score=p["score"],
            reversible=p["reversible"],
            explanation=p["explanation"],
            safer_alternative=p.get("safer_alternative"),
            provider=provider,
        )

    def _load(self) -> None:
        # HTTP, SQL, shell: keyed by the uppercase (http/sql) or lowercase
        # (shell) match string, consistent with the classifier.
        http = self._read(self.patterns_dir / "http_methods.json")
        for p in http["patterns"]:
            self._http[p["match"].upper()] = self._entry_from_pattern(p)

        sql = self._read(self.patterns_dir / "sql_operations.json")
        for p in sql["patterns"]:
            self._sql[p["match"].upper()] = self._entry_from_pattern(p)

        shell = self._read(self.patterns_dir / "shell_commands.json")
        for p in shell["patterns"]:
            self._shell[p["match"].lower()] = self._entry_from_pattern(p)

        # Cloud APIs: one dict per provider, with every alias also pointing
        # at the same entry so callers can use whichever name they have.
        if CLOUD_API_DIR.is_dir():
            for fp in sorted(CLOUD_API_DIR.glob("*.json")):
                data = self._read(fp)
                provider = data["provider"].lower()
                table: dict = {}
                for p in data["patterns"]:
                    entry = self._entry_from_pattern(p, provider=provider)
                    table[p["match"].lower()] = entry
                    for alias in p.get("aliases", []):
                        table[alias.lower()] = entry
                self._cloud[provider] = table

    # ------------------------------------------------------------------ #
    # Lookups
    # ------------------------------------------------------------------ #
    @property
    def providers(self) -> list:
        return sorted(self._cloud.keys())

    def cloud(
        self, provider: str, action: str, default: bool = False
    ) -> Optional[ScoreEntry]:
        """
        Look up a cloud API action for a provider.

        Returns the ScoreEntry, or None if the action is unknown. Pass
        default=True to get a conservative fallback entry instead of None.
        Raises ValueError if the provider itself is unknown.
        """
        provider = (provider or "").lower()
        table = self._cloud.get(provider)
        if table is None:
            raise ValueError(
                f"Unknown provider '{provider}'. Known: {', '.join(self.providers)}"
            )
        entry = table.get(action.lower())
        if entry is not None:
            return entry
        return self._default(action, provider) if default else None

    def sql(self, keyword: str, default: bool = False) -> Optional[ScoreEntry]:
        """Look up a SQL operation by its leading keyword (e.g. 'DROP')."""
        entry = self._sql.get(keyword.strip().upper())
        if entry is not None:
            return entry
        return self._default(keyword) if default else None

    def http(self, method: str, default: bool = False) -> Optional[ScoreEntry]:
        """Look up an HTTP method (e.g. 'DELETE')."""
        entry = self._http.get(method.strip().upper())
        if entry is not None:
            return entry
        return self._default(method) if default else None

    def shell(self, command: str, default: bool = False) -> Optional[ScoreEntry]:
        """Look up a shell command by name (e.g. 'rm')."""
        entry = self._shell.get(command.strip().lower())
        if entry is not None:
            return entry
        return self._default(command) if default else None

    # ------------------------------------------------------------------ #
    # Bulk access -- handy for tools that iterate over everything
    # ------------------------------------------------------------------ #
    def all_cloud(self, provider: str) -> dict:
        """
        Every canonical entry for a provider, keyed by canonical match string
        only (aliases excluded). Returns a fresh dict; safe to iterate.
        """
        provider = (provider or "").lower()
        table = self._cloud.get(provider)
        if table is None:
            raise ValueError(
                f"Unknown provider '{provider}'. Known: {', '.join(self.providers)}"
            )
        # Aliases and canonical keys share entry objects; dedupe by identity.
        seen = {}
        for entry in table.values():
            seen[entry.action] = entry
        return dict(seen)

    # ------------------------------------------------------------------ #
    # Fallback
    # ------------------------------------------------------------------ #
    def _default(self, action: str, provider: Optional[str] = None) -> ScoreEntry:
        return ScoreEntry(
            action=action,
            score=UNKNOWN_SCORE,
            reversible=False,
            explanation=(
                "Action is not in the irreversibility pattern files. Returning "
                "a conservative default. The correct fix is to add a pattern for "
                "this action to the relevant patterns/*.json file."
            ),
            safer_alternative="Treat as potentially destructive until a pattern is added.",
            provider=provider,
            recognized=False,
        )


# A module-level shared instance, for callers that just want the scores and
# do not need their own ScoreBook. Loading is cheap but this avoids repeating
# it across many small tools.
_DEFAULT_BOOK: Optional[ScoreBook] = None


def get_scorebook() -> ScoreBook:
    """Return a shared, lazily-constructed ScoreBook instance."""
    global _DEFAULT_BOOK
    if _DEFAULT_BOOK is None:
        _DEFAULT_BOOK = ScoreBook()
    return _DEFAULT_BOOK


if __name__ == "__main__":
    # Self-demo. Run: python scores.py
    book = ScoreBook()
    print("Providers:", book.providers)
    print()
    for prov, action in [
        ("railway", "volume.delete"),
        ("railway", "deleteVolume"),       # alias of the above
        ("aws", "s3:DeleteBucket"),
        ("aws", "rds:RebootDBInstance"),
        ("supabase", "database.query.truncate"),
    ]:
        e = book.cloud(prov, action)
        print(f"  {prov:10} {action:28} -> score {e.score:2}  reversible={e.reversible}")
    print()
    for kind, fn, key in [
        ("sql", book.sql, "DROP"),
        ("http", book.http, "DELETE"),
        ("shell", book.shell, "rm"),
    ]:
        e = fn(key)
        print(f"  {kind:10} {key:28} -> score {e.score:2}  reversible={e.reversible}")
    print()
    miss = book.cloud("railway", "not.a.real.action")
    print(f"  unknown action, default=False -> {miss}")
    miss_d = book.cloud("railway", "not.a.real.action", default=True)
    print(f"  unknown action, default=True  -> score {miss_d.score}, recognized={miss_d.recognized}")
