"""
Tests for the Blast Radius Scorer.

Run with:  python -m pytest tests/ -v
       or:  python tests/test_scorer.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scorer import BlastRadiusScorer, BlastRadiusReport  # noqa: E402


scorer = BlastRadiusScorer()


# ---------------------------------------------------------------------- #
# Railway
# ---------------------------------------------------------------------- #
def test_pocketos_shaped_token_is_critical():
    r = scorer.score("railway", {
        "label": "agent-token",
        "scope": "full",
        "environment": "production",
        "projects": ["*"],
    })
    assert r.risk_level == "CRITICAL"
    assert r.score >= 70
    assert r.safe_to_automate() is False


def test_readonly_railway_token_is_minimal():
    r = scorer.score("railway", {
        "label": "ci-readonly",
        "scope": "read_only",
        "environment": "staging",
        "projects": ["my-app"],
    })
    assert r.score == 0
    assert r.risk_level == "MINIMAL"
    assert r.safe_to_automate() is True


def test_railway_volume_delete_triggers_pocketos_warning():
    r = scorer.score("railway", {
        "label": "t", "scope": "full", "environment": "production", "projects": ["*"],
    })
    assert any("PocketOS" in w for w in r.warnings)


def test_railway_custom_scope_only_scores_listed_perms():
    r = scorer.score("railway", {
        "label": "scoped",
        "scope": "custom",
        "environment": "staging",
        "projects": ["app"],
        "custom_permissions": ["deployment.create", "service.get"],
    })
    actions = {c.action for c in r.scored_capabilities}
    assert actions == {"railway:deployment.create", "railway:service.get"}
    assert r.irreversible_count == 0


def test_railway_unknown_scope_defaults_to_full():
    r = scorer.score("railway", {
        "label": "weird", "scope": "banana", "environment": "production", "projects": ["*"],
    })
    # Pessimistic default: unrecognised scope treated as full -> critical.
    assert r.risk_level == "CRITICAL"
    assert any("pessimistic" in n.lower() for n in r.notes)


# ---------------------------------------------------------------------- #
# AWS
# ---------------------------------------------------------------------- #
def test_aws_admin_is_critical():
    r = scorer.score("aws", {
        "label": "admin",
        "environment": "production",
        "actions": ["*"],
        "resources": ["*"],
    })
    assert r.risk_level == "CRITICAL"
    assert r.irreversible_count >= 5


def test_aws_wildcard_expands_service():
    r = scorer.score("aws", {
        "label": "s3-only",
        "environment": "staging",
        "actions": ["s3:*"],
        "resources": ["*"],
    })
    actions = {c.action for c in r.scored_capabilities}
    assert "s3:DeleteBucket" in actions
    assert "s3:GetObject" in actions
    # s3:* should not pull in RDS actions
    assert not any(a.startswith("rds:") for a in actions)


def test_aws_readonly_actions_are_low():
    r = scorer.score("aws", {
        "label": "describe-only",
        "environment": "production",
        "actions": ["ec2:DescribeInstances", "s3:ListBucket", "iam:ListRoles"],
        "resources": ["*"],
    })
    assert r.score == 0
    assert r.destructive_count == 0


def test_aws_empty_actions_scores_zero():
    r = scorer.score("aws", {"label": "empty", "actions": []})
    assert r.score == 0
    assert r.scored_capabilities == []


def test_aws_unknown_action_scored_conservatively():
    r = scorer.score("aws", {
        "label": "mystery",
        "environment": "production",
        "actions": ["madeup:DoSomething"],
        "resources": ["*"],
    })
    cap = r.scored_capabilities[0]
    assert cap.irreversibility == 6  # conservative default
    assert any("not in the pattern files" in n for n in r.notes)


# ---------------------------------------------------------------------- #
# Supabase
# ---------------------------------------------------------------------- #
def test_supabase_anon_is_low():
    r = scorer.score("supabase", {
        "label": "public-key", "key_type": "anon", "environment": "production",
    })
    assert r.score == 0
    assert r.risk_level == "MINIMAL"


def test_supabase_service_role_is_risky():
    r = scorer.score("supabase", {
        "label": "svc", "key_type": "service_role", "environment": "production",
    })
    assert r.score >= 45
    assert any("Row Level Security" in w for w in r.warnings)


def test_supabase_management_can_delete_project():
    r = scorer.score("supabase", {
        "label": "mgmt", "key_type": "management", "environment": "production",
    })
    actions = {c.action for c in r.scored_capabilities}
    assert "supabase:project.delete" in actions
    assert r.irreversible_count >= 1


def test_supabase_db_connection_allows_drop():
    r = scorer.score("supabase", {
        "label": "pg", "key_type": "db_connection", "environment": "production",
    })
    actions = {c.action for c in r.scored_capabilities}
    assert "supabase:database.query.drop" in actions


def test_supabase_unknown_key_type_scores_nothing():
    r = scorer.score("supabase", {"label": "x", "key_type": "not_a_real_type"})
    assert r.scored_capabilities == []
    assert any("not recognised" in n for n in r.notes)


# ---------------------------------------------------------------------- #
# Scoring model
# ---------------------------------------------------------------------- #
def test_production_multiplier_raises_score():
    prod = scorer.score("supabase", {
        "label": "p", "key_type": "service_role", "environment": "production",
    })
    staging = scorer.score("supabase", {
        "label": "s", "key_type": "service_role", "environment": "staging",
    })
    assert prod.score > staging.score


def test_backup_capability_gets_backup_multiplier():
    r = scorer.score("railway", {
        "label": "t", "scope": "full", "environment": "production", "projects": ["*"],
    })
    vol = next(c for c in r.scored_capabilities if c.action == "railway:volume.delete")
    assert any("backup" in m for m in vol.multipliers)


def test_score_is_capped_at_100():
    r = scorer.score("aws", {
        "label": "everything",
        "environment": "production",
        "actions": ["*"],
        "resources": ["*"],
    })
    assert r.score <= 100


def test_to_dict_is_json_friendly():
    import json
    r = scorer.score("railway", {
        "label": "t", "scope": "full", "environment": "production", "projects": ["*"],
    })
    d = r.to_dict()
    json.dumps(d)  # must not raise
    assert d["risk_level"] == "CRITICAL"
    assert "safe_to_automate" in d


# ---------------------------------------------------------------------- #
# Errors
# ---------------------------------------------------------------------- #
def test_unknown_provider_raises():
    try:
        scorer.score("madeupcloud", {"label": "x"})
    except ValueError as e:
        assert "Unknown provider" in str(e)
    else:
        assert False, "expected ValueError"


def test_secret_in_scope_field_is_caught():
    # A value that looks like a real token pasted into a description field.
    r = scorer.score("railway", {
        "label": "oops",
        "scope": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4",
        "environment": "production",
        "projects": ["*"],
    })
    assert any("looks like a real secret" in w for w in r.warnings)


# ---------------------------------------------------------------------- #
# Single source of truth
# ---------------------------------------------------------------------- #
def test_scores_come_from_classifier_pattern_files():
    # The whole point of the refactor: the scorer must not hold its own copy
    # of irreversibility scores. It must read the classifier's pattern files.
    # We load the classifier's ScoreBook directly and confirm the scorer's
    # capabilities carry the same irreversibility numbers.
    import sys
    from pathlib import Path
    classifier_dir = (
        Path(__file__).resolve().parents[3]
        / "irreversibility-classifier"
    )
    sys.path.insert(0, str(classifier_dir))
    from scores import ScoreBook

    book = ScoreBook()

    r = scorer.score("railway", {
        "label": "t", "scope": "full", "environment": "production", "projects": ["*"],
    })
    for cap in r.scored_capabilities:
        # cap.action looks like "railway:volume.delete"
        canonical = cap.action.split(":", 1)[1]
        truth = book.cloud("railway", canonical)
        assert truth is not None, f"{canonical} missing from pattern files"
        assert cap.irreversibility == truth.score, (
            f"{canonical}: scorer says {cap.irreversibility}, "
            f"source of truth says {truth.score}"
        )


def test_aws_scores_match_source_of_truth():
    import sys
    from pathlib import Path
    classifier_dir = (
        Path(__file__).resolve().parents[3]
        / "irreversibility-classifier"
    )
    sys.path.insert(0, str(classifier_dir))
    from scores import ScoreBook

    book = ScoreBook()
    r = scorer.score("aws", {
        "label": "t", "environment": "production",
        "actions": ["*"], "resources": ["*"],
    })
    for cap in r.scored_capabilities:
        truth = book.cloud("aws", cap.action)
        if truth is None:
            continue  # unknown action, conservatively scored -- not a truth mismatch
        assert cap.irreversibility == truth.score


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
