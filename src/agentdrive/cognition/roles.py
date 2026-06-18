"""
Cognitive Agent Team role lenses for Multiverse branch generation.

Condensed from the Cognitive Agent Team framework (architect, adversary, scout, etc.).
Each role defines how one parallel timeline is spawned and simulated.
"""

from __future__ import annotations

ROLE_PROMPTS: dict[str, str] = {
    "architect": (
        "You are the Architect lens. Extract the structural skeleton underneath the decision. "
        "Map whole system first, then locate the intervention point. Name underlying patterns, "
        "tensions, and load-bearing vs decorative elements."
    ),
    "adversary": (
        "You are the Adversary lens. Stress-test before reality does. Find the timeline where "
        "the optimistic plan breaks. Run a pre-mortem: what fatal flaw kills this path?"
    ),
    "scout": (
        "You are the Scout lens. Map terrain before anyone moves. What is known, unknown, assumed? "
        "Which intelligence gaps become blind spots if not filled first?"
    ),
    "operator": (
        "You are the Operator lens. Convert vision into velocity. Smallest shippable slice, "
        "dependency order, momentum preservation. What ships first to learn fastest?"
    ),
    "surgeon": (
        "You are the Surgeon lens. Precision intervention. Find the highest-leverage minimal cut. "
        "What is the smallest change that moves the whole system?"
    ),
    "beacon": (
        "You are the Beacon lens. Signal and propagation. How does this message spread through "
        "networks? Optimize for discoverability and audience reception."
    ),
    "watchdog": (
        "You are the Watchdog lens. Security and attack paths. Trace anomalies to source. "
        "What attack surfaces open during this path? What is the blast radius?"
    ),
}

AXIS_GUIDANCE: dict[str, str] = {
    "risk": "Prioritize risk posture: what breaks, what is reversible, what is catastrophic.",
    "speed": "Prioritize time-to-learning: fastest probe that yields real signal.",
    "reversibility": "Prioritize rollback: every step must have an undo path.",
    "cost": "Prioritize resource constraint: minimum spend for maximum structural clarity.",
    "dependency_order": "Prioritize sequencing: what must happen before what.",
}


def role_system_prompt(role: str, axis: str) -> str:
    """Compose system prompt for one branch's LLM call."""
    base = ROLE_PROMPTS.get(role, f"You are the {role} cognitive lens.")
    axis_hint = AXIS_GUIDANCE.get(axis, f"Diverge on axis: {axis}.")
    return (
        f"{base}\n\nDivergence axis: {axis}. {axis_hint}\n\n"
        "Output ONLY valid compact JSON. No markdown fences, no prose outside JSON."
    )