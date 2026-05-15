"""
Provider base class for the Blast Radius Scorer.
================================================

A "provider" knows how to take a credential or permission config for one
platform (Railway, AWS, Supabase, ...) and expand it into the concrete set
of destructive actions that credential makes possible.

Each provider returns a list of `Capability` objects. The scorer aggregates
those into a single blast radius score.

Providers in this repo work OFFLINE by default: they analyse a permission
config / scope description that the user supplies. They do NOT call the real
cloud APIs with the user's live token. This is deliberate -- a security tool
should not itself ship a token off to a third party. Live introspection can
be added later as an explicit opt-in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Capability:
    """
    One thing a credential is able to do.

    irreversibility is the 0-10 score from the Irreversibility Classifier's
    scale. The scorer weights capabilities by this value.
    """

    action: str                      # e.g. "ec2:DeleteVolume"
    irreversibility: int             # 0-10
    resource_scope: str              # e.g. "all volumes in account", "bucket: prod-data"
    explanation: str
    reversible: bool = False
    targets_production: bool = False
    targets_backup: bool = False

    @property
    def is_destructive(self) -> bool:
        return self.irreversibility >= 6


@dataclass
class ProviderReport:
    """Everything one provider found for one credential."""

    provider: str
    credential_label: str            # a non-sensitive label, never the token itself
    capabilities: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    notes: list = field(default_factory=list)


class Provider:
    """
    Base class. A concrete provider implements `analyze`.

    The input `config` is a plain dict describing the credential's scope --
    NOT the raw secret. See each provider's docstring for the expected shape,
    and the examples/ folder for samples.
    """

    name: str = "base"

    def analyze(self, config: dict) -> ProviderReport:
        raise NotImplementedError

    # -- helpers shared by concrete providers -------------------------- #
    @staticmethod
    def _label(config: dict) -> str:
        """Pull a safe, non-sensitive label out of a config dict."""
        return (
            config.get("label")
            or config.get("name")
            or config.get("environment")
            or "unlabelled-credential"
        )

    @staticmethod
    def _looks_like_secret(value: str) -> bool:
        """
        Heuristic guard. If a user accidentally pastes a real token where a
        scope description belongs, we want to notice and refuse to store it.
        """
        if not isinstance(value, str):
            return False
        v = value.strip()
        if len(v) < 20:
            return False
        # Long opaque strings with no spaces are probably secrets.
        return " " not in v and any(c.isdigit() for c in v) and any(c.isalpha() for c in v)
