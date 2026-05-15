"""
Tests for the Colocated Risk Scanner.

Run with:  python -m pytest tests/ -v
       or:  python tests/test_scanner.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scanner import ColocatedRiskScanner  # noqa: E402


scanner = ColocatedRiskScanner()


# ---------------------------------------------------------------------- #
# COLO-001: production data + backup on the same volume
# ---------------------------------------------------------------------- #
def test_pocketos_volume_colocation_is_detected():
    infra = {
        "resources": [
            {"id": "db", "roles": ["production_data"], "volume": "vol-1"},
            {"id": "bk", "roles": ["backup"], "volume": "vol-1"},
        ]
    }
    report = scanner.scan(infra)
    assert any(f.rule_id == "COLO-001" for f in report.findings)
    assert report.worst_severity == "critical"
    assert report.passed is False


def test_separate_volumes_do_not_trigger_colo001():
    infra = {
        "resources": [
            {"id": "db", "roles": ["production_data"], "volume": "vol-1"},
            {"id": "bk", "roles": ["backup"], "volume": "vol-2"},
        ]
    }
    report = scanner.scan(infra)
    assert not any(f.rule_id == "COLO-001" for f in report.findings)


def test_null_volume_is_not_a_match():
    # Two resources with unspecified volumes must NOT be treated as colocated.
    infra = {
        "resources": [
            {"id": "db", "roles": ["production_data"]},
            {"id": "bk", "roles": ["backup"]},
        ]
    }
    report = scanner.scan(infra)
    assert not any(f.rule_id == "COLO-001" for f in report.findings)


# ---------------------------------------------------------------------- #
# COLO-002 / COLO-005 / COLO-006: account, region, project
# ---------------------------------------------------------------------- #
def test_same_account_triggers_colo002():
    infra = {
        "resources": [
            {"id": "db", "roles": ["production_data"], "account": "acct-1"},
            {"id": "bk", "roles": ["backup"], "account": "acct-1"},
        ]
    }
    report = scanner.scan(infra)
    assert any(f.rule_id == "COLO-002" for f in report.findings)


def test_same_region_triggers_colo005():
    infra = {
        "resources": [
            {"id": "db", "roles": ["production_data"], "region": "us-east-1"},
            {"id": "bk", "roles": ["backup"], "region": "us-east-1"},
        ]
    }
    report = scanner.scan(infra)
    assert any(f.rule_id == "COLO-005" for f in report.findings)


def test_same_project_with_snapshot_triggers_colo006():
    infra = {
        "resources": [
            {"id": "db", "roles": ["production_data"], "project": "proj-1"},
            {"id": "snap", "roles": ["snapshot"], "project": "proj-1"},
        ]
    }
    report = scanner.scan(infra)
    assert any(f.rule_id == "COLO-006" for f in report.findings)


# ---------------------------------------------------------------------- #
# COLO-003 / COLO-004: credential role colocation
# ---------------------------------------------------------------------- #
def test_separate_credentials_sharing_token_value_triggers_colo003():
    # Two credential entries that share the same token boundary value,
    # one with production access and one with staging access.
    infra = {
        "credentials": [
            {"id": "cred-a", "roles": ["production_access"], "token": "tok-shared"},
            {"id": "cred-b", "roles": ["staging_access"], "token": "tok-shared"},
        ]
    }
    report = scanner.scan(infra)
    assert any(f.rule_id == "COLO-003" for f in report.findings)


def test_read_and_destructive_on_shared_token_triggers_colo004():
    infra = {
        "credentials": [
            {"id": "cred-a", "roles": ["read_access"], "token": "tok-1"},
            {"id": "cred-b", "roles": ["destructive_access"], "token": "tok-1"},
        ]
    }
    report = scanner.scan(infra)
    assert any(f.rule_id == "COLO-004" for f in report.findings)


# ---------------------------------------------------------------------- #
# COLO-007: capability combo
# ---------------------------------------------------------------------- #
def test_deploy_plus_delete_all_scope_triggers_colo007():
    infra = {
        "credentials": [
            {
                "id": "agent-token",
                "roles": ["production_access"],
                "capabilities": ["deploy", "delete"],
                "scope": "all",
            }
        ]
    }
    report = scanner.scan(infra)
    assert any(f.rule_id == "COLO-007" for f in report.findings)


def test_deploy_plus_delete_single_project_does_not_trigger_colo007():
    infra = {
        "credentials": [
            {
                "id": "agent-token",
                "roles": ["production_access"],
                "capabilities": ["deploy", "delete"],
                "scope": "single-project",
            }
        ]
    }
    report = scanner.scan(infra)
    assert not any(f.rule_id == "COLO-007" for f in report.findings)


def test_deploy_only_does_not_trigger_colo007():
    infra = {
        "credentials": [
            {"id": "t", "roles": [], "capabilities": ["deploy"], "scope": "all"}
        ]
    }
    report = scanner.scan(infra)
    assert not any(f.rule_id == "COLO-007" for f in report.findings)


# ---------------------------------------------------------------------- #
# Clean setups
# ---------------------------------------------------------------------- #
def test_fully_separated_setup_passes():
    infra = {
        "resources": [
            {"id": "db", "roles": ["production_data"], "volume": "v-prod",
             "account": "a-prod", "project": "p-prod", "region": "us-east-1"},
            {"id": "bk", "roles": ["backup", "snapshot"], "volume": "v-bk",
             "account": "a-bk", "project": "p-bk", "region": "us-west-2"},
        ],
        "credentials": [
            {"id": "read", "roles": ["read_access"], "token": "tok-read",
             "capabilities": ["deploy"], "scope": "single-project"},
            {"id": "del", "roles": ["destructive_access"], "token": "tok-del",
             "capabilities": ["delete"], "scope": "single-project"},
        ],
    }
    report = scanner.scan(infra)
    assert report.passed is True
    assert report.findings == []


def test_empty_infra_passes():
    report = scanner.scan({})
    assert report.passed is True
    assert report.resources_scanned == 0
    assert report.credentials_scanned == 0


# ---------------------------------------------------------------------- #
# Report behaviour
# ---------------------------------------------------------------------- #
def test_no_duplicate_findings_for_same_pair():
    # One pair colocated on the volume should produce exactly one COLO-001.
    infra = {
        "resources": [
            {"id": "db", "roles": ["production_data"], "volume": "v1"},
            {"id": "bk", "roles": ["backup"], "volume": "v1"},
        ]
    }
    report = scanner.scan(infra)
    colo001 = [f for f in report.findings if f.rule_id == "COLO-001"]
    assert len(colo001) == 1


def test_passed_is_false_only_for_medium_and_above():
    # A lone info/low finding would still pass; medium and up fails.
    # COLO-005 is medium, so this must fail.
    infra = {
        "resources": [
            {"id": "db", "roles": ["production_data"], "region": "r1"},
            {"id": "bk", "roles": ["backup"], "region": "r1"},
        ]
    }
    report = scanner.scan(infra)
    assert report.passed is False


def test_to_dict_is_json_serialisable():
    import json
    infra = {
        "resources": [
            {"id": "db", "roles": ["production_data"], "volume": "v1"},
            {"id": "bk", "roles": ["backup"], "volume": "v1"},
        ]
    }
    report = scanner.scan(infra)
    json.dumps(report.to_dict())  # must not raise


def test_count_by_severity():
    infra = {
        "resources": [
            {"id": "db", "roles": ["production_data"], "volume": "v1",
             "account": "a1", "project": "p1", "region": "r1"},
            {"id": "bk", "roles": ["backup", "snapshot"], "volume": "v1",
             "account": "a1", "project": "p1", "region": "r1"},
        ]
    }
    report = scanner.scan(infra)
    # COLO-001 critical, COLO-002 high, COLO-006 high, COLO-005 medium
    assert report.count("critical") == 1
    assert report.count("high") == 2
    assert report.count("medium") == 1


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
