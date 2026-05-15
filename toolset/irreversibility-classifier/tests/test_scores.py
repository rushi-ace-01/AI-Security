"""
Tests for scores.py -- the single source of truth lookup module.

Run with:  python -m pytest tests/ -v
       or:  python tests/test_scores.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scores import ScoreBook, ScoreEntry, get_scorebook, UNKNOWN_SCORE  # noqa: E402


book = ScoreBook()


# ---------------------------------------------------------------------- #
# Cloud lookups
# ---------------------------------------------------------------------- #
def test_railway_volume_delete_is_canonical_10():
    e = book.cloud("railway", "volume.delete")
    assert e is not None
    assert e.score == 10
    assert e.reversible is False
    assert e.provider == "railway"


def test_cloud_alias_resolves_to_same_entry():
    canonical = book.cloud("railway", "volume.delete")
    via_alias = book.cloud("railway", "deleteVolume")
    assert via_alias is not None
    assert via_alias.action == canonical.action
    assert via_alias.score == canonical.score


def test_cloud_lookup_is_case_insensitive():
    a = book.cloud("railway", "volume.delete")
    b = book.cloud("RAILWAY", "VOLUME.DELETE")
    assert a.score == b.score


def test_aws_and_supabase_providers_present():
    assert "aws" in book.providers
    assert "supabase" in book.providers
    assert "railway" in book.providers


def test_aws_known_action_lookup():
    e = book.cloud("aws", "s3:DeleteBucket")
    assert e.score == 10
    e2 = book.cloud("aws", "rds:RebootDBInstance")
    assert e2.score == 3
    assert e2.reversible is True


def test_supabase_truncate_is_10():
    e = book.cloud("supabase", "database.query.truncate")
    assert e.score == 10
    assert e.is_irreversible is True


def test_unknown_action_returns_none_by_default():
    assert book.cloud("railway", "not.a.real.action") is None


def test_unknown_action_with_default_returns_conservative_entry():
    e = book.cloud("railway", "not.a.real.action", default=True)
    assert e is not None
    assert e.score == UNKNOWN_SCORE
    assert e.recognized is False
    assert e.reversible is False


def test_unknown_provider_raises():
    try:
        book.cloud("madeupcloud", "thing.delete")
    except ValueError as e:
        assert "Unknown provider" in str(e)
    else:
        assert False, "expected ValueError"


# ---------------------------------------------------------------------- #
# Non-cloud lookups
# ---------------------------------------------------------------------- #
def test_sql_drop_is_10():
    e = book.sql("DROP")
    assert e.score == 10


def test_sql_select_is_0():
    assert book.sql("SELECT").score == 0


def test_http_delete_is_9():
    assert book.http("DELETE").score == 9


def test_http_get_is_0():
    assert book.http("GET").score == 0


def test_shell_rm_is_9():
    assert book.shell("rm").score == 9


def test_shell_unknown_returns_none():
    assert book.shell("frobnicate") is None


def test_shell_unknown_with_default():
    e = book.shell("frobnicate", default=True)
    assert e.score == UNKNOWN_SCORE
    assert e.recognized is False


# ---------------------------------------------------------------------- #
# Bulk access
# ---------------------------------------------------------------------- #
def test_all_cloud_returns_canonical_keys_only():
    table = book.all_cloud("railway")
    # Canonical key present, alias absent.
    assert "volume.delete" in table
    assert "deleteVolume" not in table
    # Every value is a ScoreEntry.
    assert all(isinstance(v, ScoreEntry) for v in table.values())


def test_all_cloud_count_matches_pattern_file():
    import json
    rj = json.load(open(
        Path(__file__).parent.parent / "patterns" / "cloud_apis" / "railway.json"
    ))
    assert len(book.all_cloud("railway")) == len(rj["patterns"])


def test_all_cloud_unknown_provider_raises():
    try:
        book.all_cloud("madeupcloud")
    except ValueError:
        pass
    else:
        assert False, "expected ValueError"


# ---------------------------------------------------------------------- #
# Shared instance
# ---------------------------------------------------------------------- #
def test_get_scorebook_returns_shared_instance():
    a = get_scorebook()
    b = get_scorebook()
    assert a is b


# ---------------------------------------------------------------------- #
# Consistency: the ScoreBook must agree with the classifier itself
# ---------------------------------------------------------------------- #
def test_scorebook_agrees_with_classifier():
    # ScoreBook reads the same pattern files the classifier does. For any
    # action, classifying it and looking it up must yield the same score.
    from classifier import IrreversibilityClassifier
    clf = IrreversibilityClassifier()

    checks = [
        ("railway", "volume.delete"),
        ("aws", "s3:DeleteBucket"),
        ("aws", "rds:RebootDBInstance"),
        ("supabase", "database.query.delete"),
    ]
    for provider, action in checks:
        classified = clf.classify(action, kind="cloud_api", provider=provider)
        looked_up = book.cloud(provider, action)
        assert classified.score == looked_up.score, (
            f"{provider}:{action} -- classifier {classified.score} "
            f"vs scorebook {looked_up.score}"
        )


# ---------------------------------------------------------------------- #
# Runner
# ---------------------------------------------------------------------- #
if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {t.__name__}: {e}")
            failed += 1
        except Exception as e:  # noqa: BLE001
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print("-" * 60)
    print(f"{passed} passed, {failed} failed, {len(tests)} total")
    sys.exit(1 if failed else 0)
