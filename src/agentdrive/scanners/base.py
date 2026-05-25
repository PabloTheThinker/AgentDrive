"""
Base class for all DNA Scanners.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from agentdrive.genome.models import Genome


class BaseScanner(ABC):
    """
    A Scanner knows how to look at an agent run (or a collection of runs)
    and produce candidate Genomes.
    """

    name: str = "base"

    @abstractmethod
    def scan(self, run_data: dict[str, Any] | Path) -> list[Genome]:
        """
        Given raw run data (or a path to a trajectory / log / engagement),
        return one or more candidate Genomes.
        """
        raise NotImplementedError

    def get_name(self) -> str:
        """Return the scanner name (use this instead of .name to avoid shadowing)."""
        return self.name
