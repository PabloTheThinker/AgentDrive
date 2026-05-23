"""
Savant Harness — The execution adapter for participating in the Savant Pool.

Any agent (rich external or custom) can use `SavantHarness` to:
- Pull relevant DNA from the central pool for a task
- Adapt its behavior using that DNA
- Record outcomes so the pool learns and evolves
"""

from .harness import SavantHarness, create_harness

__all__ = ["SavantHarness", "create_harness"]