
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Project root: Nupe_to_Eng_TextProcessor/
PROJECT_DIR = Path(__file__).resolve().parents[2]

# Allow Python to import review_page_boundaries.py directly
# from the experiments directory.
EXPERIMENTS_DIR = PROJECT_DIR / "experiments"
sys.path.insert(0, str(EXPERIMENTS_DIR))

from review_page_boundaries import load_pages, review_boundary

OUTPUT_DIR = PROJECT_DIR / "output" / "reconciliation"

PILOT_REPORT = OUTPUT_DIR / "boundary_review_pilot.json"
ALL_REPORT = OUTPUT_DIR / "boundary_review_all.json"
DECISIONS_FILE = OUTPUT_DIR / "human_review_decisions.json"


def read_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path, data):
    """Save atomically so an interrupted run preserves earlier progress."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


def get_boundary(previous_page, next_page):
    return (
        f"{previous_page['filename']} -> "
        f"{next_page['filename']}"
    )


def load_existing_results():
    """Reuse previous results so existing boundaries aren't billed again."""
    results_by_boundary = {}

    # Load the pilot first, then the cumulative report if it exists.
    for path in (PILOT_REPORT, ALL_REPORT):
        if not path.exists():
            continue

        report = read_json(path)

        for result in report.get("results", []):
            boundary = result.get("boundary")
            if boundary:
                results_by_boundary[boundary] = result

    return results_by_boundary


def load_decided_boundaries():
    if not DECISIONS_FILE.exists():
        return set()

    data = read_json(DECISIONS_FILE)
    decisions = data.get("decisions", {})

    # Do not call the model again for a boundary with a saved decision.
    return set(decisions.keys())


def calculate_usage(results):
    input_tokens = 0
    output_tokens = 0

    for result in results:
        usage = result.get("_usage", {})
        input_tokens += usage.get("input_tokens", 0)
        output_tokens += usage.get("output_tokens", 0)

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Nupe Dictionary — Full Boundary Review")
    print("---------------------------------------")

    pages = load_pages()
    boundaries = list(zip(pages[:-1], pages[1:]))

    results_by_boundary = load_existing_results()
    decided_boundaries = load_decided_boundaries()

    report = {
        "description": (
            "Cumulative model review of consecutive dictionary page "
            "boundaries. Findings are proposals, not verified corrections."
        ),
        "input_directory": str(
            PROJECT_DIR / "output" / "validated"
        ),
        "model": "gpt-6-astra",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source_files_modified": False,
        "boundary_pairs_in_dataset": len(boundaries),
        "results": list(results_by_boundary.values()),
        "usage_totals": calculate_usage(
            list(results_by_boundary.values())
        ),
        "errors": [],
    }

    # Save the cumulative starting point before making any API calls.
    save_json(ALL_REPORT, report)

    reused = len(results_by_boundary)
    print("Page files loaded:", len(pages))
    print("Consecutive boundaries:", len(boundaries))
    print("Existing results reused:", reused)
    print("Saved decisions:", len(decided_boundaries))
    print("Cumulative report:", ALL_REPORT)
    print()

    for index, (previous_page, next_page) in enumerate(
        boundaries, start=1
    ):
        boundary = get_boundary(previous_page, next_page)

        # Existing findings are reused, never regenerated.
        if boundary in results_by_boundary:
            continue

        # Avoid spending credits on a boundary already decided by you.
        if boundary in decided_boundaries:
            print(f"[{index}/{len(boundaries)}] Already decided: {boundary}")
            continue

        print(f"[{index}/{len(boundaries)}] Reviewing {boundary}")

        try:
            result = review_boundary(previous_page, next_page)

            # Ensure the boundary identifier is present and consistent.
            result["boundary"] = boundary
            result["needs_visual_verification"] = (
                result.get("finding") == "continuation_likely"
                or result.get("finding") == "uncertain"
            )

            if result["needs_visual_verification"]:
                result["reason_visual_verification_needed"] = (
                    result.get("reason_visual_verification_needed")
                    or "Human verification against the original scan "
                    "is required before accepting this proposal."
                )

            results_by_boundary[boundary] = result

            report["results"] = list(results_by_boundary.values())
            report["updated_at"] = datetime.now(
                timezone.utc
            ).isoformat()
            report["usage_totals"] = calculate_usage(
                report["results"]
            )

            # Persist each successful result immediately.
            save_json(ALL_REPORT, report)

            print(
                "  Finding:",
                result.get("finding", "uncertain"),
                "| Confidence:",
                result.get("confidence", "unknown"),
            )

        except KeyboardInterrupt:
            print("\nInterrupted. Saving progress before exit.")
            report["results"] = list(results_by_boundary.values())
            report["usage_totals"] = calculate_usage(
                report["results"]
            )
            report["updated_at"] = datetime.now(
                timezone.utc
            ).isoformat()
            save_json(ALL_REPORT, report)
            raise

        except Exception as exc:
            error = {
                "boundary": boundary,
                "error": str(exc),
                "recorded_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            }

            # Errors are logged separately from findings.
            # The boundary remains eligible for retry on the next run.
            report["errors"].append(error)
            report["updated_at"] = datetime.now(
                timezone.utc
            ).isoformat()
            save_json(ALL_REPORT, report)

            print("  ERROR:", exc)
            print("  This boundary can be retried on the next run.")

    report["results"] = list(results_by_boundary.values())
    report["updated_at"] = datetime.now(timezone.utc).isoformat()
    report["usage_totals"] = calculate_usage(report["results"])

    findings = {}
    for result in report["results"]:
        finding = result.get("finding", "uncertain")
        findings[finding] = findings.get(finding, 0) + 1

    report["finding_counts"] = findings
    report["source_files_modified"] = False
    save_json(ALL_REPORT, report)

    usage = report["usage_totals"]

    print("\n" + "=" * 64)
    print("FULL REVIEW SUMMARY")
    print("=" * 64)
    print("Boundaries in dataset:", len(boundaries))
    print("Results saved:", len(report["results"]))
    print("Findings:", findings)
    print("Input tokens:", usage["input_tokens"])
    print("Output tokens:", usage["output_tokens"])
    print("Total tokens:", usage["total_tokens"])
    print("Logged errors:", len(report["errors"]))
    print("Report:", ALL_REPORT)
    print("\nValidated source JSON files were not modified.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped safely. Saved results can be reused.")
        sys.exit(130)
