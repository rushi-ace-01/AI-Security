"""
scorebook.py -- bridge to the single source of truth.
=====================================================

The Blast Radius Scorer must not keep its own copy of irreversibility
scores. They live in the Irreversibility Classifier's pattern files, exposed
by that tool's `scores` module.

This thin shim makes the classifier's ScoreBook importable from inside the
blast-radius-scorer package without every provider repeating the sys.path
wiring. Providers do:

    from .scorebook import get_book
    book = get_book()
    book.cloud("railway", "volume.delete")   # canonical score, one source

In a future packaged version of agent-guardrails this shim disappears --
the classifier's scores module becomes a normal importable dependency. For
the current repo-of-folders layout, this is the seam that keeps the source
of truth single.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The classifier lives alongside the blast-radius-scorer in toolset/.
#   toolset/blast-radius-scorer/providers/scorebook.py   <- this file
#   toolset/irreversibility-classifier/scores.py         <- the source of truth
_CLASSIFIER_DIR = (
    Path(__file__).resolve().parents[2] / "irreversibility-classifier"
)

if str(_CLASSIFIER_DIR) not in sys.path:
    sys.path.insert(0, str(_CLASSIFIER_DIR))

# Re-export the pieces providers need, so they import from here.
from scores import ScoreBook, ScoreEntry, get_scorebook  # noqa: E402


def get_book() -> ScoreBook:
    """Return the shared ScoreBook -- the canonical irreversibility scores."""
    return get_scorebook()


__all__ = ["ScoreBook", "ScoreEntry", "get_book"]
