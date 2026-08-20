#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

TERMINAL_STATUSES = {"completed", "failed", "escalated"}


def request_json(
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed with {exc.code}: {detail}") from exc


def load_cases(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def contains_value(value: Any, expected: str) -> bool:
    if isinstance(value, str):
        return expected in value
    if isinstance(value, dict):
        return any(contains_value(nested, expected) for nested in value.values())
    if isinstance(value, list):
        return any(contains_value(item, expected) for item in value)
    return False


def event_types(details: dict[str, Any]) -> list[str]:
    return [str(event.get("type")) for event in details.get("events", [])]


def wait_for_progress(
    api_base: str,
    thread_id: str,
    *,
    timeout_seconds: float,
    poll_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    latest: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        latest = request_json("GET", f"{api_base}/api/workflows/{thread_id}")
        status = latest.get("status")
        if status in TERMINAL_STATUSES or status == "waiting_approval":
            return latest
        time.sleep(poll_seconds)
    raise TimeoutError(f"Timed out waiting for workflow {thread_id}; last={latest}")


def wait_for_terminal(
    api_base: str,
    thread_id: str,
    *,
    timeout_seconds: float,
    poll_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    latest: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        latest = request_json("GET", f"{api_base}/api/workflows/{thread_id}")
        if latest.get("status") in TERMINAL_STATUSES:
            return latest
        time.sleep(poll_seconds)
    raise TimeoutError(f"Timed out waiting for terminal workflow {thread_id}; last={latest}")


def submit_decision(api_base: str, details: dict[str, Any], decision: str, case_id: str) -> None:
    approvals = details.get("pending_approvals") or []
    if not approvals:
        raise RuntimeError(f"{case_id}: expected pending approval but found none")
    approval = approvals[0]
    request_json(
        "POST",
        f"{api_base}/api/hitl/respond",
        {
            "checkpoint_id": approval["checkpoint_id"],
            "decision": decision,
            "reviewer": "manual-matrix-runner",
            "comments": f"{decision} by manual matrix runner for {case_id}",
        },
    )


def evaluate_case(case: dict[str, Any], details: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    types = set(event_types(details))
    status = details.get("status")
    expected_status = case.get("expected_status")
    if status != expected_status:
        failures.append(f"status expected {expected_status}, observed {status}")

    has_hitl = "hitl.request" in types
    if has_hitl != bool(case.get("expect_hitl")):
        failures.append(f"HITL expected {case.get('expect_hitl')}, observed {has_hitl}")

    for event_type in case.get("required_events", []):
        if event_type not in types:
            failures.append(f"missing event {event_type}")

    for event_type in case.get("forbidden_events", []):
        if event_type in types:
            failures.append(f"forbidden event {event_type} was emitted")

    expected_order_id = case.get("expected_order_id")
    if expected_order_id and not contains_value(details, expected_order_id):
        failures.append(f"expected order id {expected_order_id} not found in workflow details")

    return failures


def run_case(
    api_base: str,
    case: dict[str, Any],
    *,
    request_timeout_seconds: float,
    timeout_seconds: float,
    poll_seconds: float,
) -> dict[str, Any]:
    body = {"message": case["prompt"]}
    if case.get("session_id"):
        body["session_id"] = case["session_id"]
    response = request_json(
        "POST",
        f"{api_base}/api/chat/run",
        body,
        timeout=request_timeout_seconds,
    )
    thread_id = response["thread_id"]
    details = wait_for_progress(
        api_base,
        thread_id,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
    )

    decision = case.get("decision")
    if decision:
        submit_decision(api_base, details, str(decision), case["id"])
        details = wait_for_terminal(
            api_base,
            thread_id,
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
        )
    elif details.get("status") not in TERMINAL_STATUSES:
        details = wait_for_terminal(
            api_base,
            thread_id,
            timeout_seconds=timeout_seconds,
            poll_seconds=poll_seconds,
        )

    failures = evaluate_case(case, details)
    return {
        "case_id": case["id"],
        "thread_id": thread_id,
        "status": details.get("status"),
        "hitl": "hitl.request" in event_types(details),
        "result": "PASS" if not failures else "FAIL",
        "failures": failures,
    }


def print_results(results: list[dict[str, Any]]) -> None:
    print("| Case | Result | Status | HITL | Thread | Notes |")
    print("| --- | --- | --- | --- | --- | --- |")
    for result in results:
        notes = "; ".join(result["failures"]) if result["failures"] else "ok"
        print(
            f"| {result['case_id']} | {result['result']} | {result['status']} | "
            f"{result['hitl']} | {result['thread_id']} | {notes} |"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the ORD manual verification matrix.")
    parser.add_argument("api_base", help="Backend base URL, for example http://localhost:8000")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).parents[2] / "frontend/src/data/manualCases.json",
        help="Path to manual matrix JSON cases.",
    )
    parser.add_argument("--case", dest="case_ids", action="append", help="Run one case id.")
    parser.add_argument(
        "--request-timeout",
        type=float,
        default=60.0,
        help="HTTP request timeout in seconds.",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="Timeout per wait phase.")
    parser.add_argument("--poll", type=float, default=1.0, help="Polling interval in seconds.")
    parser.add_argument(
        "--case-delay",
        type=float,
        default=0.0,
        help="Delay between cases in seconds; useful for low-capacity hosted model deployments.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    api_base = args.api_base.rstrip("/")
    cases = load_cases(args.cases)
    if args.case_ids:
        selected = {case_id.upper() for case_id in args.case_ids}
        cases = [case for case in cases if str(case["id"]).upper() in selected]
        missing = selected - {str(case["id"]).upper() for case in cases}
        if missing:
            print(f"Unknown case id(s): {', '.join(sorted(missing))}", file=sys.stderr)
            return 2

    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        if index > 0 and args.case_delay > 0:
            time.sleep(args.case_delay)
        try:
            results.append(
                run_case(
                    api_base,
                    case,
                    request_timeout_seconds=args.request_timeout,
                    timeout_seconds=args.timeout,
                    poll_seconds=args.poll,
                )
            )
        except Exception as exc:
            results.append(
                {
                    "case_id": case["id"],
                    "thread_id": "n/a",
                    "status": "error",
                    "hitl": "n/a",
                    "result": "FAIL",
                    "failures": [str(exc)],
                }
            )

    print_results(results)
    return 1 if any(result["result"] == "FAIL" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
