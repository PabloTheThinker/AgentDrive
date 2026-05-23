"""
DNA Scanners — extract high-value, generalizable patterns from agent runs into candidate Genomes.

A scanner takes a run (from Savant workers, rich external agents, or other instrumented
systems) and extracts reusable reasoning patterns, frameworks, and improvements.
"""

from .base import BaseScanner
from .rich_run_scanner import SavantRunScanner, RichRunScanner

__all__ = ["BaseScanner", "SavantRunScanner", "RichRunScanner"]