"""
Savant Agent — the Savant Framework as a conversational AI agent.

The framework is the body. The model is the voice. The pool is the memory.
The user talks to the agent; the agent talks back, grounded in DNA that
grows with every turn.
"""

from agentdrive.agent.agent import SAVANT_IDENTITY, SavantAgent, TurnResult
from agentdrive.agent.indicator import Indicator
from agentdrive.agent.session import AgentSession, Turn

__all__ = [
    "SavantAgent",
    "TurnResult",
    "SAVANT_IDENTITY",
    "AgentSession",
    "Turn",
    "Indicator",
]
