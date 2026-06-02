"""
Tests for Mission Control v1.5 surfaces (wave2-tests-hardening).

Covers:
- daily/dream emissions (via durable._publish_mission_event and Integrated paths)
- command dispatch (graceful + through-router)
- replay seq integrity
- attach points
- rich StaticFire telemetry (run_* context + publish + FireSession)

All target stabilization-wave-20260531 context where possible.
Uses the built-in smoke_mission_control_with_integrated_system + direct hub tests.
"""

from __future__ import annotations

# Package marker for pytest discovery of tests/mission_control/
