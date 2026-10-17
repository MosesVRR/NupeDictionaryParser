
import json
from pathlib import Path
from datetime import datetime, timezone

# --------------------------------------------------
# Paths
# --------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent.parent
RECONCILIATION_DIR = PROJECT_DIR / "output" / "reconciliation"

REPORT_FILE = RECONCILIATION_DIR / "boundary_review_all.json" # try "boundary_review_pilot.json"
DECISIONS_FILE = RECONCILIATION_DIR / "human_review_decisions.json"
APPROVED_FILE = RECONCILIATION_DIR / "approved_corrections.json"


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path, data):
    """Write safely to a temporary file before replacing the report."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")

    temporary_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def boundary_id(result):
    return result.get("boundary", "unknown_boundary")


def load_decisions():
    if not DECISIONS_FILE.exists():
        return {"decisions": {}}

    data = load_json(DECISIONS_FILE)

    if not isinstance(data.get("decisions"), dict):
        raise ValueError(
            f"Unexpected decisions format in {DECISIONS_FILE}"
        )

    return data


def get_candidates(report):
    """Return proposed continuations and cases needing investigation."""
    return [
        result
        for result in report.get("results", [])
        if result.get("finding") in {
            "continuation_likely",
            "uncertain",
        }
    ]


def display_candidate(result, index, total, previous_decision=None):
    print("\n" + "=" * 72)
    print(f"REVIEW {index} OF {total}")
    print("=" * 72)

    print("Boundary:", result.get("boundary"))
    print("Finding:", result.get("finding"))
    print("Model confidence:", result.get("confidence"))
    print("Target page:", result.get("target_page"))
    print("Target headword:", result.get("target_headword"))
    print("Target field:", result.get("target_field"))

    print("\nEvidence:")
    for evidence in result.get("evidence", []):
        print(f"  - {evidence}")

    print("\nProposed action:")
    print(result.get("proposed_action", "(none supplied)"))

    replacement = result.get("proposed_replacement")
    if replacement is not None:
        print("\nProposed replacement:")
        print(replacement)

    # A model's confidence never removes the need for human review.
    print("\nHuman verification required: YES")

    if previous_decision:
        print("\nExisting decision:", previous_decision.get("status"))
        if previous_decision.get("note"):
            print("Previous note:", previous_decision["note"])


def record_decision(result, decisions, status, note):
    key = boundary_id(result)

    decisions["decisions"][key] = {
        "boundary": key,
        "status": status,
        "note": note,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "target_page": result.get("target_page"),
        "target_headword": result.get("target_headword"),
        "target_field": result.get("target_field"),
        "proposed_replacement": result.get("proposed_replacement"),
    }

    # Save immediately so progress survives interruption.
    save_json(DECISIONS_FILE, decisions)


def export_approved(report, decisions):
    """Export approved proposals only; do not edit source page JSON."""
    approved = []

    for result in report.get("results", []):
        decision = decisions["decisions"].get(boundary_id(result))

        if decision and decision.get("status") == "approved":
            approved.append({
                "boundary": result.get("boundary"),
                "target_page": result.get("target_page"),
                "target_headword": result.get("target_headword"),
                "target_field": result.get("target_field"),
                "proposed_replacement": result.get(
                    "proposed_replacement"
                ),
                "evidence": result.get("evidence", []),
                "human_review": decision,
                "source_proposal": result,
                "applied": False,
            })

    save_json(
        APPROVED_FILE,
        {
            "description": (
                "Human-approved correction proposals. "
                "These have NOT been applied to source JSON files."
            ),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "approved_count": len(approved),
            "corrections": approved,
        },
    )

    return len(approved)


def main():
    if not REPORT_FILE.exists():
        raise FileNotFoundError(
            f"Review report not found: {REPORT_FILE}\n"
            "Run review_page_boundaries.py first."
        )

    report = load_json(REPORT_FILE)
    decisions = load_decisions()
    candidates = get_candidates(report)

    if not candidates:
        print("No continuation or uncertain cases found in the report.")
        return

    print("Nupe Dictionary — Human Boundary Review")
    print("---------------------------------------")
    print("Candidates:", len(candidates))
    print("Report:", REPORT_FILE)
    print("Decisions:", DECISIONS_FILE)
    print("\nDecisions are saved after each response.")
    print("No source page JSON files will be modified.")

    for index, result in enumerate(candidates, start=1):
        key = boundary_id(result)
        previous = decisions["decisions"].get(key)

        # Skip completed decisions unless the user explicitly
        # chooses to revisit them.
        if previous and previous.get("status") in {"approved", "rejected"}:
            print(f"\nAlready decided: {key} — {previous['status']}")
            revisit = input("Revisit this decision? [y/N]: ").strip().lower()
            if revisit != "y":
                continue

        display_candidate(result, index, len(candidates), previous)

        while True:
            print("\nChoose a decision:")
            print("  A = Approve proposed correction")
            print("  R = Reject proposed correction")
            print("  D = Defer / investigate later")
            print("  S = Skip for now")
            print("  Q = Quit review")

            choice = input("Your choice: ").strip().lower()

            if choice in {"a", "r", "d", "s", "q"}:
                break

            print("Please enter A, R, D, S, or Q.")

        if choice == "q":
            print("Review stopped. Your previous decisions are saved.")
            break

        if choice == "s":
            continue

        status_map = {
            "a": "approved",
            "r": "rejected",
            "d": "deferred",
        }

        status = status_map[choice]
        note = input(
            "Optional note (e.g. 'Confirmed against scan'): "
        ).strip()

        record_decision(result, decisions, status, note)
        print(f"Saved decision: {status}")

    approved_count = export_approved(report, decisions)

    print("\n" + "=" * 72)
    print("REVIEW SUMMARY")
    print("=" * 72)

    counts = {}
    for decision in decisions["decisions"].values():
        status = decision.get("status", "unknown")
        counts[status] = counts.get(status, 0) + 1

    for status, count in sorted(counts.items()):
        print(f"{status.capitalize()}: {count}")

    print("\nApproved proposals exported:", approved_count)
    print("Decision log:", DECISIONS_FILE)
    print("Approved proposal file:", APPROVED_FILE)
    print("\nNo validated page JSON files were changed.")


if __name__ == "__main__":
    main()
