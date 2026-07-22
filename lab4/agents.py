# =============================================================
# agents.py — All security agents + Supervisor
# =============================================================

import json
import math
import re
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage

from prompts import (
    AUDITOR_PROMPT,
    AUDITOR_SYSTEM,
    EXECUTOR_PROMPT,
    EXECUTOR_SYSTEM,
    GATE_PROMPT,
    GATE_SYSTEM,
    HARDENER_PROMPT,
    HARDENER_SYSTEM,
    LOGGER_SYSTEM,
    MONITOR_SYSTEM,
    SUPERVISOR_SYSTEM,
)
from state import SecurityState, ThreatResult
from tools import (
    get_llm,
    log,
    pattern_scan,
    save_security_report,
)


# =============================================================
# SUPERVISOR AGENT
# =============================================================

def supervisor_agent(state: SecurityState) -> dict:
    """
    The orchestrator of the security pipeline.

    Routing logic:
        no gate result        → security_gate
        threat detected       → security_logger
        gate clean            → llm_hardener
        hardened, no exec     → safe_executor
        executed, no monitor  → behavior_monitor
        monitored, no log     → security_logger
        logged, no report     → security_auditor
        audited               → FINISH
    """
    print("\n" + "=" * 55)
    print("[SUPERVISOR] Evaluating security pipeline state...")

    threat_detected  = state.get("threat_detected")        # None until gate runs
    threat_score     = state.get("threat_score", 0.0)
    hardened_prompt  = state.get("hardened_prompt", "")
    defense_strategy = state.get("defense_strategy", "")   # set even on hardener error
    safe_response    = state.get("safe_response", "")
    anomaly_score    = state.get("anomaly_score", -1.0)    # -1 signals not-yet-run
    security_events  = state.get("security_events") or []
    security_report  = state.get("security_report", "")

    hardener_ran = bool(defense_strategy)   # always set by llm_hardener, even on error

    # Decision tree
    if security_report:
        next_agent = "FINISH"

    elif security_events:
        next_agent = "security_auditor"

    elif anomaly_score >= 0:
        next_agent = "security_logger"

    elif safe_response:
        next_agent = "behavior_monitor"

    elif hardener_ran:
        next_agent = "safe_executor"

    elif threat_detected is True:
        # Blocked — skip hardener/executor, go straight to logging
        next_agent = "security_logger"

    elif threat_detected is False:
        next_agent = "llm_hardener"

    else:
        # Gate hasn't run yet
        next_agent = "security_gate"

    print(f"  Decision → {next_agent.upper()}")

    return {
        "current_agent": "supervisor",
        "next_agent":    next_agent,
        "execution_logs": log("Supervisor", f"Routing to: {next_agent.upper()}"),
    }


# =============================================================
# AGENT 1 — SECURITY GATE
# =============================================================

def security_gate(state: SecurityState) -> dict:
    """
    First line of defense: detects threats via fast regex + LLM.

    1. Fast regex pattern scan (pattern_scan)
    2. LLM structured output (ThreatResult) for deeper analysis

    Sets: threat_detected, threat_type, threat_score
    """
    print("\n" + "-" * 55)
    print("[SECURITY GATE] Scanning prompt for threats...")

    user_prompt = state.get("user_prompt", "")

    # Step 1: Fast regex pre-scan
    pattern_hit, matched = pattern_scan(user_prompt)
    if pattern_hit:
        print(f"  [!] Pattern match: {matched}")

    # Step 2: LLM structured analysis
    llm       = get_llm()
    evaluator = llm.with_structured_output(ThreatResult)

    try:
        result: ThreatResult = evaluator.invoke([
            SystemMessage(content=GATE_SYSTEM),
            HumanMessage(content=GATE_PROMPT.format(
                user_id=state.get("user_id", "unknown"),
                user_prompt=user_prompt,
            )),
        ])

        # If pattern matched but LLM disagrees, elevate the score
        if pattern_hit and not result.threat_detected:
            threat_detected = True
            threat_type     = "prompt_injection"
            threat_score    = max(result.threat_score, 0.75)
            reason          = f"Pattern match override: '{matched}'"
        else:
            threat_detected = result.threat_detected
            threat_type     = result.threat_type
            threat_score    = result.threat_score
            reason          = result.reason

    except Exception as exc:
        print(f"  [!] LLM gate error: {exc}")
        # Fall back to pattern scan result
        threat_detected = pattern_hit
        threat_type     = "prompt_injection" if pattern_hit else "none"
        threat_score    = 0.8 if pattern_hit else 0.0
        reason          = f"Fallback to pattern scan: {matched or 'no match'}"

    status = "BLOCKED" if threat_detected else "CLEAN"
    print(f"  Result: {status} | type={threat_type} | score={threat_score:.2f}")

    return {
        "current_agent":  "security_gate",
        "threat_detected": threat_detected,
        "threat_type":     threat_type,
        "threat_score":    threat_score,
        "execution_logs":  log("Security Gate",
            f"{status} | type={threat_type} | score={threat_score:.2f} | {reason}"
        ),
    }


