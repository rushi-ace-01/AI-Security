"""
Tests for the Credential Scope Auditor.

Run with:  python -m pytest tests/ -v
       or:  python tests/test_auditor.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from auditor import CredentialScopeAuditor  # noqa: E402


auditor = CredentialScopeAuditor()


# ---------------------------------------------------------------------- #
# The PocketOS pattern
# ---------------------------------------------------------------------- #
def test_pocketos_token_fails_audit():
    r = auditor.audit({
        "id": "agent-token",
        "stated_purpose": "read_only",
        "granted_capabilities": ["read", "restart", "delete", "deploy"],
        "environment": "production",
        "scope": "all",
    })
    assert r.verdict == "FAIL"
    assert r.over_permissioned is True
    assert "delete" in r.destructive_excess


def test_pocketos_token_flags_pocketos_pattern_warning():
    r = auditor.audit({
        "id": "t",
        "stated_purpose": "read_only",
        "granted_capabilities": ["read", "delete"],
        "environment": "production",
        "scope": "all",
    })
    assert any("PocketOS" in w for w in r.warnings)


# ---------------------------------------------------------------------- #
# Clean credentials
# ---------------------------------------------------------------------- #
def test_read_only_with_only_read_caps_passes():
    r = auditor.audit({
        "id": "reader",
        "stated_purpose": "read_only",
        "granted_capabilities": ["read", "list", "describe"],
        "environment": "production",
        "scope": "single-project",
    })
    assert r.verdict == "PASS"
    assert r.over_permissioned is False
    assert r.excess_capabilities == []


def test_operate_purpose_allows_operate_caps():
    r = auditor.audit({
        "id": "deploy-bot",
        "stated_purpose": "operate",
        "granted_capabilities": ["read", "restart", "redeploy", "deploy"],
        "environment": "staging",
        "scope": "single-project",
    })
    assert r.verdict == "PASS"


def test_full_admin_allows_destructive():
    r = auditor.audit({
        "id": "human-operated",
        "stated_purpose": "full_admin",
        "granted_capabilities": ["read", "delete", "terminate", "deploy"],
        "environment": "production",
        "scope": "all",
    })
    # full_admin legitimately includes destruction -> within purpose -> PASS
    assert r.verdict == "PASS"
    assert r.destructive_excess == []


# ---------------------------------------------------------------------- #
# Partial over-permissioning
# ---------------------------------------------------------------------- #
def test_non_destructive_excess_is_warn_not_fail():
    # read_only credential granted 'deploy' -> exceeds purpose, but deploy
    # is not destructive, so verdict should be WARN not FAIL.
    r = auditor.audit({
        "id": "t",
        "stated_purpose": "read_only",
        "granted_capabilities": ["read", "deploy"],
        "environment": "staging",
        "scope": "single-project",
    })
    assert r.verdict == "WARN"
    assert "deploy" in r.excess_capabilities
    assert r.destructive_excess == []


def test_modify_purpose_still_flags_delete():
    r = auditor.audit({
        "id": "t",
        "stated_purpose": "modify",
        "granted_capabilities": ["read", "write", "update", "delete"],
        "environment": "production",
        "scope": "single-project",
    })
    assert r.verdict == "FAIL"
    assert "delete" in r.destructive_excess
    # write and update are within 'modify' and must NOT be flagged
    assert "write" not in r.excess_capabilities
    assert "update" not in r.excess_capabilities


# ---------------------------------------------------------------------- #
# Unknown inputs
# ---------------------------------------------------------------------- #
def test_unknown_purpose_treated_as_read_only():
    r = auditor.audit({
        "id": "t",
        "stated_purpose": "banana",
        "granted_capabilities": ["read", "deploy"],
        "environment": "staging",
        "scope": "single-project",
    })
    # 'banana' -> read_only, so 'deploy' becomes excess
    assert "deploy" in r.excess_capabilities
    assert "unrecognised" in r.stated_purpose


def test_unknown_capability_is_flagged():
    r = auditor.audit({
        "id": "t",
        "stated_purpose": "operate",
        "granted_capabilities": ["read", "frobnicate"],
        "environment": "staging",
        "scope": "single-project",
    })
    finding = next(f for f in r.capability_findings if f.capability == "frobnicate")
    assert finding.min_purpose == "unknown"
    assert finding.within_purpose is False
    assert any("Unrecognised capabilities" in w for w in r.warnings)


def test_missing_fields_use_safe_defaults():
    # Only an id and one capability; everything else defaults.
    r = auditor.audit({"id": "minimal", "granted_capabilities": ["read"]})
    assert r.stated_purpose == "read_only"
    assert r.environment == "unknown"
    assert r.verdict == "PASS"


def test_empty_capabilities_passes():
    r = auditor.audit({
        "id": "t",
        "stated_purpose": "read_only",
        "granted_capabilities": [],
        "environment": "production",
        "scope": "all",
    })
    assert r.verdict == "PASS"
    assert r.capability_findings == []


# ---------------------------------------------------------------------- #
# Report behaviour
# ---------------------------------------------------------------------- #
def test_to_dict_is_json_serialisable():
    import json
    r = auditor.audit({
        "id": "t",
        "stated_purpose": "read_only",
        "granted_capabilities": ["read", "delete"],
        "environment": "production",
        "scope": "all",
    })
    d = r.to_dict()
    json.dumps(d)
    assert d["verdict"] == "FAIL"
    assert "destructive_excess" in d


def test_recommendations_present_on_failure():
    r = auditor.audit({
        "id": "t",
        "stated_purpose": "read_only",
        "granted_capabilities": ["read", "delete"],
        "environment": "production",
        "scope": "all",
    })
    assert len(r.recommendations) > 0


def test_scope_all_adds_scope_warning():
    r = auditor.audit({
        "id": "t",
        "stated_purpose": "read_only",
        "granted_capabilities": ["read", "deploy"],
        "environment": "staging",
        "scope": "all",
    })
    assert any("scope is 'all'" in w for w in r.warnings)


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
