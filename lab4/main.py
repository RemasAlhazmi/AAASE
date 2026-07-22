#!/usr/bin/env python3
# =============================================================
# main.py — CLI entry point for the AI Security Platform
# =============================================================

import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Ensure lab4/ is on the path when run from project root
LAB4_DIR = os.path.dirname(os.path.abspath(__file__))
if LAB4_DIR not in sys.path:
    sys.path.insert(0, LAB4_DIR)

from graph import build_graph


def run_security_pipeline(user_id: str, user_prompt: str) -> dict:
    """Run the full security pipeline and return the final state."""
    app = build_graph()

    initial_state = {
        "user_id":            user_id,
        "user_prompt":        user_prompt,
        "current_agent":      "",
        "next_agent":         "",
        "threat_detected":    None,
        "threat_type":        "none",
        "threat_score":       0.0,
        "hardened_prompt":    "",
        "defense_strategy":   "",
        "safe_response":      "",
        "anomaly_score":      -1.0,
        "requests_per_minute": 0,
        "failed_requests":    0,
        "is_anomalous":       False,
        "security_events":    [],
        "alert_level":        "LOW",
        "security_report":    "",
        "execution_logs":     [],
    }

    config = {"configurable": {"thread_id": f"cli-{user_id}"}}

    final_state = None
    for snapshot in app.stream(initial_state, config, stream_mode="values"):
        final_state = snapshot

    return final_state


def main():
    print("=" * 60)
    print("  AI SECURITY PLATFORM — Lab 4")
    print("=" * 60)

    user_id = input("\nEnter User ID (or press Enter for 'user_001'): ").strip() or "user_001"

    print("\nEnter your prompt (press Enter twice to submit):")
    lines = []
    while True:
        line = input()
        if line == "" and lines:
            break
        lines.append(line)
    user_prompt = "\n".join(lines).strip()

    if not user_prompt:
        print("[!] No prompt provided. Exiting.")
        return

    print("\n" + "=" * 60)
    print("  Running security pipeline...")
    print("=" * 60)

    final_state = run_security_pipeline(user_id, user_prompt)

    print("\n" + "=" * 60)
    print("  SECURITY ANALYSIS RESULTS")
    print("=" * 60)

    threat_detected = final_state.get("threat_detected", False)
    status          = "BLOCKED" if threat_detected else "SUCCESS"
    print(f"\n  Status      : [{status}]")
    print(f"  Threat Type : {final_state.get('threat_type', 'none')}")
    print(f"  Threat Score: {final_state.get('threat_score', 0.0):.2f}")
    print(f"  Alert Level : {final_state.get('alert_level', 'LOW')}")
    print(f"  Anomaly     : {final_state.get('anomaly_score', 0.0):.3f}")

    if not threat_detected and final_state.get("safe_response"):
        print("\n  Safe Response:")
        print("  " + "-" * 40)
        print(final_state["safe_response"])

    print("\n  Execution Log:")
    for entry in final_state.get("execution_logs", []):
        print(f"  {entry}")


if __name__ == "__main__":
    main()
