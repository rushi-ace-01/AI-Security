"""
End-to-end example: running the full agent-guardrails toolset against a
reconstruction of the PocketOS incident setup.

This is the scenario the whole repo exists for. In the real incident, an
autonomous coding agent found a full-scope Railway API token and used it to
delete a storage volume that held both the production database and its
backups. Customers were left reconstructing their data by hand.

This script asks: if PocketOS had run agent-guardrails first, what would it
have seen? Run it:

    python examples/pocketos_full_scan.py

Every check below flags the problem. None of them needs a live credential.
"""

import sys
from pathlib import Path

# Wire up imports from the toolset (examples/ sits next to toolset/).
ROOT = Path(__file__).parent.parent / "toolset"
sys.path.insert(0, str(ROOT / "irreversibility-classifier"))
sys.path.insert(0, str(ROOT / "blast-radius-scorer"))
sys.path.insert(0, str(ROOT / "infrastructure-protection" / "colocated-risk-scanner"))
sys.path.insert(0, str(ROOT / "infrastructure-protection" / "credential-scope-auditor"))
sys.path.insert(0, str(ROOT / "infrastructure-protection" / "separation-enforcer"))

from classifier import IrreversibilityClassifier   # noqa: E402
from scorer import BlastRadiusScorer               # noqa: E402
from scanner import ColocatedRiskScanner           # noqa: E402
from auditor import CredentialScopeAuditor         # noqa: E402
from enforcer import SeparationEnforcer            # noqa: E402


def banner(text):
    print("\n" + "#" * 70)
    print(f"#  {text}")
    print("#" * 70)


# --------------------------------------------------------------------- #
# The PocketOS setup, as a description.
# --------------------------------------------------------------------- #
INFRASTRUCTURE = {
    "resources": [
        {
            "id": "production-db",
            "roles": ["production_data"],
            "volume": "railway-vol-01",
            "account": "pocketos-railway",
            "project": "pocketos",
            "region": "us-east",
        },
        {
            "id": "database-backups",
            "roles": ["backup", "snapshot"],
            # The fatal line: same volume as production.
            "volume": "railway-vol-01",
            "account": "pocketos-railway",
            "project": "pocketos",
            "region": "us-east",
        },
    ],
    "credentials": [
        {
            "id": "railway-api-token",
            "roles": [
                "agent_default",
                "production_access",
                "staging_access",
                "read_access",
                "destructive_access",
            ],
            "capabilities": ["read", "deploy", "delete"],
            "scope": "all",
        }
    ],
}

# The same token, described for the blast radius scorer.
TOKEN_SCOPE = {
    "label": "railway-api-token",
    "scope": "full",
    "environment": "production",
    "projects": ["*"],
}

# The same token, described for the credential scope auditor. The agent's
# actual task was fixing a credential mismatch -- a read/operate job.
TOKEN_PURPOSE = {
    "id": "railway-api-token",
    "stated_purpose": "operate",
    "granted_capabilities": ["read", "deploy", "delete"],
    "environment": "production",
    "scope": "all",
}


def main():
    banner("CHECK 1  --  Irreversibility Classifier")
    print("The single action that caused the outage:\n")
    clf = IrreversibilityClassifier()
    result = clf.classify("volume.delete", kind="cloud_api", provider="railway")
    print(result)
    print(f"\n  -> should_block: {result.should_block()}")
    print("  A guardrail on this action alone would have required human")
    print("  confirmation before the volume was touched.")

    banner("CHECK 2  --  Blast Radius Scorer")
    print("What the Railway token could do, before any agent touched it:\n")
    scorer = BlastRadiusScorer()
    br = scorer.score("railway", TOKEN_SCOPE)
    print(br)

    banner("CHECK 3  --  Credential Scope Auditor")
    print("Was the token more powerful than the agent's actual job?\n")
    auditor = CredentialScopeAuditor()
    audit = auditor.audit(TOKEN_PURPOSE)
    print(audit)

    banner("CHECK 4  --  Colocated Risk Scanner")
    print("Were production data and backups dangerously colocated?\n")
    scanner = ColocatedRiskScanner()
    scan = scanner.scan(INFRASTRUCTURE)
    print(scan)

    banner("CHECK 5  --  Separation Enforcer  (the CI gate)")
    print("Would this setup have passed a separation policy in CI?\n")
    enforcer = SeparationEnforcer()
    enforcement = enforcer.enforce(INFRASTRUCTURE)
    print(enforcement)

    banner("SUMMARY")
    checks = [
        ("Irreversibility Classifier", result.should_block()),
        ("Blast Radius Scorer", not br.safe_to_automate()),
        ("Credential Scope Auditor", audit.verdict == "FAIL"),
        ("Colocated Risk Scanner", not scan.passed),
        ("Separation Enforcer", not enforcement.passed),
    ]
    for name, flagged in checks:
        mark = "FLAGGED" if flagged else "passed "
        print(f"  [{mark}]  {name}")
    flagged_count = sum(1 for _, f in checks if f)
    print(f"\n  {flagged_count} of {len(checks)} checks would have caught this before deployment.")
    print("  The incident was preventable with static analysis alone.\n")

    # Non-zero exit if the enforcer gate failed -- mirrors real CI use.
    return enforcement.exit_code


if __name__ == "__main__":
    sys.exit(main())
