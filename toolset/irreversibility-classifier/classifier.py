"""
Irreversibility Classifier
==========================

Scores AI agent actions on how reversible they are, BEFORE the action runs.

The classifier is deliberately simple and transparent: it is pattern-based,
not an ML model. Every score can be traced to a rule in a JSON file under
patterns/. This makes it auditable, easy to contribute to, and predictable.

Scoring scale:
    0  = fully safe / read-only
    10 = permanent and irreversible

Typical usage:

    from classifier import IrreversibilityClassifier

    clf = IrreversibilityClassifier()

    result = clf.classify("DELETE", kind="http_method")
    result = clf.classify("DROP TABLE users", kind="sql_operation")
    result = clf.classify("rm -rf /var/data", kind="shell_command")
    result = clf.classify("volume.delete", kind="cloud_api", provider="railway")

    # Or let it guess the kind:
    result = clf.classify("DROP TABLE users")

Each call returns a ClassificationResult.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# Default threshold above which an action should be treated as needing a
# human in the loop. Consumers can override this.
DEFAULT_BLOCK_THRESHOLD = 7

PATTERNS_DIR = Path(__file__).parent / "patterns"
CLOUD_API_DIR = PATTERNS_DIR / "cloud_apis"


@dataclass
class ClassificationResult:
    """The outcome of classifying a single action."""

    action: str
    score: int
    reversible: bool
    kind: str
    explanation: str
    matched_pattern: Optional[str] = None
    provider: Optional[str] = None
    safer_alternative: Optional[str] = None
    modifiers_applied: list = field(default_factory=list)
    recognized: bool = True

    @property
    def risk_level(self) -> str:
        """Human-readable bucket for the numeric score."""
        if self.score <= 2:
            return "SAFE"
        if self.score <= 5:
            return "LOW"
        if self.score <= 7:
            return "MEDIUM"
        if self.score <= 9:
            return "HIGH"
        return "CRITICAL"

    def should_block(self, threshold: int = DEFAULT_BLOCK_THRESHOLD) -> bool:
        """Whether this action should be held for human confirmation."""
        return self.score >= threshold

    def to_dict(self) -> dict:
        d = asdict(self)
        d["risk_level"] = self.risk_level
        return d

    def __str__(self) -> str:
        lines = [
            f"Action:        {self.action}",
            f"Kind:          {self.kind}" + (f" ({self.provider})" if self.provider else ""),
            f"Score:         {self.score}/10  [{self.risk_level}]",
            f"Reversible:    {self.reversible}",
            f"Explanation:   {self.explanation}",
        ]
        if self.modifiers_applied:
            lines.append(f"Modifiers:     {', '.join(self.modifiers_applied)}")
        if self.safer_alternative:
            lines.append(f"Safer path:    {self.safer_alternative}")
        if not self.recognized:
            lines.append("Note:          Action not recognized. Returned a conservative default.")
        return "\n".join(lines)


class IrreversibilityClassifier:
    """
    Pattern-based classifier for action irreversibility.

    Loads pattern files once at construction. Pattern files live in
    patterns/ and patterns/cloud_apis/ and can be extended by contributors
    without touching this code.
    """

    # Score returned when an action cannot be matched to any pattern.
    # Deliberately conservative: an unknown action is treated as risky
    # enough to warrant a look, but not auto-blocked.
    UNKNOWN_SCORE = 6

    def __init__(self, patterns_dir: Path = PATTERNS_DIR):
        self.patterns_dir = Path(patterns_dir)
        self._http: dict = {}
        self._sql: dict = {}
        self._shell: dict = {}
        self._cloud: dict = {}  # provider -> list of pattern dicts
        self._load_patterns()

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #
    def _load_json(self, path: Path) -> dict:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _load_patterns(self) -> None:
        http = self._load_json(self.patterns_dir / "http_methods.json")
        self._http = {p["match"].upper(): p for p in http["patterns"]}

        sql = self._load_json(self.patterns_dir / "sql_operations.json")
        self._sql = {p["match"].upper(): p for p in sql["patterns"]}

        shell = self._load_json(self.patterns_dir / "shell_commands.json")
        self._shell = {p["match"].lower(): p for p in shell["patterns"]}

        cloud_dir = self.patterns_dir / "cloud_apis"
        if cloud_dir.is_dir():
            for fp in sorted(cloud_dir.glob("*.json")):
                data = self._load_json(fp)
                provider = data["provider"].lower()
                self._cloud[provider] = data["patterns"]

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    @property
    def supported_providers(self) -> list:
        return sorted(self._cloud.keys())

    def classify(
        self,
        action: str,
        kind: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> ClassificationResult:
        """
        Classify a single action.

        action   : the raw action string, e.g. "DROP TABLE users" or "DELETE"
        kind     : one of http_method, sql_operation, shell_command, cloud_api.
                   If None, the classifier guesses.
        provider : required when kind is cloud_api (e.g. "railway", "aws").
        """
        if not action or not action.strip():
            raise ValueError("action must be a non-empty string")

        action = action.strip()

        if kind is None:
            kind = self._guess_kind(action, provider)

        if kind == "http_method":
            return self._classify_http(action)
        if kind == "sql_operation":
            return self._classify_sql(action)
        if kind == "shell_command":
            return self._classify_shell(action)
        if kind == "cloud_api":
            return self._classify_cloud(action, provider)

        raise ValueError(
            f"Unknown kind '{kind}'. Expected one of: "
            "http_method, sql_operation, shell_command, cloud_api"
        )

    # ------------------------------------------------------------------ #
    # Kind guessing
    # ------------------------------------------------------------------ #
    def _guess_kind(self, action: str, provider: Optional[str]) -> str:
        if provider:
            return "cloud_api"

        upper = action.upper()
        first = upper.split()[0] if upper.split() else ""

        if first in self._http:
            return "http_method"
        if first in self._sql:
            return "sql_operation"

        lower_first = action.strip().split()[0].lower() if action.strip().split() else ""
        if lower_first in self._shell:
            return "shell_command"

        # A dotted identifier like "volume.delete" is most likely a cloud API.
        if re.match(r"^[a-z]+(\.[a-z]+)+$", action.strip().split()[0], re.IGNORECASE):
            return "cloud_api"

        # Fall back to shell; it has the broadest catch and a safe default.
        return "shell_command"

    # ------------------------------------------------------------------ #
    # Per-kind classification
    # ------------------------------------------------------------------ #
    def _classify_http(self, action: str) -> ClassificationResult:
        method = action.split()[0].upper()
        pat = self._http.get(method)
        if pat is None:
            return self._unknown(action, "http_method")
        return ClassificationResult(
            action=action,
            score=pat["score"],
            reversible=pat["reversible"],
            kind="http_method",
            explanation=pat["explanation"],
            matched_pattern=pat["match"],
            safer_alternative=pat.get("safer_alternative"),
        )

    def _classify_sql(self, action: str) -> ClassificationResult:
        keyword = action.split()[0].upper()
        pat = self._sql.get(keyword)
        if pat is None:
            return self._unknown(action, "sql_operation")

        score = pat["score"]
        modifiers = []

        # Context bump: a destructive statement without a WHERE clause is worse.
        if keyword in ("UPDATE", "DELETE") and not re.search(
            r"\bWHERE\b", action, re.IGNORECASE
        ):
            score = max(score, 9)
            modifiers.append("no WHERE clause -> affects entire table")

        return ClassificationResult(
            action=action,
            score=score,
            reversible=pat["reversible"] and not modifiers,
            kind="sql_operation",
            explanation=pat["explanation"],
            matched_pattern=pat["match"],
            safer_alternative=pat.get("safer_alternative"),
            modifiers_applied=modifiers,
        )

    def _classify_shell(self, action: str) -> ClassificationResult:
        tokens = action.split()
        cmd = tokens[0].lower() if tokens else ""
        pat = self._shell.get(cmd)
        if pat is None:
            return self._unknown(action, "shell_command")

        score = pat["score"]
        reversible = pat["reversible"]
        modifiers = []

        for mod in pat.get("modifiers", []):
            flag = mod["flag"]
            # Match the flag anywhere in the command string.
            if flag in action or all(
                part in action for part in flag.split()
            ):
                if mod["score"] > score:
                    score = mod["score"]
                    reversible = False
                modifiers.append(f"{flag} -> {mod['explanation']}")

        return ClassificationResult(
            action=action,
            score=score,
            reversible=reversible,
            kind="shell_command",
            explanation=pat["explanation"],
            matched_pattern=pat["match"],
            safer_alternative=pat.get("safer_alternative"),
            modifiers_applied=modifiers,
        )

    def _classify_cloud(
        self, action: str, provider: Optional[str]
    ) -> ClassificationResult:
        if not provider:
            raise ValueError(
                "provider is required for cloud_api actions "
                f"(supported: {', '.join(self.supported_providers)})"
            )
        provider = provider.lower()
        patterns = self._cloud.get(provider)
        if patterns is None:
            raise ValueError(
                f"Unsupported provider '{provider}'. "
                f"Supported: {', '.join(self.supported_providers)}"
            )

        token = action.strip()
        for pat in patterns:
            candidates = [pat["match"]] + pat.get("aliases", [])
            if any(token.lower() == c.lower() for c in candidates):
                return ClassificationResult(
                    action=action,
                    score=pat["score"],
                    reversible=pat["reversible"],
                    kind="cloud_api",
                    explanation=pat["explanation"],
                    matched_pattern=pat["match"],
                    provider=provider,
                    safer_alternative=pat.get("safer_alternative"),
                )

        result = self._unknown(action, "cloud_api")
        result.provider = provider
        return result

    # ------------------------------------------------------------------ #
    # Unknown fallback
    # ------------------------------------------------------------------ #
    def _unknown(self, action: str, kind: str) -> ClassificationResult:
        return ClassificationResult(
            action=action,
            score=self.UNKNOWN_SCORE,
            reversible=False,
            kind=kind,
            explanation=(
                "Action did not match any known pattern. Returning a "
                "conservative default score. Consider adding a pattern for "
                "this action so it can be scored accurately."
            ),
            matched_pattern=None,
            safer_alternative=(
                "Treat as potentially destructive until a pattern is added. "
                "Require human review."
            ),
            recognized=False,
        )


if __name__ == "__main__":
    # Small self-demo. Run: python classifier.py
    clf = IrreversibilityClassifier()
    samples = [
        ("GET /api/users", None, None),
        ("DELETE /api/users/42", None, None),
        ("DROP TABLE users", None, None),
        ("UPDATE users SET active = false", None, None),
        ("rm -rf /var/data", None, None),
        ("git push --force origin main", None, None),
        ("volume.delete", "cloud_api", "railway"),
        ("rds:DeleteDBSnapshot", "cloud_api", "aws"),
        ("project.delete", "cloud_api", "supabase"),
        ("frobnicate the widget", None, None),
    ]
    for action, kind, provider in samples:
        result = clf.classify(action, kind=kind, provider=provider)
        print(result)
        print(f"  -> should_block: {result.should_block()}")
        print("-" * 60)