# =============================================================
# AGENT 2 — LLM HARDENER
# =============================================================

def llm_hardener(state: SecurityState) -> dict:
    """
    Sanitizes a prompt that passed the gate (low threat score).

    Sets: hardened_prompt, defense_strategy
    """
    print("\n" + "-" * 55)
    print("[LLM HARDENER] Sanitizing prompt...")

    llm = get_llm()

    try:
        response = llm.invoke([
            SystemMessage(content=HARDENER_SYSTEM),
            HumanMessage(content=HARDENER_PROMPT.format(
                user_prompt=state.get("user_prompt", ""),
                threat_score=state.get("threat_score", 0.0),
                threat_type=state.get("threat_type", "none"),
            )),
        ])
        raw = response.content

        # Parse structured sections
        sanitized_match = re.search(
            r"SANITIZED_PROMPT:\s*(.*?)(?=DEFENSE_STRATEGIES:|$)",
            raw, re.DOTALL
        )
        defense_match = re.search(
            r"DEFENSE_STRATEGIES:\s*(.*?)$",
            raw, re.DOTALL
        )

        hardened_prompt  = sanitized_match.group(1).strip() if sanitized_match else state.get("user_prompt", "")
        defense_strategy = defense_match.group(1).strip()   if defense_match   else "Standard sanitization applied."

    except Exception as exc:
        print(f"  [!] Hardener error: {exc}")
        hardened_prompt  = state.get("user_prompt", "")
        defense_strategy = "Hardening unavailable — passthrough with no modification."

    print(f"  Hardened prompt ({len(hardened_prompt)} chars).")

    return {
        "current_agent":   "llm_hardener",
        "hardened_prompt": hardened_prompt,
        "defense_strategy": defense_strategy,
        "execution_logs":  log("LLM Hardener",
            f"Prompt sanitized ({len(hardened_prompt)} chars)."
        ),
    }


# =============================================================
# AGENT 3 — SAFE EXECUTOR
# =============================================================

def safe_executor(state: SecurityState) -> dict:
    """
    Executes the hardened prompt within a restricted system boundary.

    Sets: safe_response
    """
    print("\n" + "-" * 55)
    print("[SAFE EXECUTOR] Generating response within security boundary...")

    llm = get_llm()

    try:
        response = llm.invoke([
            SystemMessage(content=EXECUTOR_SYSTEM),
            HumanMessage(content=EXECUTOR_PROMPT.format(
                hardened_prompt=state.get("hardened_prompt", ""),
            )),
        ])
        safe_response = response.content

    except Exception as exc:
        print(f"  [!] Executor error: {exc}")
        safe_response = f"Execution error: {exc}"

    print(f"  Response generated ({len(safe_response)} chars).")

    return {
        "current_agent": "safe_executor",
        "safe_response": safe_response,
        "execution_logs": log("Safe Executor",
            f"Response generated ({len(safe_response)} chars)."
        ),
    }


# =============================================================
# AGENT 4 — BEHAVIOR MONITOR
# =============================================================

def behavior_monitor(state: SecurityState) -> dict:
    """
    Simulates anomaly detection based on prompt characteristics.

    Anomaly score is computed from:
    - Prompt length (very long prompts are suspicious)
    - Special character density
    - Threat score from the gate

    Sets: anomaly_score, requests_per_minute, failed_requests, is_anomalous
    """
    print("\n" + "-" * 55)
    print("[BEHAVIOR MONITOR] Computing anomaly metrics...")

    prompt      = state.get("user_prompt", "")
    threat_score = state.get("threat_score", 0.0)

    # Length factor: normalized sigmoid around 500 chars
    length_factor = 1.0 / (1.0 + math.exp(-(len(prompt) - 500) / 200))

    # Special character density
    special_chars = sum(1 for c in prompt if not c.isalnum() and not c.isspace())
    char_factor   = min(special_chars / max(len(prompt), 1) * 5, 1.0)

    # Combine factors
    anomaly_score = round(
        0.4 * threat_score + 0.35 * length_factor + 0.25 * char_factor,
        3,
    )

    # Simulate RPM and failed requests (realistic range for demo)
    requests_per_minute = max(1, int(10 + anomaly_score * 50))
    failed_requests     = max(0, int(anomaly_score * 5))
    is_anomalous        = anomaly_score > 0.6

    print(f"  anomaly_score={anomaly_score:.3f} | rpm={requests_per_minute} | anomalous={is_anomalous}")

    return {
        "current_agent":      "behavior_monitor",
        "anomaly_score":       anomaly_score,
        "requests_per_minute": requests_per_minute,
        "failed_requests":     failed_requests,
        "is_anomalous":        is_anomalous,
        "execution_logs":      log("Behavior Monitor",
            f"anomaly={anomaly_score:.3f} | rpm={requests_per_minute} | anomalous={is_anomalous}"
        ),
    }


