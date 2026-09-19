import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend"))

from decision import make_decision  # noqa: E402

TICKET_FIELDS = [
    "message",
    "order_value_inr",
    "days_since_delivery",
    "days_since_dispatch",
    "product_type",
    "opened_status",
    "order_status",
]


def build_ticket(case: dict) -> dict:
    return {k: case[k] for k in TICKET_FIELDS if case.get(k) not in (None, "")}


def run_case(case: dict) -> dict:
    decision = make_decision(build_ticket(case))
    return {
        "id": case.get("case_id", case.get("ticket_id", "?")),
        "expected": case["expected_action"],
        "action": decision["action"],
        "confidence": decision["confidence"],
        "correct": decision["action"] == case["expected_action"],
    }


def run_cases(cases: list[dict]) -> list[dict]:
    return [run_case(c) for c in cases]


def print_report(results: list[dict]) -> None:
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    incorrect = total - correct

    print("\n" + "=" * 40)
    print(f"{total} test cases")
    print(f"Correct: {correct}")
    print(f"Incorrect: {incorrect}")
    print(f"Accuracy: {100 * correct / total:.0f}%")
    print("=" * 40 + "\n")

    for r in results:
        status = "PASS" if r["correct"] else "FAIL"
        print(f"[{status}] {r['id']}: got={r['action']} ({(r['confidence'] or 0):.0%}) expected={r['expected']}")


def load_cases(path: str, fmt: str) -> list[dict]:
    if fmt == "csv":
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            row["expected_action"] = row.pop("resolved_action")
        return rows

    if fmt == "json":
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    raise ValueError(f"Unknown format: {fmt}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate AI decision accuracy against labeled cases")
    parser.add_argument(
        "--cases",
        default="data/sample_test_cases.json",
        help="Path to sample_test_cases.json or tickets.csv (default: data/sample_test_cases.json)",
    )
    parser.add_argument(
        "--format",
        choices=["auto", "json", "csv"],
        default="auto",
        help="Input format (default: auto-detect from file extension)",
    )
    args = parser.parse_args()

    fmt = "csv" if args.format == "auto" and args.cases.endswith(".csv") else ("json" if args.format == "auto" else args.format)
    cases = load_cases(args.cases, fmt)
    print(f"Evaluating {len(cases)} cases from {args.cases}...")

    results = run_cases(cases)
    print_report(results)


if __name__ == "__main__":
    main()