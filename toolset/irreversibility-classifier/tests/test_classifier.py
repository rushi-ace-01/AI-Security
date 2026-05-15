"""
Tests for the Irreversibility Classifier.

Run with:  python -m pytest tests/  -v
       or:  python tests/test_classifier.py
"""

import sys
from pathlib import Path

# Make the parent module importable when run directly.
sys.path.insert(0, str(Path(__file__).parent.parent))

from classifier import IrreversibilityClassifier, ClassificationResult  # noqa: E402


clf = IrreversibilityClassifier()


# ---------------------------------------------------------------------- #
# HTTP methods
# ---------------------------------------------------------------------- #
def test_http_get_is_safe():
    r = clf.classify("GET /api/users", kind="http_method")
    assert r.score == 0
    assert r.reversible is True
    assert r.risk_level == "SAFE"
    assert r.should_block() is False


def test_http_delete_is_high_risk():
    r = clf.classify("DELETE /api/users/1", kind="http_method")
    assert r.score >= 8
    assert r.reversible is False
    assert r.should_block() is True


def test_http_kind_is_guessed():
    r = clf.classify("POST /api/orders")
    assert r.kind == "http_method"


# ---------------------------------------------------------------------- #
# SQL operations
# ---------------------------------------------------------------------- #
def test_sql_select_is_safe():
    r = clf.classify("SELECT * FROM users", kind="sql_operation")
    assert r.score == 0
    assert r.risk_level == "SAFE"


def test_sql_drop_is_critical():
    r = clf.classify("DROP TABLE users", kind="sql_operation")
    assert r.score == 10
    assert r.reversible is False
    assert r.risk_level == "CRITICAL"


def test_sql_truncate_is_critical():
    r = clf.classify("TRUNCATE TABLE sessions", kind="sql_operation")
    assert r.score == 10


def test_sql_update_without_where_is_bumped():
    with_where = clf.classify("UPDATE users SET x = 1 WHERE id = 5", kind="sql_operation")
    without_where = clf.classify("UPDATE users SET x = 1", kind="sql_operation")
    assert without_where.score > with_where.score
    assert without_where.modifiers_applied != []


def test_sql_delete_without_where_is_bumped():
    r = clf.classify("DELETE FROM users", kind="sql_operation")
    assert r.score >= 9
    assert any("WHERE" in m for m in r.modifiers_applied)


# ---------------------------------------------------------------------- #
# Shell commands
# ---------------------------------------------------------------------- #
def test_shell_ls_is_safe():
    r = clf.classify("ls -la /home", kind="shell_command")
    assert r.score == 0


def test_shell_rm_is_high():
    r = clf.classify("rm /tmp/file.txt", kind="shell_command")
    assert r.score >= 8


def test_shell_rm_rf_is_critical():
    r = clf.classify("rm -rf /var/data", kind="shell_command")
    assert r.score == 10
    assert r.reversible is False
    assert r.modifiers_applied != []


def test_shell_git_push_force_is_bumped():
    plain = clf.classify("git status", kind="shell_command")
    forced = clf.classify("git push --force origin main", kind="shell_command")
    assert forced.score > plain.score


# ---------------------------------------------------------------------- #
# Cloud APIs
# ---------------------------------------------------------------------- #
def test_railway_volume_delete_is_critical():
    r = clf.classify("volume.delete", kind="cloud_api", provider="railway")
    assert r.score == 10
    assert r.provider == "railway"
    assert "PocketOS" in r.explanation


def test_cloud_api_alias_matches():
    # alias of volume.delete
    r = clf.classify("deleteVolume", kind="cloud_api", provider="railway")
    assert r.score == 10
    assert r.matched_pattern == "volume.delete"


def test_aws_snapshot_delete_is_critical():
    r = clf.classify("rds:DeleteDBSnapshot", kind="cloud_api", provider="aws")
    assert r.score == 10


def test_supabase_project_delete_is_critical():
    r = clf.classify("project.delete", kind="cloud_api", provider="supabase")
    assert r.score == 10


def test_cloud_api_requires_provider():
    try:
        clf.classify("volume.delete", kind="cloud_api")
    except ValueError as e:
        assert "provider" in str(e)
    else:
        assert False, "expected ValueError for missing provider"


def test_unsupported_provider_raises():
    try:
        clf.classify("thing.delete", kind="cloud_api", provider="madeupcloud")
    except ValueError as e:
        assert "Unsupported provider" in str(e)
    else:
        assert False, "expected ValueError for unsupported provider"


# ---------------------------------------------------------------------- #
# Unknown actions
# ---------------------------------------------------------------------- #
def test_unknown_action_gets_conservative_default():
    r = clf.classify("frobnicate the widget", kind="shell_command")
    assert r.recognized is False
    assert r.score == clf.UNKNOWN_SCORE
    assert r.reversible is False


def test_unknown_cloud_action_keeps_provider():
    r = clf.classify("mystery.operation", kind="cloud_api", provider="aws")
    assert r.recognized is False
    assert r.provider == "aws"


# ---------------------------------------------------------------------- #
# Result object behavior
# ---------------------------------------------------------------------- #
def test_empty_action_raises():
    try:
        clf.classify("   ")
    except ValueError:
        pass
    else:
        assert False, "expected ValueError for empty action"


def test_threshold_is_respected():
    r = clf.classify("PATCH /api/users/1", kind="http_method")  # score 5
    assert r.should_block(threshold=4) is True
    assert r.should_block(threshold=8) is False


def test_to_dict_includes_risk_level():
    r = clf.classify("DROP TABLE users", kind="sql_operation")
    d = r.to_dict()
    assert d["risk_level"] == "CRITICAL"
    assert d["score"] == 10


# ---------------------------------------------------------------------- #
# Runner for direct execution (no pytest required)
# ---------------------------------------------------------------------- #
if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    failed = 0
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
