"""
Agent Drive Harness — The execution adapter for participating in the AgentDrive.

Any agent (rich external or custom) can use `Harness` to:
- Pull relevant DNA from the Drive for a task
- Adapt its behavior using that DNA
- Record outcomes so the Drive learns and evolves
"""

from .harness import Harness, create_harness

__all__ = ["Harness", "create_harness"]