# =============================================================
# AGENT 5 — SECURITY LOGGER
# =============================================================

def security_logger(state: SecurityState) -> dict:
    """
    Creates a structured JSON security event and sets the alert level.

    Alert level logic:
        CRITICAL  → threat_detected AND score >= 0.8
        HIGH      → threat_detected OR is_anomalous
        MEDIUM    → threat_score >= 0.4
        LOW       → everything else

    Sets: security_events, alert_level
    """
    print("\n" + "-" * 55)
    print("[SECURITY LOGGER] Building security event log...")

    threat_detected  = state.get("threat_detected", False)
    threat_score     = state.get("threat_score", 0.0)
    is_anomalous     = state.get("is_anomalous", False)
    anomaly_score    = state.get("anomaly_score", 0.0)

    # Determine alert level
    if threat_detected and threat_score >= 0.8:
        alert_level = "CRITICAL"
    elif threat_detected or is_anomalous:
        alert_level = "HIGH"
    elif threat_score >= 0.4:
        alert_level = "MEDIUM"
    else:
        alert_level = "LOW"

    event = {
        "timestamp":          datetime.now().isoformat(),
        "user_id":            state.get("user_id", "unknown"),
        "alert_level":        alert_level,
        "threat_detected":    threat_detected,
        "threat_type":        state.get("threat_type", "none"),
        "threat_score":       threat_score,
        "anomaly_score":      anomaly_score,
        "is_anomalous":       is_anomalous,
        "requests_per_minute": state.get("requests_per_minute", 0),
        "failed_requests":    state.get("failed_requests", 0),
        "prompt_length":      len(state.get("user_prompt", "")),
        "response_generated": bool(state.get("safe_response", "")),
    }

    print(f"  Alert level: {alert_level}")

    return {
        "current_agent":  "security_logger",
        "security_events": [event],
        "alert_level":    alert_level,
        "execution_logs": log("Security Logger",
            f"Event logged | alert_level={alert_level}"
        ),
    }


# =============================================================
# AGENT 6 — SECURITY AUDITOR
# =============================================================

def security_auditor(state: SecurityState) -> dict:
    """
    Generates the final structured security report and saves it to disk.

    Sets: security_report
    """
    print("\n" + "-" * 55)
    print("[SECURITY AUDITOR] Generating security report...")

    llm = get_llm()

    try:
        response = llm.invoke([
            SystemMessage(content=AUDITOR_SYSTEM),
            HumanMessage(content=AUDITOR_PROMPT.format(
                user_id=state.get("user_id", "unknown"),
                threat_detected=state.get("threat_detected", False),
                threat_type=state.get("threat_type", "none"),
                threat_score=state.get("threat_score", 0.0),
                alert_level=state.get("alert_level", "LOW"),
                anomaly_score=state.get("anomaly_score", 0.0),
                is_anomalous=state.get("is_anomalous", False),
                defense_strategy=state.get("defense_strategy", "N/A"),
                response_generated=bool(state.get("safe_response", "")),
            )),
        ])
        security_report = response.content

    except Exception as exc:
        print(f"  [!] Auditor LLM error: {exc}")
        security_report = (
            f"Security Report — {datetime.now().isoformat()}\n"
            f"User ID      : {state.get('user_id', 'unknown')}\n"
            f"Alert Level  : {state.get('alert_level', 'LOW')}\n"
            f"Threat       : {state.get('threat_type', 'none')} "
            f"(score={state.get('threat_score', 0.0):.2f})\n"
            f"Anomalous    : {state.get('is_anomalous', False)}\n"
            f"[Report generation failed: {exc}]\n"
        )

    # Save to disk
    report_path = save_security_report(
        state.get("user_id", "unknown"),
        security_report,
    )
    print(f"  Report saved → {report_path}")

    return {
        "current_agent":  "security_auditor",
        "security_report": security_report,
        "execution_logs": log("Security Auditor",
            f"Report saved → {report_path}"
        ),
    }
