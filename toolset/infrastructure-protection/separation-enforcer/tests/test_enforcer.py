"""
Tests for the Separation Enforcer.

Run with:  python -m pytest tests/ -v
       or:  python tests/test_enforcer.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from enforcer import SeparationEnforcer, EXIT_OK, EXIT_VIOLATION  # noqa: E402


enforcer = SeparationEnforcer()


# ---------------------------------------------------------------------- #
# SEP-001 / SEP-002: shared boundary rules
# ---------------------------------------------------------------------- #
def test_shared_volume_is_blocking_violation():
    infra = {
        "resources": [
            {"id": "db", "roles": ["production_data"], "volume": "v1"},
            {"id": "bk", "roles": ["backup"], "volume": "v1"},
        ]
    }
    result = enforcer.enforce(infra)
    assert any(v.rule_id == "SEP-001" for v in result.blocking_violations)
    assert result.passed is False
    assert result.exit_code == EXIT_VIOLATION


def test_separate_volumes_pass():
    infra = {
        "resources": [
            {"id": "db", "roles": ["production_data"], "volume": "v1", "account": "a1"},
            {"id": "bk", "roles": ["backup"], "volume": "v2", "account": "a2"},
        ]
    }
    result = enforcer.enforce(infra)
    assert not any(v.rule_id in ("SEP-001", "SEP-002") for v in result.violations)


def test_shared_account_is_blocking():
    infra = {
        "resources": [
            {"id": "db", "roles": ["production_data"], "volume": "v1", "account": "a1"},
            {"id": "bk", "roles": ["backup"], "volume": "v2", "account": "a1"},
        ]
    }
    result = enforcer.enforce(infra)
    assert any(v.rule_id == "SEP-002" for v in result.blocking_violations)


# ---------------------------------------------------------------------- #
# SEP-003 / SEP-006: role combos on a credential
# ---------------------------------------------------------------------- #
def test_prod_and_staging_on_one_credential_blocks():
    infra = {
        "credentials": [
            {"id": "c", "roles": ["production_access", "staging_access"]}
        ]
    }
    result = enforcer.enforce(infra)
    assert any(v.rule_id == "SEP-003" for v in result.blocking_violations)


def test_read_and_destructive_combo_is_warn_only():
    infra = {
        "credentials": [
            {"id": "c", "roles": ["read_access", "destructive_access"]}
        ]
    }
    result = enforcer.enforce(infra)
    sep006 = [v for v in result.violations if v.rule_id == "SEP-006"]
    assert len(sep006) == 1
    assert sep006[0].blocking is False
    # SEP-006 alone is a warning, so the gate still passes.
    assert result.passed is True
    assert result.exit_code == EXIT_OK


# ---------------------------------------------------------------------- #
# SEP-004: destructive capability on agent_default
# ---------------------------------------------------------------------- #
def test_agent_default_with_delete_blocks():
    infra = {
        "credentials": [
            {"id": "c", "roles": ["agent_default"],
             "capabilities": ["read", "delete"], "scope": "single-project"}
        ]
    }
    result = enforcer.enforce(infra)
    assert any(v.rule_id == "SEP-004" for v in result.blocking_violations)


def test_agent_default_without_destructive_passes_sep004():
    infra = {
        "credentials": [
            {"id": "c", "roles": ["agent_default"],
             "capabilities": ["read", "deploy"], "scope": "single-project"}
        ]
    }
    result = enforcer.enforce(infra)
    assert not any(v.rule_id == "SEP-004" for v in result.violations)


def test_non_agent_default_with_delete_does_not_trip_sep004():
    # A deliberately-separate destructive credential is allowed by SEP-004.
    infra = {
        "credentials": [
            {"id": "c", "roles": ["destructive_access"],
             "capabilities": ["delete"], "scope": "single-resource"}
        ]
    }
    result = enforcer.enforce(infra)
    assert not any(v.rule_id == "SEP-004" for v in result.violations)


# ---------------------------------------------------------------------- #
# SEP-005: destructive capability at scope 'all'
# ---------------------------------------------------------------------- #
def test_delete_at_scope_all_blocks():
    infra = {
        "credentials": [
            {"id": "c", "roles": ["destructive_access"],
             "capabilities": ["delete"], "scope": "all"}
        ]
    }
    result = enforcer.enforce(infra)
    assert any(v.rule_id == "SEP-005" for v in result.blocking_violations)


def test_delete_at_single_resource_scope_passes_sep005():
    infra = {
        "credentials": [
            {"id": "c", "roles": ["destructive_access"],
             "capabilities": ["delete"], "scope": "single-resource"}
        ]
    }
    result = enforcer.enforce(infra)
    assert not any(v.rule_id == "SEP-005" for v in result.violations)


# ---------------------------------------------------------------------- #
# SEP-007: production resource requires a backup counterpart
# ---------------------------------------------------------------------- #
def test_production_without_any_backup_warns():
    infra = {
        "resources": [
            {"id": "db", "roles": ["production_data"], "volume": "v1"}
        ]
    }
    result = enforcer.enforce(infra)
    sep007 = [v for v in result.violations if v.rule_id == "SEP-007"]
    assert len(sep007) == 1
    assert sep007[0].blocking is False


def test_production_with_a_backup_passes_sep007():
    infra = {
        "resources": [
            {"id": "db", "roles": ["production_data"], "volume": "v1"},
            {"id": "bk", "roles": ["backup"], "volume": "v2"},
        ]
    }
    result = enforcer.enforce(infra)
    assert not any(v.rule_id == "SEP-007" for v in result.violations)


# ---------------------------------------------------------------------- #
# Whole-config behaviour
# ---------------------------------------------------------------------- #
def test_pocketos_arrangement_fails_with_multiple_blocks():
    infra = {
        "resources": [
            {"id": "db", "roles": ["production_data"], "volume": "v1", "account": "a1"},
            {"id": "bk", "roles": ["backup"], "volume": "v1", "account": "a1"},
        ],
        "credentials": [
            {"id": "t",
             "roles": ["production_access", "staging_access", "agent_default", "destructive_access"],
             "capabilities": ["read", "delete"], "scope": "all"},
        ],
    }
    result = enforcer.enforce(infra)
    assert result.passed is False
    assert len(result.blocking_violations) >= 4


def test_compliant_setup_passes_clean():
    infra = {
        "resources": [
            {"id": "db", "roles": ["production_data"], "volume": "v-prod", "account": "a-prod"},
            {"id": "bk", "roles": ["backup"], "volume": "v-bk", "account": "a-bk"},
        ],
        "credentials": [
            {"id": "agent", "roles": ["agent_default", "staging_access"],
             "capabilities": ["read", "deploy"], "scope": "single-project"},
            {"id": "destruct", "roles": ["destructive_access", "production_access"],
             "capabilities": ["delete"], "scope": "single-resource"},
        ],
    }
    result = enforcer.enforce(infra)
    assert result.passed is True
    assert result.exit_code == EXIT_OK
    assert result.violations == []


def test_empty_infra_passes():
    result = enforcer.enforce({})
    assert result.passed is True
    assert result.rules_checked == 7


def test_to_dict_is_json_serialisable():
    import json
    infra = {
        "resources": [
            {"id": "db", "roles": ["production_data"], "volume": "v1"},
            {"id": "bk", "roles": ["backup"], "volume": "v1"},
        ]
    }
    result = enforcer.enforce(infra)
    d = result.to_dict()
    json.dumps(d)
    assert d["passed"] is False
    assert d["exit_code"] == EXIT_VIOLATION


def test_warnings_do_not_affect_exit_code():
    # Only a warning-level violation -> still exit 0.
    infra = {
        "resources": [
            {"id": "db", "roles": ["production_data"], "volume": "v1"}
        ]
    }
    result = enforcer.enforce(infra)
    assert len(result.warnings) >= 1
    assert len(result.blocking_violations) == 0
    assert result.exit_code == EXIT_OK


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
