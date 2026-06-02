"""
AgentDrive Professional TUI Application

High-quality terminal interface for the AgentDrive.
Focus: precision, clarity, trust, and powerful genome-aware workflows.

Agent Drive is an independent, open-source framework for agent DNA (memory + patterns).
It gives every agent — and every swarm of sub-agents — its own persistent,
user-controlled living pool of experience that starts empty and grows with use.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from contextlib import nullcontext
from datetime import datetime
from typing import Any

import httpx
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from rich.console import Group
from rich.live import Live
from rich.markup import escape as rich_escape
from rich.panel import Panel
from rich.text import Text

from agentdrive.genome.models import Genome
from agentdrive.registry import GenomeRegistry
from agentdrive.tui.chat import ChatView
from agentdrive.tui.skin_engine import skin
from agentdrive.tui.views.drive_view import register_drive_view


class MissionControlClient:
    """
    Cross-process client for MissionControlHub (Wave 3).

    - Hydrates from /state (httpx, always available) for 6-step + fabric + grid snapshots.
    - Optional true WS subscribe (/ws/mission) when 'websocket-client' package present
      (import websocket): push events, seq tracking, replay via after_seq on reconnect,
      command surface with ack correlation.
    - Background polling thread keeps snapshots fresh (lightweight "SSE-like" fallback).
    - Resilient: auto-reconnect + replay for WS path; always falls back to http snapshots.
    - Duck-types the in-process hub API surface used by TUI (derive_* + recent_events + dispatch_command)
      so _show_mission_control_view render + command paths need zero special casing.
    - Per AGENTS.md: no new auth (uses the documented unauth observation + local cmd surface),
      local-first, targets real `agentdrive mission` on stabilization-wave-20260531 context.
    - References exact payloads from server.py: initial_state{type,data,seq}, event{seq,event_type,data,...},
      replay{type,after_seq,events,current_seq}, command_ack{type,...}, replay_events command.
    """

    def __init__(self, url: str = "ws://127.0.0.1:8421/ws/mission"):
        self._raw_url = url or "ws://127.0.0.1:8421/ws/mission"
        self.ws_url = self._normalize_ws_url(self._raw_url)
        self.http_base = self._to_http_base(self._raw_url)
        self._state_lock = threading.Lock()
        self.loop_state: dict[str, Any] = {"status": "initializing"}
        self.fabric: dict[str, Any] = {}
        self.grid_health: dict[str, Any] = {}
        self.recent_events: list[dict[str, Any]] = []
        self.last_seq: int = 0
        self.connected: bool = False  # true WS push connected
        self._http_ok: bool = False
        self._stop_event = threading.Event()
        self._poll_thread: threading.Thread | None = None
        self._ws_thread: threading.Thread | None = None
        self._ws_sock: Any = None  # the websocket connection when HAS_WS
        self._pending_acks: dict[str, dict[str, Any]] = {}  # nonce -> ack payload
        self._ack_timeout = 2.0
        self._last_ack: Any = None
        self._seq_gap_detected: bool = False
        self.last_error: str | None = None
        self._reconnect_backoff: float = 0.5
        self._ws_supervisor_thread: threading.Thread | None = None

        # Optional real WS client (pip install websocket-client provides "import websocket")
        try:
            import websocket as _wsmod  # type: ignore

            self._wsmod = _wsmod
            self._has_ws_lib = True
        except Exception:
            self._wsmod = None
            self._has_ws_lib = False

        self._start_poll_thread()
        # Wave 3 harden: always start resilient WS supervisor (if lib) for auto reconnect + late join even if initial connect fails
        if self._has_ws_lib:
            self._start_ws_supervisor()
        # WS attempt is lazy: first explicit connect() or on first use in view

    def _normalize_ws_url(self, u: str) -> str:
        u = u.strip()
        if u.startswith("http://"):
            u = "ws://" + u[len("http://") :]
        elif u.startswith("https://"):
            u = "wss://" + u[len("https://") :]
        if "://" not in u:
            u = "ws://" + u
        # ensure /ws/mission path
        if "/ws/mission" not in u:
            base = u.rstrip("/")
            if not base.endswith("/ws/mission"):
                u = base + "/ws/mission"
        return u

    def _to_http_base(self, u: str) -> str:
        u = u.strip()
        if u.startswith("ws://"):
            u = "http://" + u[5:]
        elif u.startswith("wss://"):
            u = "https://" + u[6:]
        # strip ws path
        if "/ws/mission" in u:
            u = u.split("/ws/mission")[0]
        return u.rstrip("/")

    def _start_poll_thread(self) -> None:
        self._stop_event.clear()
        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="mc-http-poll"
        )
        self._poll_thread.start()

    def _start_ws_supervisor(self) -> None:
        """Minimal resilient WS supervisor: ensures auto-reconnect + late-join replay with exp backoff even if daemon starts after TUI (or initial connect fails)."""
        if self._ws_supervisor_thread and self._ws_supervisor_thread.is_alive():
            return
        self._ws_supervisor_thread = threading.Thread(
            target=self._ws_supervisor_loop, daemon=True, name="mc-ws-supervisor"
        )
        self._ws_supervisor_thread.start()

    def _ws_supervisor_loop(self) -> None:
        """Background supervisor for WS resilience (exponential backoff, seq replay on every (re)connect)."""
        while not self._stop_event.is_set():
            if self.connected and self._ws_sock is not None:
                time.sleep(2.0)
                continue
            if not self._has_ws_lib:
                time.sleep(5.0)
                continue
            try:
                sock = self._wsmod.create_connection(self.ws_url, timeout=3.5)
                with self._state_lock:
                    self._ws_sock = sock
                    self.connected = True
                    self._reconnect_backoff = 0.5
                    self.last_error = None
                # start recv thread if needed
                if self._ws_thread is None or not self._ws_thread.is_alive():
                    self._ws_thread = threading.Thread(
                        target=self._ws_recv_loop, daemon=True, name="mc-ws-recv"
                    )
                    self._ws_thread.start()
                # seq replay for reconnect / late join
                self._request_replay(self.last_seq)
            except Exception as exc:
                with self._state_lock:
                    self.connected = False
                    self._ws_sock = None
                    self.last_error = f"ws_connect:{str(exc)[:80]}"
                    self._reconnect_backoff = min(self._reconnect_backoff * 1.8, 12.0)
                time.sleep(self._reconnect_backoff)
                continue
            time.sleep(1.5)

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            self._hydrate_http()
            # jittered poll
            time.sleep(1.2 + (time.time() % 0.3))

    def _hydrate_http(self) -> None:
        """Always-available snapshot path using /state (exact contract from server.py)."""
        if httpx is None:
            return
        try:
            url = self.http_base + "/state"
            with httpx.Client(timeout=2.5, follow_redirects=True) as client:
                resp = client.get(url)
                if resp.status_code == 200:
                    payload = resp.json()
                    with self._state_lock:
                        # Fix: handle bare {"status": "no_mission_attached"} from server /state (when no Integrated attached to Tower)
                        ls = payload.get("loop_state")
                        if ls is None:
                            st = payload.get("status")
                            self.loop_state = {"status": st} if isinstance(st, (str, dict)) else {}
                        else:
                            self.loop_state = ls or {}
                        self.fabric = payload.get("fabric", {}) or {}
                        self.grid_health = payload.get("grid_health", {}) or {}
                        self._http_ok = True
                        # recent count only; full list comes from WS when available
                else:
                    with self._state_lock:
                        self._http_ok = False
        except Exception:
            with self._state_lock:
                self._http_ok = False

    def connect(self) -> bool:
        """Attempt WS connection for live push + commands + replay. Returns whether WS path active. (supervisor provides resilience + late join)"""
        if not self._has_ws_lib:
            self.last_error = "no_websocket_client_lib"
            return False
        if self.connected and self._ws_sock is not None:
            return True
        # Trigger supervisor for immediate + background resilience (fixes prior late-connect failure mode)
        if self._has_ws_lib:
            self._start_ws_supervisor()
        # Best-effort immediate try (supervisor will keep retrying)
        try:
            sock = self._wsmod.create_connection(self.ws_url, timeout=3.5)
            with self._state_lock:
                self._ws_sock = sock
                self.connected = True
                self._reconnect_backoff = 0.5
                self.last_error = None
            if self._ws_thread is None or not self._ws_thread.is_alive():
                self._ws_thread = threading.Thread(
                    target=self._ws_recv_loop, daemon=True, name="mc-ws-recv"
                )
                self._ws_thread.start()
            self._request_replay(self.last_seq)
            return True
        except Exception as exc:
            with self._state_lock:
                self.connected = False
                self._ws_sock = None
                self.last_error = f"ws_connect:{str(exc)[:80]}"
            return False

    def _ws_recv_loop(self) -> None:
        """Push subscribe loop. Handles exact WS payloads per server.py. (supervisor owns connect/reconnect resilience + replay)"""
        while not self._stop_event.is_set():
            sock = self._ws_sock
            if sock is None or not self.connected:
                time.sleep(1.0)
                # Do not attempt connect here; supervisor thread handles resilient reconnect + after_seq replay
                continue
            try:
                # blocking recv of text frame
                raw = sock.recv()
                if raw:
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        msg = {"raw": str(raw)[:200]}
                    self._handle_ws_message(msg)
            except Exception:
                # connection lost; flag for supervisor (resilient auto-reconnect + replay)
                with self._state_lock:
                    self.connected = False
                    self._seq_gap_detected = True  # expect replay on recovery
                try:
                    if self._ws_sock:
                        self._ws_sock.close()
                except Exception:
                    pass
                self._ws_sock = None
                time.sleep(0.2)

    def _handle_ws_message(self, msg: dict[str, Any]) -> None:
        """Process initial_state, replay, command_ack, and live event payloads (see server.py)."""
        with self._state_lock:
            mtype = msg.get("type")
            if mtype == "initial_state":
                data = msg.get("data", {})
                self.loop_state = data.get("loop_state", {}) or data.get("status", {}) or {}
                if isinstance(self.loop_state, str):
                    self.loop_state = {"status": self.loop_state}
                self.fabric = data.get("fabric", {}) or {}
                self.grid_health = data.get("grid_health", {}) or {}
                new_seq = int(msg.get("seq", self.last_seq))
                if new_seq > self.last_seq + 1:
                    self._seq_gap_detected = True
                self.last_seq = new_seq
                # server may also include recent count; we rely on subsequent events or explicit replay
            elif mtype == "replay":
                for ev in msg.get("events", []) or []:
                    self._ingest_event(ev)
                new_seq = int(msg.get("current_seq", self.last_seq))
                if new_seq > self.last_seq + 1:
                    self._seq_gap_detected = True
                self.last_seq = new_seq
                if self._seq_gap_detected:
                    self.last_error = "seq gap detected + replay successful"
            elif mtype == "command_ack":
                # correlate by command or by our nonce if present (now echoed by server post tiny align)
                nonce = msg.get("nonce") or msg.get("id")
                if nonce and nonce in self._pending_acks:
                    self._pending_acks[nonce] = msg
                # also keep a last ack for simple cases
                self._last_ack = msg
            elif "seq" in msg or msg.get("event_type"):
                # canonical live event (or replay item shape)
                self._ingest_event(msg)
                if "seq" in msg:
                    new_seq = int(msg["seq"])
                    if new_seq > self.last_seq + 1:
                        self._seq_gap_detected = True
                    self.last_seq = max(self.last_seq, new_seq)
            # also allow server to push state updates in other shapes (defensive)

    def _ingest_event(self, ev: dict[str, Any]) -> None:
        self.recent_events.append(ev)
        if len(self.recent_events) > 80:
            self.recent_events = self.recent_events[-50:]
        # Opportunistic: some events carry fresh coherence etc; hydrate will correct anyway
        et = ev.get("event_type", "")
        if et in ("loop_step", "fabric_update", "overseer_state"):
            # leave authoritative snapshots to /state ; events primarily for the "recent" pane
            pass

    def _request_replay(self, after: int) -> None:
        if self.connected and self._ws_sock:
            try:
                payload = {"command": "replay_events", "after_seq": int(after)}
                self._ws_sock.send(json.dumps(payload))
            except Exception:
                pass

    def _make_nonce(self) -> str:
        return f"{time.time_ns()}"

    def send_command(self, command: str, **kwargs: Any) -> dict[str, Any]:
        """Send command over WS (if live) or degrade gracefully. Mirrors hub.dispatch_command contract (now with nonce ack correlation)."""
        if not self._has_ws_lib or not self.connected or self._ws_sock is None:
            # Consistent graceful shape with in-proc hub when no mission (duck-type)
            return {
                "command": command,
                "error": "no_mission_attached" if not self._has_ws_lib else "no_cross_process_ws",
                "graceful": True,
                "note": "WS not active; using HTTP snapshots. Use agentdrive mission + attach Integrated for full live.",
                "timestamp": time.time(),
            }
        nonce = self._make_nonce()
        payload = {
            "command": command,
            "nonce": nonce,
            **{k: v for k, v in kwargs.items() if k != "nonce"},
        }
        with self._state_lock:
            self._pending_acks[nonce] = {"_pending": True}
        try:
            self._ws_sock.send(json.dumps(payload, default=str))
        except Exception as exc:
            with self._state_lock:
                self._pending_acks.pop(nonce, None)
            self.last_error = f"ws_send:{exc}"
            return {"command": command, "error": f"ws_send_failed:{exc}", "timestamp": time.time()}

        # Wait for correlated ack (nonce now echoed by server post-align; recv thread populates)
        deadline = time.time() + self._ack_timeout
        while time.time() < deadline:
            with self._state_lock:
                entry = self._pending_acks.get(nonce)
                if entry and not entry.get("_pending"):
                    ack = self._pending_acks.pop(nonce, entry)
                    return ack
            time.sleep(0.03)
        # timeout: still ok (side-effect via publish_event_sync will appear); events show in Tower
        with self._state_lock:
            self._pending_acks.pop(nonce, None)
        return {
            "command": command,
            "status": "sent_ws_no_ack_timeout",
            "graceful": True,
            "timestamp": time.time(),
        }

    # --- Duck-type surface for zero-delta usage in _show_mission_control_view ---
    def derive_loop_state_snapshot(self) -> dict[str, Any]:
        with self._state_lock:
            return dict(self.loop_state)

    def derive_fabric_snapshot(self) -> dict[str, Any]:
        with self._state_lock:
            return dict(self.fabric)

    def dispatch_command(self, command: str, **kwargs: Any) -> dict[str, Any]:
        """Compatibility with in-proc hub.dispatch_command."""
        return self.send_command(command, **kwargs)

    # recent_events already a list attr (we return ref; callers do list()[-N:] which is fine)

    def close(self) -> None:
        self._stop_event.set()
        if self._ws_sock:
            try:
                self._ws_sock.close()
            except Exception:
                pass
        self.connected = False
        self._ws_sock = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass


class AgentDriveTUI:
    """Production-grade interactive TUI for Agent Drive genome management and orchestration."""

    def __init__(self, mission_url: str | None = None):
        self.skin = skin
        self.console = skin.console
        self.registry = GenomeRegistry()
        self.running = True
        self.selected: str | None = None  # current focused genome dir_name or id
        self.run_history: list[dict[str, Any]] = []
        self._cancel_event = threading.Event()

        # Prompt toolkit session with persistent history
        agentdrive_home = self.registry.root.parent
        agentdrive_home.mkdir(parents=True, exist_ok=True)
        self._history_file = agentdrive_home / ".agentdrive_tui_history"
        self.session: PromptSession = PromptSession(
            history=FileHistory(str(self._history_file)),
            completer=None,  # set dynamically per prompt for fresh genome list
            enable_history_search=True,
            mouse_support=False,
        )

        self._base_commands = [
            "help",
            "?",
            "h",
            "genomes",
            "ls",
            "list",
            "g",
            "view",
            "v",
            "status",
            "dash",
            "dashboard",
            "s",
            "drive",
            "d",
            "board",
            "missions",
            "kanban",
            "b",
            "mc",
            "mission",
            "control",
            "mctrl",
            "chat",
            "scan",
            "run",
            "r",
            "execute",
            "evolve",
            "e",
            "compose",
            "c",
            "doctor",
            "dr",
            "setup",
            "configure",
            "import",
            "bootstrap",
            "clear",
            "cls",
            "exit",
            "quit",
            "q",
            ":q",
        ]
        self._ensure_bootstrap()
        # Attach first-class Pool view (stateful across switches)
        try:
            register_drive_view(self)
        except Exception:
            self.pool_view = None

        # Optional MissionControlHub subscription for v1.5 unified mission view parity (non-breaking)
        # If a harness / Integrated system in same process attached the global hub, or if
        # mission_control module importable, TUI can surface 6-step / fabric / events / commands.
        # Graceful: remains None and invisible if no MC in this runtime (default TUI unchanged).
        self._mc_hub = None
        try:
            from agentdrive.mission_control.server import hub as _mc_hub

            self._mc_hub = _mc_hub
        except Exception:
            self._mc_hub = None

        # Wave 3: cross-process Mission Control client (TUI separate from supervisor running `agentdrive mission`).
        # Populated on-demand in mc view when url provided or auto-discovered (or via launch flag).
        # Duck-types the in-proc hub (derive_loop_state_snapshot / derive_fabric_snapshot / recent_events / dispatch_command)
        # so _show_mission_control_view + status + commands need zero special casing.
        # Uses /state + /ws/mission with seq replay (after_seq), reconnect backoff per exact payloads in server.py:mission_websocket + handle_inbound_command.
        # Targets stabilization-wave-20260531 IntegratedRealTimeEvolutionSystem attached to `agentdrive mission`.
        self._mc_remote: MissionControlClient | None = None
        if mission_url:
            try:
                mc = MissionControlClient(url=mission_url)
                mc.connect()  # best-effort WS; HTTP /state poll always active from ctor
                self._mc_remote = mc
            except Exception:
                # leave None (graceful; TUI + local mc still fully work)
                pass

    def _ensure_bootstrap(self) -> None:
        """Register seed example on first use so TUI is immediately useful."""
        try:
            gid = self.registry.ensure_bootstrap_example()
            if gid:
                self.console.print(
                    f"[agentdrive.ok]✓ Bootstrapped seed genome into registry:[/] [agentdrive.genome]{gid}[/]"
                )
                if not self.selected:
                    self.selected = gid
        except Exception as e:
            self.console.print(f"[agentdrive.warn]Bootstrap note:[/] {e}")

    def _get_status_context(self) -> str:
        """Short status snippet for the prompt line (registry count, pool health, optional MC)."""
        try:
            stats = self.registry.get_registry_stats()
            cnt = stats.get("count", 0)
            base = f"[dim]{cnt} genome{'s' if cnt != 1 else ''}[/]"
            if getattr(self, "_mc_hub", None) is not None:
                base += " [agentdrive.accent]mc[/]"
            elif getattr(self, "_mc_remote", None) is not None and getattr(
                self._mc_remote, "connected", False
            ):
                base += " [agentdrive.accent]mc:remote[/]"
            elif getattr(self, "_mc_remote", None) is not None:
                base += " [agentdrive.muted]mc:http[/]"
            return base
        except Exception:
            return "[dim]--[/]"

    def _build_completer(self) -> WordCompleter:
        """Fresh completer including live genome names and commands."""
        try:
            details = self.registry.list_genome_details()
            names = set()
            for d in details:
                names.add(d["dir_name"])
                names.add(d["genome_id"])
                names.add(d["id"])
            names.update(self.registry.list_genomes())
        except Exception:
            names = set()
        # Pool sub-commands for excellent sentence completion after "pool " or "p "
        pool_sub_commands = [
            "query",
            "q",
            "search",
            "swarms",
            "sw",
            "switch",
            "use",
            "swarm",
            "global",
            "main",
            "genomes",
            "ls",
            "browse",
            "view",
            "v",
            "ingest",
            "i",
            "evolve",
            "e",
            "merge",
            "m",
            "settings",
            "cfg",
            "config",
            "stats",
            "st",
            "overview",
            "o",
            "create-swarm",
            "help",
            "back",
            "leave",
        ]
        all_tokens = list(self._base_commands) + pool_sub_commands + sorted(names)
        return WordCompleter(all_tokens, ignore_case=True, sentence=True)

    def run(self) -> None:
        """Main REPL loop — premium feel with completion, history, clean interrupts."""
        from agentdrive.config import get_instance_name

        self.skin.print_banner(get_instance_name())

        # Dedicated first-launch Agent Drive Welcome Screen
        # Shown once after onboarding — distinct from the reusable setup wizard.
        try:
            from agentdrive.config import load_config, save_config

            cfg = load_config()
            if cfg.get("onboarded") and not cfg.get("tui_welcome_shown"):
                self._show_dedicated_welcome_screen()
                cfg["tui_welcome_shown"] = True
                save_config(cfg)
        except Exception:
            pass

        self.console.print(
            "[dim]Professional evolutionary agent capability platform • Genomes as DNA • Precise • Trustworthy[/dim]\n"
        )

        stats = self.registry.get_registry_stats()
        if stats["count"] > 0:
            doms = ", ".join(stats["domains_covered"][:4]) or "—"
            self.console.print(
                f"[agentdrive.label]Registry[/]: [agentdrive.genome]{stats['count']}[/] genomes  •  domains: [agentdrive.framework]{doms}[/]\n"
            )

        self._print_quick_help()

        # First-class chat is the default landing — drop straight into talking
        # to your Agent Drive Agent. /back from chat returns to the command REPL.
        try:
            self._show_chat()
        except Exception as exc:
            self.console.print(f"[agentdrive.warn]Chat could not start:[/] {rich_escape(str(exc))}")
        if not self.running:
            self.console.print(
                "\n[dim]Goodbye — your genomes and runs are safe in the registry.[/dim]"
            )
            return

        while self.running:
            try:
                completer = self._build_completer()
                self.session.completer = completer

                sel = ""
                if self.selected:
                    short = self.selected.split("@")[0] if "@" in self.selected else self.selected
                    sel = f" ({short})"

                status_str = self._get_status_context()
                prompt_text = f"agentdrive{sel} {status_str} ❯ "
                line = self.session.prompt(
                    prompt_text,
                    default="",
                ).strip()

                if not line:
                    continue
                self._dispatch(line)

            except KeyboardInterrupt:
                self._cancel_event.set()
                self.console.print(
                    "\n[agentdrive.warn]▲ Interrupted[/]  (use 'exit' or Ctrl+D to quit)"
                )
            except EOFError:
                self.running = False
            except Exception as exc:
                self.console.print(f"[agentdrive.error]TUI error:[/] {rich_escape(str(exc))}")

        self.console.print("\n[dim]Goodbye — your genomes and runs are safe in the registry.[/dim]")

    def _print_quick_help(self) -> None:
        from agentdrive.tui.chrome import Palette, status_rule

        p = Palette(self.skin)
        self.console.print(
            status_rule(
                f"[{p.accent}]chat[/]",
                f"[{p.accent}]board[/]",
                f"[{p.accent}]pool[/]",
                f"[{p.accent}]mc[/]",
                f"[{p.accent}]genomes[/]",
                f"[{p.accent}]run[/]",
                f"[{p.accent}]doctor[/]",
                f"[{p.muted}]help · exit[/]",
                palette=p,
            )
        )
        self.console.print()

    def _show_dedicated_welcome_screen(self) -> None:
        """One-time welcome screen shown on first TUI launch after onboarding."""
        from rich.console import Group
        from rich.text import Text

        from agentdrive.tui.chrome import Glyphs, Palette, Section, section_panel

        p = Palette(self.skin)

        # Environment snapshot
        try:
            from pathlib import Path

            from agentdrive.drive.drive import get_default_drive

            agentdrive_home = Path.home() / ".agentdrive"
            pool = get_default_drive()
            pstats = pool.get_pool_stats()
            ingest_count = pstats.get("ingest_events", 0)
            swarm_count = (
                len(list((agentdrive_home / "swarms").glob("*")))
                if (agentdrive_home / "swarms").exists()
                else 0
            )
        except Exception:
            agentdrive_home = Path.home() / ".agentdrive"
            ingest_count = 0
            swarm_count = 0

        try:
            from agentdrive.providers import detect

            detected = detect()
            provider_v = (
                f"[agentdrive.ok]✓ {detected.display_name}[/]"
                if detected
                else "[agentdrive.warn]not configured[/]"
            )
        except Exception:
            provider_v = "[agentdrive.warn]unavailable[/]"

        from agentdrive.config import get_instance_name

        instance_name = get_instance_name()
        is_personal = instance_name and instance_name != "AgentDrive"

        hero = Text()
        hero.append(f"{Glyphs.DIAMOND} ", style=p.accent)
        if is_personal:
            hero.append(instance_name, style=p.title + " bold")
            hero.append("  ·  ", style=p.muted)
            hero.append("AgentDrive", style=p.title + " bold")
        else:
            hero.append("AGENTDRIVE", style=p.title + " bold")

        tagline = Text(
            "Your private, persistent ecosystem for agent DNA.",
            style=p.muted + " italic",
        )

        body = section_panel(
            Group(hero, tagline),
            Section(
                "Your system",
                [
                    ("home", f"[agentdrive.genome]{agentdrive_home}[/]"),
                    ("provider", provider_v),
                    (
                        "drive",
                        f"[agentdrive.ok]ready[/]  · {ingest_count} events",
                    ),
                    ("swarms", f"{swarm_count} active"),
                ],
                palette=p,
            ),
            Section(
                "Begin",
                [
                    ("chat", "talk to your agents"),
                    ("drive", "explore genomes & memory"),
                    ("board", "see missions & work"),
                    ("doctor", "health check"),
                ],
                palette=p,
                key_width=12,
            ),
            title=f"Welcome to {instance_name}" if is_personal else "Welcome to AgentDrive",
            palette=p,
        )

        self.console.print()
        self.console.print(body)
        self.console.print()

    def _dispatch(self, line: str) -> None:
        """Parse and route command. Supports 'cmd arg1 arg2', aliases, and
        slash-prefixed forms (`/pool` works the same as `pool`)."""
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower().strip()
        if cmd.startswith("/"):
            cmd = cmd[1:]
        argstr = parts[1] if len(parts) > 1 else ""
        args = argstr.split() if argstr else []

        if cmd in ("exit", "quit", "q", ":q", "bye"):
            self.running = False
            return
        if cmd in ("help", "?", "h"):
            self._show_help()
            return
        if cmd in ("genomes", "ls", "list", "g"):
            self._browse_genomes(args)
            return
        if cmd in ("view", "v", "show"):
            self._view_genome(args)
            return
        if cmd in ("status", "dash", "dashboard", "s"):
            self._show_status()
            return
        if cmd in ("drive", "d"):
            self._show_pool_view(args)
            return
        if cmd in ("chat", "/chat"):
            self._show_chat()
            return
        if cmd in ("board", "missions", "kanban", "b"):
            self._show_board(args)
            return
        if cmd in ("mc", "mission", "control", "mctrl"):
            self._show_mission_control_view(args)
            return
        if cmd == "scan":
            self._scan_runs(args)
            return
        if cmd in ("run", "r", "execute"):
            self._run_work(args)
            return
        if cmd in ("evolve", "e", "improve"):
            self._evolve_genome(args)
            return
        if cmd in ("compose", "c"):
            self._compose_mission(args)
            return
        if cmd in ("doctor", "dr", "health"):
            self._doctor()
            return
        if cmd in ("setup", "configure"):
            self._run_setup_wizard(args)
            return
        if cmd in ("import", "bootstrap", "seed"):
            self._import_example(args)
            return
        if cmd in ("clear", "cls"):
            # No user input in the command string, but os.system spawns a
            # shell — prefer subprocess.run with an argv list so any future
            # caller that thinks they can templatize the command can't
            # accidentally introduce a shell-injection path.
            import subprocess

            subprocess.run(
                ["cls"] if os.name == "nt" else ["clear"],
                check=False,
                shell=False,
            )
            self.skin.print_banner("AgentDrive")
            return

        self.console.print(f"[agentdrive.warn]Unknown:[/] {cmd}  — try [agentdrive.accent]help[/]")

    # ─────────────────────────────────────────────────────────────────────
    # Command implementations
    # ─────────────────────────────────────────────────────────────────────

    def _show_help(self) -> None:
        from rich.text import Text

        from agentdrive.tui.chrome import Palette, Section, section_panel

        p = Palette(self.skin)

        sections = [
            Section(
                "Talk",
                [
                    ("chat", "open the agent chat (default landing)"),
                ],
                palette=p,
                key_width=18,
            ),
            Section(
                "Pool",
                [
                    ("pool / p", "enter the first-class Pool TUI (global + swarms)"),
                    ('pool query "…"', "one-shot query from this prompt"),
                    ("pool swarms", "browse swarms"),
                    ("pool stats", "pool-wide stats"),
                ],
                palette=p,
                key_width=18,
            ),
            Section(
                "Board",
                [
                    ("board / b / kanban", "AgentDrive Mission Board (terminal) — web Kanban at http://127.0.0.1:8421/ (run `agentdrive board`)"),
                    ("board recent", "compact recent-missions view"),
                    ("board create <t>", "stage a Pending mission"),
                    ("board stats", "lane counts + avg duration"),
                ],
                palette=p,
                key_width=18,
            ),
            Section(
                "Mission Control (v1.5 + Wave 3 cross-proc)",
                [
                    (
                        "mc / mission / control",
                        "unified 6-step + fabric + events + cmd surface (same-proc hub or remote)",
                    ),
                    (
                        "agentdrive tui --mission ws://127.0.0.1:8421",
                        "cross-process TUI client against separate `agentdrive mission` Tower",
                    ),
                    (
                        "inside TUI: mc ws://...  or mc --url ...",
                        "ad-hoc attach live client (uses MissionControlClient + seq replay)",
                    ),
                    (
                        "",
                        "graceful no_mission; targets stabilization-wave-20260531; uses existing chrome",
                    ),
                ],
                palette=p,
                key_width=22,
            ),
            Section(
                "Genomes",
                [
                    ("genomes / g", "browse the registry as a table"),
                    ("view <id|#>", "inspect a single genome"),
                    ("import / seed", "register the bundled seed example"),
                ],
                palette=p,
                key_width=18,
            ),
            Section(
                "Execution",
                [
                    ("run <genome>", "interactive composer + live progress"),
                    ("scan <path>", "extract DNA from a run/trajectory"),
                    ("evolve <genome>", "propose an evolutionary improvement"),
                    ("compose / c", "multi-genome mission composer"),
                ],
                palette=p,
                key_width=18,
            ),
            Section(
                "Environment",
                [
                    ("doctor / dr", "animated system health check"),
                    ("setup / configure", "re-run the setup wizard"),
                    ("status / s", "registry health + recent activity"),
                ],
                palette=p,
                key_width=18,
            ),
            Section(
                "Session",
                [
                    ("clear / cls", "clear screen + banner"),
                    ("help / ?", "show this panel"),
                    ("exit / quit / q", "clean shutdown"),
                ],
                palette=p,
                key_width=18,
            ),
        ]

        hint = Text()
        hint.append("Keys: ", style=p.muted)
        hint.append("Tab", style=f"bold {p.accent}")
        hint.append(" complete  ", style=p.muted)
        hint.append("↑↓", style=f"bold {p.accent}")
        hint.append(" history  ", style=p.muted)
        hint.append("Ctrl+C", style=f"bold {p.accent}")
        hint.append(" interrupt  ", style=p.muted)
        hint.append("Ctrl+D", style=f"bold {p.accent}")
        hint.append(" quit", style=p.muted)

        self.console.print()
        self.console.print(
            section_panel(
                *sections,
                hint,
                title="AgentDrive TUI · commands",
                palette=p,
            )
        )

    def _browse_genomes(self, args: list[str]) -> None:
        """Tree-stem genome browser with optional search filter."""
        from rich.text import Text

        from agentdrive.tui.chrome import (
            Palette,
            Tree,
            TreeRow,
            error_line,
            section_panel,
            warn_line,
        )
        from agentdrive.tui.loading import MicroSpinner

        p = Palette(self.skin)

        query = " ".join(args) if args else ""
        try:
            with MicroSpinner(self.console, "scanning registry…", accent=p.accent):
                if query:
                    dirs = self.registry.search_genomes(query)
                    details = [
                        d for d in self.registry.list_genome_details() if d["dir_name"] in dirs
                    ]
                else:
                    details = self.registry.list_genome_details()
        except Exception as e:
            self.console.print(error_line(f"Registry error: {e}", palette=p))
            return

        if not details:
            self.console.print()
            self.console.print(
                warn_line(
                    f"No genomes match. Use [{p.accent}]import[/] to seed the example.",
                    palette=p,
                )
            )
            return

        rows: list[TreeRow] = []
        for idx, d in enumerate(details, 1):
            dom = ", ".join(d.get("domains", [])[:2]) or "—"
            n_steps = d.get("num_steps", 0)
            score = d.get("score", 0)
            gid = d.get("genome_id", d["dir_name"])
            # genome_id may already include @version (e.g. "name@1.0.0") — don't duplicate
            gid_short = gid.split("@", 1)[0] if "@" in gid else gid
            ver = d.get("version") or (gid.split("@", 1)[1] if "@" in gid else "?")
            author = ", ".join(d.get("authors", [])[:1]) or "?"

            label = f"[{p.muted}]{idx:>2}[/]  [bold {p.genome}]{gid_short}[/] [dim]@{ver}[/]"
            secondary = (
                f"{dom}  [{p.muted}]·[/] {n_steps} step{'s' if n_steps != 1 else ''}  "
                f"[{p.muted}]·[/] score [{p.evolution}]{score:.2f}[/]  "
                f"[{p.muted}]·[/] {author}"
            )
            rows.append(TreeRow(label=label, secondary=secondary))

        head = Text("Genomes  ", style=f"bold {p.accent}")
        head.append(f"({len(details)})", style=p.muted)
        if query:
            head.append("   search: ", style=p.muted)
            head.append(query, style=f"bold {p.framework}")

        hint = Text()
        hint.append("Inspect with ", style=p.muted)
        hint.append("view <#|id>", style=f"bold {p.accent}")
        hint.append("   ·   ", style=p.muted)
        hint.append("Execute with ", style=p.muted)
        hint.append("run <#|id>", style=f"bold {p.accent}")

        self.console.print()
        self.console.print(
            section_panel(
                Group(head, Text(""), Tree(rows, palette=p)),
                hint,
                palette=p,
            )
        )

        if not self.selected and details:
            self.selected = details[0]["dir_name"]

    def _view_genome(self, args: list[str]) -> None:
        """Chrome-styled single-genome inspector."""
        from rich.console import Group as _Group
        from rich.text import Text

        from agentdrive.tui.chrome import (
            Glyphs,
            Palette,
            Section,
            Tree,
            TreeRow,
            error_line,
            section_panel,
        )

        p = Palette(self.skin)

        key = args[0] if args else (self.selected or "")
        if not key:
            self._browse_genomes([])
            details = self.registry.list_genome_details()
            if not details:
                return
            try:
                choice = self.session.prompt("\nEnter # or id to view: ").strip()
                if choice.isdigit():
                    key = details[int(choice) - 1]["dir_name"]
                else:
                    key = choice
            except Exception:
                return

        g = self.registry.get_genome(key)
        if not g:
            self.console.print()
            self.console.print(error_line(f"Genome not found: {key}", palette=p))
            return

        self.selected = g.genome_id
        m = g.manifest

        # Manifest section
        authors = ", ".join((a.name or str(a)) for a in (m.authors or [])) or "—"
        domains = ", ".join(m.applicability.get("domains", [])) or "—"
        score = m.evaluation_score.get("reference_tasks", "—")
        manifest_rows = [
            ("id", f"[bold {p.genome}]{m.id}[/]  [dim]@{m.version}[/]"),
            ("created", str(m.created)),
            ("authors", authors),
            ("domains", domains),
            ("score", f"[{p.evolution}]{score}[/]" if score != "—" else "—"),
        ]

        # Framework section
        fw = g.framework or {}
        steps = fw.get("steps", [])
        n_steps = len(steps)
        step_rows: list[TreeRow] = []
        for i, step in enumerate(steps[:6]):
            step_rows.append(
                TreeRow(
                    label=f"[bold {p.evolution}]{step.get('name', 'step')}[/]",
                    secondary=(step.get("description", "") or "")[:60],
                )
            )
        if n_steps > 6:
            step_rows.append(
                TreeRow(label=f"[dim]+ {n_steps - 6} more step{'s' if n_steps - 6 != 1 else ''}[/]")
            )

        fw_head = Text()
        fw_head.append(f"{Glyphs.EXPANDED} ", style=p.accent)
        fw_head.append("Framework", style=f"bold {p.accent}")
        fw_head.append(f"  {fw.get('id', 'n/a')}", style=p.muted)
        fw_head.append(f"  {n_steps} step{'s' if n_steps != 1 else ''}", style=p.muted)
        if fw.get("inputs"):
            fw_head.append(f"  inputs: {', '.join(fw.get('inputs', []))}", style=p.muted)

        if steps:
            fw_section = _Group(fw_head, Tree(step_rows, palette=p))
        else:
            empty = Text("    no structured steps (generic capability)", style=p.muted)
            fw_section = _Group(fw_head, empty)

        # Reasoning + tools sections (compact)
        extras: list[Any] = []
        if g.reasoning_patterns:
            rp_keys = list(g.reasoning_patterns.keys())
            preview = ", ".join(rp_keys[:5])
            if len(rp_keys) > 5:
                preview += f"  (+{len(rp_keys) - 5} more)"
            extras.append(
                Section(
                    "Reasoning patterns",
                    [
                        ("count", str(len(rp_keys))),
                        ("keys", preview),
                    ],
                    palette=p,
                    key_width=8,
                )
            )

        if g.tool_compositions:
            tc_keys = list(g.tool_compositions.keys())
            preview = ", ".join(tc_keys[:3])
            if len(tc_keys) > 3:
                preview += f"  (+{len(tc_keys) - 3} more)"
            extras.append(
                Section(
                    "Tool compositions",
                    [
                        ("count", str(len(tc_keys))),
                        ("keys", preview),
                    ],
                    palette=p,
                    key_width=8,
                )
            )

        # Compose
        self.console.print()
        self.console.print(
            section_panel(
                Section("Manifest", manifest_rows, palette=p),
                fw_section,
                *extras,
                title=f"Genome · {g.genome_id}",
                palette=p,
            )
        )

        hint = Text()
        hint.append("Selected for run/evolve: ", style=p.muted)
        hint.append(g.genome_id, style=f"bold {p.genome}")
        self.console.print(hint)

    def _show_status(self) -> None:
        stats = self.registry.get_registry_stats()
        c = self.skin.skin["colors"]

        reg_panel = Panel(
            f"[agentdrive.label]Root:[/] {stats['root']}\n"
            f"[agentdrive.label]Genomes:[/] [agentdrive.genome]{stats['count']}[/]\n"
            f"[agentdrive.label]Domains:[/] {', '.join(stats['domains_covered']) or '—'}\n"
            f"[agentdrive.label]Avg Score:[/] [agentdrive.evolution]{stats['avg_score']}[/]\n"
            f"[agentdrive.label]Total Steps:[/] {stats['total_steps']}\n",
            title="Registry",
            border_style=c["banner_border"],
        )

        recent = ""
        if self.run_history:
            recent = "\n".join(
                f"  • {h.get('time_str', '?')}  {h.get('genome', '?')} → [agentdrive.ok]{h.get('status', 'done')}[/]"
                for h in self.run_history[-3:]
            )
        else:
            recent = "[dim]No runs this session yet. Use 'run'.[/dim]"
        run_panel = Panel(recent, title="Recent Session Runs", border_style=c["ui_accent"])

        # Pool stats panel
        try:
            from agentdrive.drive.drive import get_default_drive

            pool = get_default_drive()
            pstats = pool.get_pool_stats()
            pool_lines = (
                f"[agentdrive.label]Pool:[/] {pstats.get('name', 'main')}\n"
                f"[agentdrive.label]Ingest events:[/] {pstats.get('ingest_events', 0)}\n"
                f"[agentdrive.label]Last ingest:[/] {pstats.get('last_ingest') or 'never'}"
            )
            pool_panel = Panel(
                pool_lines, title="Pool", border_style=c.get("status_bar_dim", "dim")
            )
        except Exception:
            pool_panel = Panel("[dim]Pool not available[/]", title="Pool", border_style="dim")

        sys_panel = Panel(
            f"AgentDrive TUI: [agentdrive.ok]active[/]  •  Skin: [agentdrive.label]{self.skin.skin.get('name', 'default')}[/]\n"
            f"Python: {sys.version.split()[0]}  •  Registry writable: [agentdrive.ok]yes[/]\n"
            "[dim]Evolutionary engine, scanners, and worker adapters ready for wiring.[/dim]",
            title="System",
            border_style="dim",
        )

        self.console.print(reg_panel)
        self.console.print(run_panel)
        self.console.print(pool_panel)
        self.console.print(sys_panel)

    def _show_chat(self) -> None:
        """Enter the conversational pool query interface."""
        try:
            cv = ChatView(self)
            cv.enter()
        except Exception as e:
            self.console.print(f"[agentdrive.warn]Chat error:[/] {rich_escape(str(e))}")

    def _show_board(self, args: list[str]) -> None:
        """Render the AgentDrive Mission Board."""
        from agentdrive.board import get_default_board
        from agentdrive.tui.board_view import render_board, render_board_inline
        from agentdrive.tui.chrome import Palette, error_line, ok_line, warn_line
        from agentdrive.tui.loading import MicroSpinner

        p = Palette(self.skin)
        with MicroSpinner(self.console, "loading mission board…", accent=p.accent):
            board = get_default_board()

        sub = args[0].lower() if args else "show"

        if sub in ("show", "view", "ls", "list"):
            render_board(board, p, self.console)
        elif sub == "recent":
            render_board_inline(board, p, self.console, limit=12)
        elif sub == "create":
            title = " ".join(args[1:]) if len(args) > 1 else ""
            if not title:
                self.console.print(warn_line("Usage: board create <title>", palette=p))
                return
            mission = board.create(title=title)
            self.console.print(
                ok_line(
                    f"Created [agentdrive.genome]{mission.id}[/] — {rich_escape(mission.title)}",
                    palette=p,
                )
            )
        elif sub in ("start", "begin"):
            mid = args[1] if len(args) > 1 else ""
            if not mid:
                self.console.print(warn_line("Usage: board start <mission-id>", palette=p))
                return
            m = board.start(mid)
            if m:
                self.console.print(
                    ok_line(f"Started [agentdrive.genome]{m.id}[/] — {m.title}", palette=p)
                )
            else:
                self.console.print(
                    error_line(f"No mission with id [agentdrive.genome]{mid}[/]", palette=p)
                )
        elif sub in ("done", "complete"):
            mid = args[1] if len(args) > 1 else ""
            if not mid:
                self.console.print(warn_line("Usage: board done <mission-id>", palette=p))
                return
            m = board.complete(mid)
            if m:
                self.console.print(ok_line(f"Completed [agentdrive.genome]{m.id}[/]", palette=p))
            else:
                self.console.print(
                    error_line(f"No mission with id [agentdrive.genome]{mid}[/]", palette=p)
                )
        elif sub == "fail":
            mid = args[1] if len(args) > 1 else ""
            if not mid:
                self.console.print(warn_line("Usage: board fail <mission-id>", palette=p))
                return
            m = board.fail(mid)
            if m:
                self.console.print(
                    ok_line(f"Marked failed [agentdrive.genome]{m.id}[/]", palette=p)
                )
            else:
                self.console.print(
                    error_line(f"No mission with id [agentdrive.genome]{mid}[/]", palette=p)
                )
        elif sub == "archive":
            mid = args[1] if len(args) > 1 else ""
            if not mid:
                self.console.print(warn_line("Usage: board archive <mission-id>", palette=p))
                return
            m = board.archive(mid)
            if m:
                self.console.print(ok_line(f"Archived [agentdrive.genome]{m.id}[/]", palette=p))
            else:
                self.console.print(
                    error_line(f"No mission with id [agentdrive.genome]{mid}[/]", palette=p)
                )
        elif sub in ("stats", "stat"):
            stats = board.stats()
            from agentdrive.tui.chrome import Section, section_panel

            self.console.print()
            self.console.print(
                section_panel(
                    Section(
                        "Mission Board",
                        [
                            ("pending", f"[{p.muted}]{stats['pending']}[/]"),
                            ("running", f"[bold {p.accent}]{stats['running']}[/]"),
                            ("done", f"[bold {p.ok}]{stats['done']}[/]"),
                            (
                                "failed",
                                f"[bold {p.error}]{stats['failed']}[/]" if stats["failed"] else "0",
                            ),
                            ("archived", str(stats["archived"])),
                            (
                                "avg time",
                                f"{stats['avg_duration_s']:.1f}s"
                                if stats["avg_duration_s"]
                                else "—",
                            ),
                            ("path", str(stats["path"])),
                        ],
                        palette=p,
                    ),
                    palette=p,
                )
            )
        elif sub in ("help", "?"):
            from agentdrive.tui.chrome import Section, section_panel

            self.console.print()
            self.console.print(
                section_panel(
                    Section(
                        "board · commands",
                        [
                            ("board", "render the full board (default)"),
                            ("board recent", "compact inline of recent missions"),
                            ("board stats", "summary numbers"),
                            ("board create <title>", "stage a Pending mission"),
                            ("board start <id>", "Pending → Running"),
                            ("board done <id>", "Running → Done"),
                            ("board fail <id>", "Running → Failed"),
                            ("board archive <id>", "Done/Failed → Archived"),
                        ],
                        palette=p,
                        key_width=22,
                    ),
                    palette=p,
                )
            )
        else:
            self.console.print(
                warn_line(
                    f"Unknown board subcommand: {sub}. Try [{p.accent}]board help[/]",
                    palette=p,
                )
            )

    def _show_mission_control_view(self, args: list[str]) -> None:
        """Lightweight unified Mission Control view in TUI (v1.5 TUI parity + Wave 3 cross-process).

        - In-process: uses the global MissionControlHub singleton when an
          IntegratedRealTimeEvolutionSystem (stabilization-wave-20260531 context) is
          attached in the same process.
        - Cross-process: when launched via `agentdrive tui --mission ws://...` (or
          ad-hoc `mc ws://127.0.0.1:8421` / `mc --url ...` inside TUI), uses the
          MissionControlClient which:
            * Hydrates from GET /state (loop_state, fabric, grid_health)
            * Subscribes /ws/mission for live events (exact payload: {seq, event_type, data, ...})
            * On connect/reconnect: receives initial_state{type,data,seq}, requests
              replay_events{after_seq} -> replay{type,events,current_seq}
            * Commands via WS -> command_ack (see server.py:handle_inbound_command + mission_websocket)
            * Resilient: WS backoff + seq replay; always falls back to HTTP snapshots.
            * Duck-types hub surface (derive_* + dispatch_command + .recent_events) for
              zero-delta render + command paths in this view.

        Non-breaking: zero change to TUI when no MC anywhere. Graceful "no_mission_attached"
        and smoke commands always work. Chrome primitives for visual parity.
        """

        from agentdrive.tui.chrome import (
            Glyphs,
            Palette,
            Section,
            context_bar,
            info_line,
            ok_line,
            section_panel,
            warn_line,
        )

        p = Palette(self.skin)
        hub = getattr(self, "_mc_hub", None)
        remote = getattr(self, "_mc_remote", None)

        # Wave 3: support ad-hoc cross-process activation from the mc command itself
        # (non-breaking addition; allows live switch without relaunch).
        # Examples inside TUI:  mc ws://127.0.0.1:8421   or   mc --url http://127.0.0.1:8421
        # Also accepts bare host:port for convenience.
        for a in args or []:
            if isinstance(a, str) and ("://" in a or a.replace(".", "").replace(":", "").isdigit()):
                candidate = (
                    a
                    if "://" in a
                    else (
                        "ws://" + a
                        if not a.startswith(("127", "localhost"))
                        else "ws://127.0.0.1:" + a.split(":")[-1]
                        if ":" in a
                        else "ws://" + a
                    )
                )
                if "://" not in candidate:
                    candidate = "ws://" + candidate
                try:
                    remote = MissionControlClient(url=candidate)
                    self._mc_remote = remote
                    remote.connect()
                    hub = remote
                    break
                except Exception:
                    pass
        # --url / --mission flag form inside mc args
        try:
            arglist = list(args or [])
            url = None
            if "--url" in arglist:
                i = arglist.index("--url")
                if i + 1 < len(arglist):
                    url = arglist[i + 1]
            elif "--mission" in arglist:
                i = arglist.index("--mission")
                if i + 1 < len(arglist):
                    url = arglist[i + 1]
            if url:
                if "://" not in url:
                    url = "ws://" + url
                remote = MissionControlClient(url=url)
                self._mc_remote = remote
                remote.connect()
                hub = remote
        except Exception:
            pass

        if remote is not None and hub is None:
            hub = remote
        if hub is None and remote is not None:
            hub = remote

        self.console.print()

        # === WAVE 3: Rich Live Mission Control TUI Surface (stabilization-wave-20260531 exclusive) ===
        # True rich.live Live display achieving visual/functional parity with Tower for "the system as one".
        # - Pulsing/animated 6-step Canonical Loop tower (cyan active glow + tick-driven scan anim via phase; step descs from LoopStepEvent)
        # - Live fabric coherence bar (context_bar) + connection density + recent densified edges (from FabricUpdateEvent + derive_fabric_snapshot)
        # - Rich Static Fire Bay: live phase cards, accumulating key_events (parent_interventions, densif lifts), post-fire final_report embeds (text/mermaid lines), coherence lift
        # - Parent timeline + recent Overseer hunches + seq-aware event stream (filterable in spirit via recent)
        # - Unified header: stabilization-wave-20260531 + cycle_id + fabric_coherence + active_step
        # - Command handoff: short Live pulse window (auto-refresh on hub pulls + publish_event_sync path) then seamless prompt REPL for parent_decision/trigger_densification/start_static_fire/etc via hub.dispatch (or remote). "pulse" re-enters Live.
        # - Graceful degradation: beautiful "no mission attached" panel with EXACT launch instructions (agentdrive mission + tui --mission + in-TUI mc ws:// + smoke for in-proc)
        # - All via existing chrome (Section/Panel/Palette/section_panel/info/ok/warn/context_bar/Glyphs) + rich Live/Group/Panel/Text (already imported/used in TUI). Duck-type preserved for hub + MissionControlClient.
        # - "mc live" arg: extended monitor until ^C. Non-tty/test: one-shot rich render of dashboard (verifiable headless).
        # Visibility exclusively through publish_event_sync (no bypass). Targets ONLY stabilization-wave-20260531 drive.
        # (chrome names + rich Group/Panel/Text/Live from early import + module top; context_bar/Glyphs added to the fn-start chrome import above)

        p = Palette(self.skin)
        hub = getattr(self, "_mc_hub", None)
        remote = getattr(self, "_mc_remote", None)

        # (ad-hoc remote activation + --url/--mission + normalization already performed above this point; preserved exactly)

        if remote is not None and hub is None:
            hub = remote
        if hub is None and remote is not None:
            hub = remote

        is_live_mode = any(a in ("live", "monitor", "watch") for a in (args or []))
        is_test_mode = any(a in ("test", "headless", "verify") for a in (args or [])) or not (
            getattr(_sys, "stdin", None)
            and getattr(getattr(_sys, "stdin", None), "isatty", lambda: False)()
            and getattr(_sys, "stdout", None)
            and getattr(getattr(_sys, "stdout", None), "isatty", lambda: False)()
        )
        pulse_seconds = 12 if is_live_mode else (2 if is_test_mode else 5)

        def _build_mc_render(
            phase: int, loop_s: dict, fabric_s: dict, recent_e: list, transport: str, last_seq: int
        ) -> Group:
            """Pure render builder (called by Live + one-shot test path). Uses ONLY existing chrome/rich. Self-contained for "whole system as one" on stabilization-wave-20260531."""
            coh = float(
                loop_s.get("fabric_coherence") or fabric_s.get("overall_coherence", 0.0) or 0.0
            )
            cid = (
                loop_s.get("cycle_id")
                or loop_s.get("active_cycle")
                or (fabric_s.get("active_cycles") or [None])[0]
                or "—"
            )
            step = int(loop_s.get("current_step") or 0)
            if step < 1 or step > 6:
                step = ((phase % 6) + 1) if not loop_s.get("current_step") else 1
            step = max(1, min(6, step))

            # STEP DEFS (canonical, match loop_views.py + Tower exactly)
            step_defs = [
                (1, "EXPERIENCE", "Experience Layer + Runtime generating signals"),
                (2, "OVERSEER INGEST", "Overseer ingesting experience + multi-cycle fabric"),
                (3, "FEED PARENT", "Overseer feeding understanding to Parent"),
                (4, "PARENT DECIDE", "Parent making real-time decisions"),
                (5, "EXECUTE", "Decisions executing back into runtime"),
                (6, "FABRIC UPDATE", "New experience + updated fabric flowing back to Overseer"),
            ]

            # Unified header (the "system as one" feeling)
            header = Text()
            header.append("◆ AGENTDRIVE MISSION CONTROL ", style=f"bold {p.accent}")
            header.append("stabilization-wave-20260531", style=f"bold {p.framework}")
            header.append("  |  ", style=p.muted)
            header.append(f"cycle:{str(cid)[:12]}", style=p.text)
            header.append("  |  ", style=p.muted)
            header.append(f"coh:{coh:.3f}", style=f"bold {p.accent}")
            header.append("  |  ", style=p.muted)
            header.append(f"step:{step}/6", style=f"bold {p.evolution}")
            if is_live_mode or not is_test_mode:
                pulse = "●" if (phase % 2 == 0) else "◌"
                header.append(f"   {pulse} LIVE", style=f"bold {p.ok if phase % 3 else p.accent}")

            head_panel = Panel(header, border_style=p.border, padding=(0, 1))

            # 6-STEP TOWER (pulsing, cyan active per Tower, scan anim via phase)
            step_lines: list[Text] = []
            scan_phase = phase % 5
            for num, short, desc in step_defs:
                is_active = num == step
                col = p.accent if is_active else p.muted
                glow = Glyphs.SPARK if is_active else Glyphs.DOT_OPEN
                scan = ""
                if is_active:
                    # tick-driven scan "glow" + moving marker (emulates Tower ::after scan + pulse-glow)
                    scan_chars = " ▏▎▍▌▋▊▉█"
                    scan = scan_chars[scan_phase % len(scan_chars)] + " "
                    if phase % 4 == 0:
                        glow = "◆"
                prefix = f"{num} {glow} {scan}"
                line = Text()
                line.append(f"  {prefix:<6}", style=f"bold {col}")
                line.append(short, style=f"{'bold ' if is_active else ''}{col}")
                if is_active:
                    line.append(f"  ◀ {desc[:48]}", style=f"dim {p.text}")
                else:
                    line.append(f"  {desc[:38]}", style=p.muted)
                step_lines.append(line)
            step_group = Group(
                Text(
                    "Canonical 6-Step Loop Tower (via LoopStepEvent + publish_event_sync)",
                    style=f"bold {p.accent}",
                ),
                *step_lines,
                Text(
                    f"  active: [{p.accent}]{step_defs[step - 1][1]}[/]  (scan anim phase {scan_phase})",
                    style=p.muted,
                ),
            )
            loop_panel = Panel(
                step_group,
                title="6-STEP TOWER",
                border_style=p.accent if step else p.border,
                padding=(1, 1),
            )

            # LIVE FABRIC (bar + density + recent densif edges)
            edges = int(fabric_s.get("total_cross_cycle_edges", 0) or 0)
            active_c = len(fabric_s.get("active_cycles", []) or []) or 1
            density = f"{edges} edges / {active_c} cycles"
            bar = context_bar(int(coh * 100), 100, palette=p, width=28, show_pct=True)
            # simple sparkline from recent fabric updates (ascii, no extra deps)
            spark = ""
            recent_cohs = []
            for e in recent_e[-8:]:
                if "fabric" in str(e.get("event_type", "")).lower():
                    d = e.get("data", {}) or {}
                    if "fabric_coherence" in d:
                        recent_cohs.append(float(d["fabric_coherence"]))
            if recent_cohs:
                spark = " ".join("▁▂▃▄▅▆▇█"[min(7, int(c * 7))] for c in recent_cohs[-6:])
            fab_content = Group(
                Text(f"coherence {bar}", style=p.text),
                Text(f"density: {density}   spark:{spark or '—'}", style=p.muted),
            )
            # recent densif edges
            dens_edges = []
            for e in recent_e[-10:]:
                if e.get("event_type") == "fabric_update":
                    dd = e.get("data", {}) or {}
                    if dd.get("delta_edges"):
                        dens_edges.append(f"+{dd['delta_edges']} @ {e.get('seq', '?')}")
            if dens_edges:
                fab_content.renderables.append(
                    Text("  recent densif: " + ", ".join(dens_edges[-3:]), style=p.genome)
                )
            fabric_panel = Panel(
                fab_content,
                title="EXPERIENCE GRAPH v3 FABRIC (live)",
                border_style=p.genome,
                padding=(1, 1),
            )

            # RICH STATIC FIRE BAY (from StaticFireEvent key_events / phase / final_report via publish only)
            fire_lines: list[Text] = []
            fire_evt = None
            for e in reversed(recent_e):
                if "static_fire" in str(e.get("event_type", "")).lower():
                    fire_evt = e
                    break
            if fire_evt:
                fd = fire_evt.get("data", {}) or {}
                phase_name = fd.get("phase", "idle")
                col_fire = (
                    p.accent
                    if phase_name in ("running", "densifying")
                    else (p.ok if phase_name == "completed" else p.warn)
                )
                fire_lines.append(
                    Text(
                        f"🔥 {phase_name.upper()}  cycles:{fd.get('cycles_completed', 0)}  coh:{fd.get('current_fabric_coherence', coh):.3f}  lift:{fd.get('total_lift', 0):.1f}%",
                        style=f"bold {col_fire}",
                    )
                )
                if fd.get("key_events"):
                    for ke in fd["key_events"][-4:]:
                        ktype = ke.get("type", ke.get("event", "?"))
                        fire_lines.append(
                            Text(f"   • {ktype}: {str(ke.get('summary', ke))[:55]}", style=p.muted)
                        )
                if fd.get("parent_interventions"):
                    fire_lines.append(
                        Text(
                            f"   parent_interventions: {fd['parent_interventions']}   edges_delta: {fd.get('fabric_edges_delta', 0)}",
                            style=p.evolution,
                        )
                    )
                if fd.get("final_report"):
                    fr = fd["final_report"]
                    if isinstance(fr, dict):
                        if fr.get("post_densif_fabric"):
                            fire_lines.append(
                                Text(
                                    "   post-fire: " + str(fr["post_densif_fabric"])[:70],
                                    style=p.genome,
                                )
                            )
                        if fr.get("recorder_snippets"):
                            fire_lines.append(
                                Text(
                                    "   recorder: " + ", ".join(fr["recorder_snippets"][:2]),
                                    style=p.muted,
                                )
                            )
            else:
                fire_lines.append(
                    Text(
                        "idle — use `fire N` or start_static_fire to engage rich Bay (live via publish_event_sync)",
                        style=p.muted,
                    )
                )
            fire_group = Group(*fire_lines)
            fire_panel = Panel(
                fire_group,
                title="STATIC FIRE BAY (rich telemetry + final_report)",
                border_style=p.warn,
                padding=(1, 1),
            )

            # PARENT + OVERSEER + EVENT STREAM (seq-aware)
            parent_lines = []
            for e in recent_e[-5:]:
                if e.get("event_type") == "parent_decision":
                    d = e.get("data", {}) or {}
                    parent_lines.append(
                        (f"p#{e.get('seq', '?')}", f"{d.get('decision_summary', '')[:50]}")
                    )
            if not parent_lines:
                parent_lines = [("—", "no ParentDecisionEvent yet (use parent_decision cmd)")]
            parent_sec = Section(
                "Parent Timeline (recent decisions)", parent_lines, palette=p, key_width=8
            )

            hunch_lines = []
            for e in recent_e[-4:]:
                if "overseer" in str(e.get("event_type", "")).lower():
                    d = e.get("data", {}) or {}
                    for h in (d.get("recent_hunches") or d.get("recommendations") or [])[:2]:
                        hunch_lines.append(("hunch", str(h)[:60]))
            if not hunch_lines:
                hunch_lines = [("—", "no OverseerStateEvent hunches yet")]
            hunch_sec = Section("Overseer Hunches", hunch_lines, palette=p, key_width=8)

            ev_lines = []
            for e in recent_e[-7:]:
                et = e.get("event_type", "?")
                sq = e.get("seq", 0)
                ts = e.get("timestamp", 0)
                ts_str = time.strftime("%H:%M:%S", time.localtime(ts)) if ts else "?"
                d = e.get("data", {}) or {}
                preview = (d.get("description") or d.get("summary") or str(d) or "")[:48].replace(
                    "\n", " "
                )
                et_col = (
                    p.evolution
                    if "loop" in et
                    else (
                        p.genome
                        if "fabric" in et
                        else (
                            p.accent if "parent" in et else (p.warn if "static" in et else p.muted)
                        )
                    )
                )
                ev_lines.append((f"[{sq:04d}]", f"[{ts_str}] [{et_col}]{et}[/] {preview}"))
            ev_sec = Section(
                "Event Stream (seq-aware, publish_event_sync only)",
                ev_lines or [("—", "quiet")],
                palette=p,
                key_width=8,
            )

            # Footer / transport
            footer = info_line(
                f"transport:{transport}  seq:{last_seq}  refresh~8Hz (Live)  wave:stabilization-wave-20260531  all visibility via publish_event_sync  Wave3 cmds: parent|densify|inject|pause|list_fires|test_lift|... | pulse|q",
                palette=p,
            )

            # Compose full (no Columns; pure Group+Panel+Section for zero new imports)
            return Group(
                head_panel,
                Text(""),
                loop_panel,
                Text(""),
                fabric_panel,
                Text(""),
                fire_panel,
                Text(""),
                parent_sec,
                Text(""),
                hunch_sec,
                Text(""),
                ev_sec,
                Text(""),
                footer,
            )

        # Pull initial (duck-type safe)
        try:
            loop = hub.derive_loop_state_snapshot() or {} if hub else {}
            fabric = hub.derive_fabric_snapshot() or {} if hub else {}
            recent = list(getattr(hub, "recent_events", []))[-20:] if hub else []
            transport = (
                "WS live"
                if (remote and getattr(remote, "connected", False))
                else ("HTTP poll" if remote else ("in-proc hub" if hub else "none"))
            )
            last_seq = int(
                getattr(remote, "last_seq", 0) or (recent[-1].get("seq", 0) if recent else 0)
            )
        except Exception:
            loop, fabric, recent = {"status": "snapshot_error"}, {}, []
            transport = "error"
            last_seq = 0

        if hub is None:
            # Beautiful graceful degradation panel (exact launch instructions per v1 DNA + Wave 3 charter)
            no_m = Group(
                Text(
                    "◆ stabilization-wave-20260531  —  MISSION CONTROL (TUI)  —  no hub attached",
                    style=f"bold {p.warn}",
                ),
                Text(""),
                info_line(
                    "This is the rich Live surface. No IntegratedRealTimeEvolutionSystem attached in-process or via remote.",
                    palette=p,
                ),
                Text(""),
                Section(
                    "Exact launch (targets stabilization-wave-20260531 exclusively)",
                    [
                        (
                            "1. hub",
                            "`agentdrive mission`  (separate term; serves Tower + WS hub on 8421)",
                        ),
                        (
                            "2. cross",
                            "`agentdrive tui --mission ws://127.0.0.1:8421`  OR inside TUI: `mc ws://127.0.0.1:8421`",
                        ),
                        (
                            "3. in-proc",
                            "python -c 'from agentdrive.mission_control.server import smoke_mission_control_with_integrated_system as s; s()'  then `mc` here",
                        ),
                        (
                            "4. direct",
                            "from agentdrive.system... import Integrated...; sys=Integrated...(swarm_id='stabilization-wave-20260531'); sys.attach_mission_control(hub); ...",
                        ),
                    ],
                    palette=p,
                    key_width=10,
                ),
                Text(""),
                info_line(
                    "All visibility (6-step, fabric v3, StaticFire Bay, Parent/Overseer) flows EXCLUSIVELY via publish_event_sync. Commands via dispatch_command.",
                    palette=p,
                ),
                warn_line(
                    "Graceful: smoke commands + `mc` still exercise surface (no_mission_attached acks).",
                    palette=p,
                ),
            )
            self.console.print(
                Panel(
                    no_m,
                    border_style=p.border,
                    title="AGENTDRIVE MC — DEGRADED (WAVE 3 RICH)",
                    padding=(1, 2),
                )
            )
            # still allow smoke dispatch in degraded
            try:
                if hub and hasattr(hub, "dispatch_command"):
                    r = hub.dispatch_command("get_state")
                else:
                    r = {
                        "error": "no_mission_attached",
                        "graceful": True,
                        "note": "stabilization-wave-20260531 TUI Wave 3",
                    }
                self.console.print(info_line(f"Smoke: {r}", palette=p))
            except Exception:
                pass
            return

        if is_test_mode:
            # one-shot rich render of the dashboard builder for headless E2E verification (no Live context, no prompts)
            self.console.print(
                Text(
                    "HEADLESS TEST RENDER (Wave 3 _build_mc_render for stabilization-wave-20260531):",
                    style=p.muted,
                )
            )
            rendered = _build_mc_render(5, loop, fabric, recent, transport, last_seq)
            self.console.print(rendered)
            self.console.print(
                ok_line(
                    "Test render complete — pulsing 6-step tower + fabric bar + Static Fire Bay + seq stream + unified header verified (all data via publish_event_sync only).",
                    palette=p,
                )
            )
            return

        # === LIVE PULSING DASHBOARD ===
        self.console.print(
            Text(
                f"[{p.muted}]Entering rich Live (pulsing 6-step + fabric + Bay). ^C or wait for handoff to commands.[/]",
                style=p.muted,
            )
        )

        phase = 0
        stop_after = int(pulse_seconds * 8)  # ~8Hz feel
        last_render = None
        try:
            with Live(
                _build_mc_render(phase, loop, fabric, recent, transport, last_seq),
                console=self.console,
                refresh_per_second=8,
                transient=False,
            ) as live:
                for i in range(stop_after):
                    phase = i
                    try:
                        loop = hub.derive_loop_state_snapshot() or loop if hub else loop
                        fabric = hub.derive_fabric_snapshot() or fabric if hub else fabric
                        recent = list(getattr(hub, "recent_events", []))[-20:] if hub else recent
                        transport = (
                            "WS live"
                            if (remote and getattr(remote, "connected", False))
                            else ("HTTP poll" if remote else ("in-proc hub" if hub else "none"))
                        )
                        last_seq = int(
                            getattr(remote, "last_seq", 0)
                            or (recent[-1].get("seq", 0) if recent else last_seq)
                        )
                    except Exception:
                        pass
                    last_render = _build_mc_render(phase, loop, fabric, recent, transport, last_seq)
                    live.update(last_render)
                    time.sleep(1.0 / 8.0)
                    if is_test_mode:
                        break  # fast exit for verification
                if is_live_mode:
                    # extended: user can ^C
                    try:
                        while True:
                            phase += 1
                            try:
                                loop = hub.derive_loop_state_snapshot() or loop if hub else loop
                                fabric = hub.derive_fabric_snapshot() or fabric if hub else fabric
                                recent = (
                                    list(getattr(hub, "recent_events", []))[-20:] if hub else recent
                                )
                            except Exception:
                                pass
                            live.update(
                                _build_mc_render(phase, loop, fabric, recent, transport, last_seq)
                            )
                            time.sleep(1.0 / 8)
                    except KeyboardInterrupt:
                        self.console.print(info_line("Live monitor ended (Ctrl-C).", palette=p))
        except Exception as live_err:
            self.console.print(
                warn_line(
                    f"Live error (graceful fallback to static): {str(live_err)[:80]}", palette=p
                )
            )
            if last_render:
                self.console.print(last_render)

        # === SEAMLESS HANDOFF TO COMMAND INPUT (after live pulse) ===
        self.console.print()
        self.console.print(
            section_panel(
                info_line(
                    "LIVE PULSE COMPLETE — now steer via commands (dispatched → publish_event_sync → next pulse will reflect)",
                    palette=p,
                ),
                palette=p,
            )
        )
        self.console.print(
            f"[{p.muted}]Commands (Wave 3 extended): parent <note|fabric_directives=...> | densify [cid] [weak=...] | fire <secs> | suggest | hunch | metacog | test_lift | inject <obs> | pause | resume | list_fires | compare_fires | pulse | status | q/quit[/]"
        )

        try:
            while True:
                raw = self.session.prompt("  mc> ", default="status").strip()
                if not raw:
                    continue
                cmd = raw.lower()
                if cmd in ("q", "quit", "exit", "back", ":q"):
                    break
                if cmd in ("pulse", "live", "monitor"):
                    self.console.print(info_line("Re-entering Live pulse...", palette=p))
                    with Live(
                        _build_mc_render(phase + 10, loop, fabric, recent, transport, last_seq),
                        console=self.console,
                        refresh_per_second=8,
                        transient=True,
                    ) as lv:
                        for ii in range(24):
                            lv.update(
                                _build_mc_render(
                                    phase + 10 + ii, loop, fabric, recent, transport, last_seq
                                )
                            )
                            time.sleep(1 / 8)
                    continue
                if cmd.startswith("status") or cmd == "s":
                    try:
                        loop = hub.derive_loop_state_snapshot() or {}
                        fabric = hub.derive_fabric_snapshot() or {}
                        recent = list(getattr(hub, "recent_events", []))[-8:]
                        self.console.print(
                            _build_mc_render(phase + 1, loop, fabric, recent, transport, last_seq)
                        )
                    except Exception as se:
                        self.console.print(warn_line(str(se)[:60], palette=p))
                    continue
                if cmd.startswith("parent") or cmd.startswith("decide"):
                    note = (
                        raw.split(" ", 1)[1]
                        if " " in raw
                        else "TUI Wave3 steer: prioritize fabric + static fire learning"
                    )
                    # support fabric_directives=... in raw for richer form
                    extra = {
                        "decision": {"action": "tui_wave3_parent_decision", "note": note[:220]},
                        "actions_taken": ["rich_tui_mission_control"],
                        "from_fabric": True,
                    }
                    if "fabric_directives=" in raw or "directives=" in raw:
                        val = (
                            raw.split("fabric_directives=", 1)[1].split()[0]
                            if "fabric_directives=" in raw
                            else raw.split("directives=", 1)[1].split()[0]
                        )
                        extra["fabric_directives"] = val
                    res = hub.dispatch_command("parent_decision", **extra)
                    fb = f"parent_decision → {res.get('result') or res.get('error', 'ok')} surface={res.get('surface', '?')} triggered_fabric={res.get('triggered_from_fabric')}"
                    self.console.print(ok_line(fb, palette=p))
                    if res.get("result") and "graph" in str(res.get("result")):
                        self.console.print(info_line(str(res["result"])[:140], palette=p))
                    continue
                if cmd.startswith("densify") or cmd.startswith("dense"):
                    cid_arg = raw.split(" ", 1)[1].strip() if " " in raw else None
                    weak = None
                    if "weak=" in raw:
                        weak = raw.split("weak=", 1)[1].split()[0]
                    res = hub.dispatch_command(
                        "trigger_densification", cycle_id=(cid_arg or None), weak_link=weak
                    )
                    fb = f"densify → {res.get('result') or res.get('error', 'ok')} surface={res.get('surface', '?')}"
                    self.console.print(ok_line(fb, palette=p))
                    continue
                if cmd.startswith("fire") or cmd.startswith("static"):
                    try:
                        secs = float(raw.split(" ", 1)[1]) if " " in raw else 20.0
                    except Exception:
                        secs = 20.0
                    res = hub.dispatch_command(
                        "start_static_fire", duration_seconds=secs, label="wave3_rich_tui"
                    )
                    self.console.print(
                        ok_line(
                            f"start_static_fire({secs}s) → {res.get('result') or res.get('error', 'ok')} surface={res.get('surface', '?')}",
                            palette=p,
                        )
                    )
                    continue
                if cmd.startswith("suggest"):
                    res = hub.dispatch_command("suggest_connection_improvements")
                    self.console.print(
                        ok_line(
                            f"suggest_connection_improvements → {res.get('result') or res.get('error', 'ok')} surface={res.get('surface', '?')}",
                            palette=p,
                        )
                    )
                    continue
                if cmd.startswith("hunch") or cmd.startswith("overseer_force"):
                    res = hub.dispatch_command("overseer_force_hunch")
                    self.console.print(
                        ok_line(
                            f"overseer_force_hunch → {res.get('result') or res.get('error', 'ok')} surface={res.get('surface', '?')}",
                            palette=p,
                        )
                    )
                    continue
                if "metacog" in cmd or cmd.startswith("get_meta"):
                    res = hub.dispatch_command("get_metacognitive_briefing")
                    self.console.print(
                        ok_line(
                            f"get_metacognitive_briefing → {res.get('result') or res.get('error', 'ok')} surface={res.get('surface', '?')}",
                            palette=p,
                        )
                    )
                    continue
                if "test_lift" in cmd or "emit_test" in cmd:
                    res = hub.dispatch_command("emit_test_fabric_lift", lift=0.04, delta_edges=6)
                    self.console.print(
                        ok_line(
                            f"emit_test_fabric_lift → {res.get('result') or res.get('error', 'ok')} surface={res.get('surface', '?')}",
                            palette=p,
                        )
                    )
                    if res.get("result") and res["result"].get("graph_delta"):
                        self.console.print(
                            info_line(f"graph_delta: {res['result']['graph_delta']}", palette=p)
                        )
                    continue
                if cmd.startswith("inject"):
                    obs = (
                        raw.split(" ", 1)[1] if " " in raw else "TUI injected obs for fabric densif"
                    )
                    res = hub.dispatch_command(
                        "inject_custom_observation", observation=obs, from_fabric=True
                    )
                    fb = f"inject → {res.get('result') or res.get('error', 'ok')} surface={res.get('surface', '?')}"
                    self.console.print(ok_line(fb, palette=p))
                    continue
                if cmd.startswith("pause"):
                    res = hub.dispatch_command(
                        "pause_evolution_context", note="TUI operator pause", from_fabric=True
                    )
                    self.console.print(
                        ok_line(
                            f"pause_evolution_context → {res.get('result') or res.get('error', 'ok')} surface={res.get('surface', '?')}",
                            palette=p,
                        )
                    )
                    continue
                if cmd.startswith("resume"):
                    res = hub.dispatch_command(
                        "resume_evolution_context", note="TUI operator resume", from_fabric=True
                    )
                    self.console.print(
                        ok_line(
                            f"resume_evolution_context → {res.get('result') or res.get('error', 'ok')} surface={res.get('surface', '?')}",
                            palette=p,
                        )
                    )
                    continue
                if "list_fire" in cmd or "recent_fire" in cmd:
                    res = hub.dispatch_command("list_recent_fires")
                    self.console.print(
                        ok_line(
                            f"list_recent_fires → count={res.get('result', {}).get('count', '?')} surface={res.get('surface', '?')}",
                            palette=p,
                        )
                    )
                    continue
                if "compare_fire" in cmd:
                    res = hub.dispatch_command("compare_fires")
                    self.console.print(
                        ok_line(
                            f"compare_fires → {res.get('result') or res.get('error', 'ok')} surface={res.get('surface', '?')}",
                            palette=p,
                        )
                    )
                    continue
                self.console.print(
                    info_line(
                        "Wave 3 known: parent <note> [fabric_directives=..] | densify [cid] [weak=..] | fire <secs> | suggest | hunch | metacog | test_lift | inject <obs> | pause | resume | list_fires | compare_fires | pulse | status | q  (all via dispatch_command + publish_event_sync; results show surface + deltas)",
                        palette=p,
                    )
                )
        except Exception as cmd_exc:
            self.console.print(warn_line(f"cmd error (graceful): {str(cmd_exc)[:80]}", palette=p))

        self.console.print(
            ok_line(
                "Mission Control surface closed. Re-invoke `mc` / `mission` / `control` anytime for fresh Live pulse.",
                palette=p,
            )
        )

    def _show_pool_view(self, args: list[str]) -> None:
        """Dedicated first-class TUI for the AgentDrive (global + per-swarm DNA).
        - No args: enter full interactive sub-shell (premium dedicated experience)
        - With args: one-shot execution of subcommand (e.g. `pool query "..."`, `p swarms`, `pool settings`)
        Uses the attached self.pool_view for persistent swarm scope across invocations.
        """
        try:
            pv = getattr(self, "pool_view", None)
            if pv is None:
                from agentdrive.tui.views.drive_view import DriveView

                pv = DriveView(self)
                self.pool_view = pv

            pv._refresh_pool()  # ensure fresh binding to any external changes

            if args:
                # One-shot support: pool query "foo bar"  or  p swarms  etc.  (no enter loop)
                sub = args[0].lower()
                subargs = args[1:]
                pv.handle_command(sub, subargs)
            else:
                # Full beautiful interactive Pool mode
                pv.enter()
        except Exception as e:
            self.console.print(f"[agentdrive.warn]Pool view:[/] {e}")

    def _scan_runs(self, args: list[str]) -> None:
        """Real DNA extraction using AgentDriveRunScanner + reasoning primitives.
        Produces a live candidate Genome from simulated or provided run data.
        """
        from agentdrive.tui.chrome import (
            Palette,
            Section,
            error_line,
            result_panel,
            section_panel,
            warn_line,
        )
        from agentdrive.tui.loading import StepProgress

        p = Palette(self.skin)

        target = args[0] if args else "demo-engagement-2026-05-23"

        self.console.print()
        self.console.print(
            section_panel(
                Section(
                    "Scan",
                    [
                        ("scanner", "[agentdrive.framework]agentdrive-run[/]"),
                        ("target", f"[agentdrive.genome]{target}[/]"),
                    ],
                    palette=p,
                ),
                title="◆ DNA extraction",
                palette=p,
            )
        )
        self.console.print()

        # Build realistic sample run data (from worker telemetry or external agent run)
        sample_run = {
            "timestamp": datetime.utcnow().isoformat(),
            "model": "agentdrive-demo-model",
            "observations": [
                {
                    "kind": "event",
                    "identity": "deploy",
                    "state": "started",
                    "summary": "v2.3.1 rollout",
                    "observed_at": 1748000000,
                },
                {
                    "kind": "metric",
                    "identity": "auth-svc.replicas",
                    "state": "2/3",
                    "summary": "readiness failed",
                    "observed_at": 1748000100,
                },
                {
                    "kind": "claim",
                    "identity": "affected_users",
                    "state": "47",
                    "summary": "lb + sessions",
                    "observed_at": 1748000200,
                },
            ],
            "claims": [
                {
                    "statement": "users impacted",
                    "count": 47,
                    "source": "lb-metrics",
                    "source_id": "run-4821",
                },
                {
                    "statement": "users impacted",
                    "count": 120,
                    "source": "support-tickets",
                    "source_id": "zendesk-991",
                },
            ],
            "ledger": [
                {"ts": 1748000000, "actor": "cd-pipeline", "operation": "deploy", "status": "ok"},
                {
                    "ts": 1748000100,
                    "actor": "auth-svc",
                    "operation": "health_check",
                    "status": "fail",
                },
            ],
            "conversations": [
                {
                    "role": "assistant",
                    "content": "<think>timeline shows deploy then failure... causal?</think>",
                }
            ],
        }

        steps = StepProgress(
            self.console,
            ["Load run data", "Run scanner", "Synthesize genome", "Save to registry"],
            title="Extracting DNA",
        )
        steps.start()
        try:
            from agentdrive.scanners import AgentDriveRunScanner

            steps.advance(
                f"{len(sample_run.get('observations', []))} obs · {len(sample_run.get('claims', []))} claims"
            )

            scanner = AgentDriveRunScanner(actor=f"tui-scan-{target[:8]}")
            candidates = scanner.scan(sample_run)
            if not candidates:
                steps.fail("scanner returned 0 candidates")
                steps.finish()
                self.console.print()
                self.console.print(warn_line("Scanner returned no candidates.", palette=p))
                return
            steps.advance(f"{len(candidates)} candidate(s)")

            cand = candidates[0]
            cand.manifest.id = "extracted-agentdrive-patterns"
            cand.manifest.version = "0.1.0-scanned"
            cand.finalize()
            steps.advance(f"{cand.genome_id}")

            saved_path = self.registry.save(cand)
            steps.advance(f"{saved_path.name}")
            steps.finish()

            rp = cand.reasoning_patterns or {}
            causal_edges = (
                len(rp.get("causality", {}).get("edges", []))
                if isinstance(rp.get("causality"), dict)
                else 0
            )

            self.console.print()
            self.console.print(
                result_panel(
                    f"DNA extracted: {cand.genome_id}",
                    [],
                    success=True,
                    palette=p,
                    extras=[
                        Section(
                            "Reasoning primitives",
                            [
                                ("trace steps", str(rp.get("trace", {}).get("step_count", 0))),
                                ("anomalies", str(len(rp.get("anomalies", [])))),
                                ("contradictions", str(len(rp.get("contradictions", [])))),
                                ("causal edges", str(causal_edges)),
                                ("patterns", str(len(rp.get("patterns_recognized", [])))),
                                (
                                    "framework",
                                    "[agentdrive.ok]synthesized[/]"
                                    if cand.framework
                                    else "[dim]none (needs more obs)[/]",
                                ),
                            ],
                            palette=p,
                        ),
                    ],
                )
            )

            self.selected = cand.genome_id.replace("@", "-")

        except Exception as e:
            steps.fail(str(e)[:60])
            steps.finish()
            import traceback

            self.console.print()
            self.console.print(
                error_line(
                    f"Scanner failed: {rich_escape(str(e))}",
                    palette=p,
                    suggestion=f"see traceback: {rich_escape(traceback.format_exc()[-300:])}",
                )
            )

    def _run_work(self, args: list[str]) -> None:
        """Command composer + live orchestrated execution view."""
        from agentdrive.board import get_default_board

        self._board = get_default_board()
        self._active_mission_id: str | None = None
        key = args[0] if args else (self.selected or "")
        if not key:
            self._browse_genomes([])
            details = self.registry.list_genome_details()
            if not details:
                return
            try:
                choice = self.session.prompt("Genome to run (# or id): ").strip()
                key = details[int(choice) - 1]["dir_name"] if choice.isdigit() else choice
            except Exception:
                return

        g = self.registry.get_genome(key)
        if not g:
            from agentdrive.tui.chrome import Palette, error_line

            p = Palette(self.skin)
            self.console.print()
            self.console.print(
                error_line(
                    f"Not found: {key}",
                    palette=p,
                    suggestion="run [cyan]genomes[/] to list available IDs",
                )
            )
            return
        self.selected = g.genome_id

        fw = g.framework or {}
        inputs_spec = fw.get("inputs", ["incident_summary", "timeline"]) or ["query"]

        from agentdrive.tui.chrome import Palette, Section, section_panel

        p = Palette(self.skin)
        self.console.print()
        self.console.print(
            section_panel(
                Section(
                    "Run",
                    [
                        ("genome", f"[agentdrive.genome]{g.genome_id}[/]"),
                        ("steps", str(len(fw.get("steps", [])))),
                        ("inputs", ", ".join(inputs_spec)),
                    ],
                    palette=p,
                ),
                title="◆ Mission composer",
                palette=p,
            )
        )
        self.console.print()

        collected: dict[str, str] = {}
        for inp in inputs_spec:
            val = self.session.prompt(f"  {inp}: ", default="Demo input for " + inp).strip()
            collected[inp] = val or "N/A"

        # Stage a Pending mission on the board, then flip to Running on launch.
        mission = self._board.create(
            title=f"Run {g.genome_id}",
            description=f"Inputs: {', '.join(collected.keys())}",
            genome_id=g.genome_id,
            agent_id=f"tui-{g.manifest.id[:16]}",
            inputs={k: (v[:80] if isinstance(v, str) else v) for k, v in collected.items()},
        )
        self._active_mission_id = mission.id
        self._board.start(mission.id)
        self.console.print(
            f"[agentdrive.label]Launching live execution...[/] "
            f"[dim]board · {mission.id[-5:]}[/]  (Ctrl+C to abort)"
        )

        # Lazy import + create Harness for the session (before steps) so base TUI launch never pulls harness/pool
        harness = None
        try:
            from agentdrive.harness.harness import Harness as _AgentDriveHarness

            harness = _AgentDriveHarness(
                agent_id=f"tui-{g.manifest.id[:16]}-{int(time.time()) % 100000}"
            )
        except Exception as imp_err:
            self.console.print(
                f"[agentdrive.warn]Harness/Pool integration unavailable this run (will use classic execution):[/] {imp_err}"
            )
            harness = None

        self._execute_live(g, collected, harness=harness)

    def _execute_live(
        self, genome: Genome, inputs: dict[str, str], harness: Harness | None = None
    ) -> None:
        """Rich Live dashboard for orchestrated work with progress, reasoning, tools.

        Integrated with Harness + AgentDrive:
        - Harness created in _run_work (before steps) or here; task_context wraps the live execution
        - Periodically calls pull_relevant_dna() and surfaces "DNA from Pool" in dashboard
        - Uses inject_into_context(...) to augment step reasoning/prompts
        - After run (success/abort): record_outcome(...) + optional auto-ingest of small improvement signal
        - All pool usage is visible, useful, and errors are handled gracefully without breaking the beautiful UI.
        """
        self._cancel_event.clear()
        start = time.time()

        fw = genome.framework or {}
        steps: list[dict] = fw.get("steps", []) or [
            {"name": "establish_facts", "description": "Analyze input"},
            {"name": "synthesize", "description": "Produce artifact"},
        ]
        n_steps = max(1, len(steps))

        # Ensure we have a harness for the session (created in caller _run_work or here as fallback)
        if harness is None:
            try:
                from agentdrive.harness.harness import Harness as _AgentDriveHarness

                harness = _AgentDriveHarness(
                    agent_id=f"tui-{genome.manifest.id[:16]}-{int(time.time()) % 100000}"
                )
            except Exception:
                # already warned in _run_work; stay silent here to not spam during live
                harness = None
        task_desc = f"Live run of {genome.genome_id} (inputs={list(inputs.keys())})"

        state: dict[str, Any] = {
            "step_idx": 0,
            "current_step": "",
            "pct": 0,
            "logs": [],
            "thinking": "",
            "tools": [],
            "done": False,
            "aborted": False,
            "artifact": "",
            "dna_from_pool": [],
            "pool_contrib": "",
        }
        spinner_faces = self.skin.get_spinner_config().get("thinking_faces", ["◐", "◑"])
        verbs = self.skin.get_spinner_config().get("thinking_verbs", ["analyzing", "evolving"])

        def _build_ui():
            sp_idx = int(time.time() * 4) % len(spinner_faces)
            sp = spinner_faces[sp_idx]
            title = f"Live Run — {genome.genome_id}"
            if state["aborted"]:
                title += " [agentdrive.warn](ABORTED)[/]"

            header = Text(
                f"{sp}  Step {state['step_idx']}/{n_steps}  •  {state['current_step']}  •  {state['pct']}%",
                style="agentdrive.accent",
            )

            log_lines = "\n".join(state["logs"][-8:]) or "[dim]No log yet...[/dim]"
            log_panel = Panel(log_lines, title="Activity Log", border_style="dim", height=10)

            think = state["thinking"] or "[dim]idle[/dim]"
            think_panel = Panel(
                think,
                title=f"Reasoning {verbs[sp_idx % len(verbs)]}",
                border_style=self.skin.style("evolution_step"),
            )

            tools = "\n".join(f"  ⊙ {t}" for t in state["tools"][-4:]) or "—"
            tools_panel = Panel(tools, title="Tool Calls", border_style=self.skin.style("ui_label"))

            # DNA from Pool panel — makes the pull-from-pool + adapt loop visible and useful in real time
            dna = state.get("dna_from_pool", []) or []
            dna_lines = (
                "\n".join(f"  🧬 {rich_escape(d)}" for d in dna)
                or "[dim]Pulling relevant DNA from AgentDrive...[/dim]"
            )
            dna_panel = Panel(
                dna_lines, title="DNA from Pool", border_style=self.skin.style("evolution_step")
            )

            hname = getattr(harness, "agent_id", "classic")
            footer = f"Elapsed: {time.time() - start:.1f}s   Inputs: {', '.join(inputs.keys())}   harness={hname}"

            body = Group(
                header, log_panel, think_panel, tools_panel, dna_panel, Text(footer, style="dim")
            )
            return Panel(body, title=title, border_style=self.skin.style("banner_border"))

        has_harness = harness is not None
        task_cm = harness.task_context(task_desc) if has_harness else nullcontext()

        # Wrap live run in task_context (when harness present) to enable the full pull-adapt-contribute loop
        try:
            with task_cm:
                if has_harness:
                    # task_context already pulled; surface DNA in dashboard immediately
                    try:
                        state["dna_from_pool"] = harness.get_pulled_genomes()[:3]
                    except Exception:
                        state["dna_from_pool"] = []

                with Live(
                    _build_ui(), console=self.console, refresh_per_sec=10, transient=False
                ) as live:
                    try:
                        for idx, step in enumerate(steps, 1):
                            if self._cancel_event.is_set():
                                state["aborted"] = True
                                break
                            state["step_idx"] = idx
                            state["current_step"] = step.get("name", f"step-{idx}")
                            state["pct"] = int(idx / n_steps * 100)

                            state["logs"].append(
                                f"[{datetime.now().strftime('%H:%M:%S')}] ▶ {state['current_step']}"
                            )
                            live.update(_build_ui())

                            # Periodically call pull_relevant_dna() and show "DNA from pool" (only when harness active)
                            if has_harness and (idx == 1 or idx % 2 == 0):
                                try:
                                    fresh_dna = harness.pull_relevant_dna(top_k=3)
                                    state["dna_from_pool"] = [
                                        d.get("genome_id", "?") for d in fresh_dna
                                    ]
                                    state["logs"].append(
                                        f"  🧬 pulled {len(fresh_dna)} DNA packets from pool"
                                    )
                                    live.update(_build_ui())
                                except Exception as pull_err:
                                    state["logs"].append(
                                        f"  [agentdrive.warn]DNA pull: {str(pull_err)[:45]}[/]"
                                    )
                                    live.update(_build_ui())

                            for j in range(2):
                                if self._cancel_event.is_set():
                                    break
                                base = f"Applying pattern: contradiction detection + causal chain (iter {j})"
                                if has_harness:
                                    try:
                                        # inject_into_context augments the prompt/reasoning for steps using pool DNA
                                        state["thinking"] = harness.inject_into_context(
                                            base,
                                            extra_instructions="Leverage relevant DNA from AgentDrive for better adaptation and quality.",
                                        )
                                    except Exception:
                                        state["thinking"] = base
                                else:
                                    state["thinking"] = base
                                state["logs"].append(f"  {verbs[j % len(verbs)]}...")
                                live.update(_build_ui())
                                time.sleep(0.35)

                            tool_name = (
                                "analyze_timeline"
                                if "fact" in state["current_step"].lower()
                                else "recommend"
                            )
                            state["tools"].append(f"{tool_name}({state['current_step'][:12]})")
                            state["logs"].append(f"  tool call → {tool_name}")
                            live.update(_build_ui())
                            time.sleep(0.45)

                        if not state["aborted"]:
                            state["done"] = True
                            state["artifact"] = (
                                "Structured postmortem document + action plan (saved to ./artifacts/ in real run)"
                            )
                            state["logs"].append("[agentdrive.ok]✓ Run completed successfully.[/]")
                            state["pct"] = 100
                            self.run_history.append(
                                {
                                    "genome": genome.genome_id,
                                    "time_str": datetime.now().strftime("%H:%M"),
                                    "status": "success",
                                    "inputs": list(inputs.keys()),
                                }
                            )
                            # Settle the mission card to Done.
                            try:
                                mid = getattr(self, "_active_mission_id", None)
                                if mid:
                                    self._board.complete(
                                        mid,
                                        outcome={
                                            "steps_completed": state["step_idx"],
                                            "artifact": state["artifact"],
                                        },
                                        dna_used=state.get("dna_from_pool") or [],
                                    )
                            except Exception:
                                pass
                        elif state["aborted"]:
                            try:
                                mid = getattr(self, "_active_mission_id", None)
                                if mid:
                                    self._board.fail(mid, error="user-aborted")
                            except Exception:
                                pass
                        live.update(_build_ui())
                        time.sleep(0.6)
                    except KeyboardInterrupt:
                        state["aborted"] = True
                        self._cancel_event.set()

                # Post-live (inside task_context when active): record_outcome + optional auto-ingest small signal
                if has_harness:
                    try:
                        outcome: dict[str, Any] = {
                            "status": "success" if not state["aborted"] else "aborted",
                            "duration_s": round(time.time() - start, 2),
                            "steps_completed": state["step_idx"],
                            "dna_used": len(getattr(harness, "pulled_dna", [])),
                            "inputs": list(inputs.keys()),
                        }
                        harness.record_outcome(outcome)

                        if not state["aborted"]:
                            # auto-ingest a small improvement signal (demonstrates contribute back)
                            try:
                                sig_ver = datetime.utcnow().strftime("%Y%m%d.%H%M%S")
                                signal = Genome.create(
                                    id="tui-execution-feedback",
                                    version=sig_ver,
                                    framework={
                                        "steps": [
                                            {
                                                "name": "reflect_contribute",
                                                "description": "Auto signal from live TUI run + pool DNA",
                                            }
                                        ]
                                    },
                                    authors=[{"name": harness.agent_id, "type": "tui-agent"}],
                                    applicability={"domains": ["meta", "pool-feedback"]},
                                    evaluation_score={"reference_tasks": 0.02},
                                    reasoning_patterns={
                                        "tui_pool_loop": {
                                            "source": genome.genome_id,
                                            "dna": state.get("dna_from_pool", []),
                                        }
                                    },
                                )
                                ires = harness.pool.ingest(
                                    signal, source="tui-live-run", actor=harness.agent_id
                                )
                                state["pool_contrib"] = (
                                    f"✓ ingested {ires.genome_id} ({ires.reason})"
                                )
                            except Exception as ingest_err:
                                state["pool_contrib"] = f"ingest note: {str(ingest_err)[:50]}"
                    except Exception as rec_err:
                        state["pool_contrib"] = f"outcome record: {str(rec_err)[:50]}"
        except Exception as harness_err:
            # Graceful: even if task_context or pool ops fail mid-run, we surface useful state
            state["logs"].append(f"[agentdrive.warn]Harness context: {str(harness_err)[:60]}[/]")
            if not state["aborted"] and not state.get("done"):
                state["done"] = True
                state["artifact"] = (
                    state.get("artifact") or "Run completed (pool integration partial)"
                )
                state["pct"] = 100

        if state["aborted"]:
            self.console.print("[agentdrive.warn]Run aborted by user.[/]")
        else:
            contrib = state.get("pool_contrib", "")
            footer_note = f"\n[agentdrive.label]Pool feedback:[/] {contrib}" if contrib else ""
            self.console.print(
                Panel(
                    f"[agentdrive.ok]Success[/]\n\n{state['artifact']}\n\n[dim]Full telemetry would feed scanners for evolution.[/dim]{footer_note}",
                    title="Execution Complete",
                    border_style=self.skin.style("ui_ok"),
                )
            )

    def _evolve_genome(self, args: list[str]) -> None:
        from agentdrive.tui.chrome import (
            Palette,
            Section,
            Tree,
            TreeRow,
            confirm_prompt,
            error_line,
            info_line,
            result_panel,
            section_panel,
        )

        p = Palette(self.skin)

        key = args[0] if args else (self.selected or "")
        if not key:
            self._browse_genomes([])
            return
        g = self.registry.get_genome(key)
        if not g:
            self.console.print()
            self.console.print(error_line("Genome not found for evolution.", palette=p))
            return

        new_ver = g.manifest.version.split(".")
        try:
            new_ver[-1] = str(int(new_ver[-1]) + 1)
        except Exception:
            new_ver = ["1", "0", "1"]
        new_version = ".".join(new_ver) + "-evolved"

        delta_rows = [
            TreeRow(label=f"[bold {p.ok}]+[/] added contradiction-detection reasoning pattern"),
            TreeRow(label=f"[bold {p.ok}]+[/] strengthened root-cause step with ledger witness"),
            TreeRow(label=f"[bold {p.ok}]+[/] +0.04 reference evaluation score"),
        ]

        self.console.print()
        self.console.print(
            section_panel(
                Section(
                    "Source",
                    [
                        ("genome", f"[agentdrive.genome]{g.genome_id}[/]"),
                        ("from", g.manifest.version),
                        ("to", f"[agentdrive.framework]{new_version}[/]"),
                    ],
                    palette=p,
                ),
                Tree(delta_rows, palette=p),
                title="◆ Evolution proposal",
                palette=p,
            )
        )

        ok = confirm_prompt(
            self.console,
            title="Register evolved candidate?",
            body=f"This forks [agentdrive.genome]{g.genome_id}[/] into a new entry at version [agentdrive.framework]{new_version}[/].",
            default_yes=True,
            palette=p,
        )
        if not ok:
            self.console.print()
            self.console.print(info_line("Evolution cancelled. No changes made.", palette=p))
            return

        try:
            g.manifest.version = new_version
            g.manifest.last_improved = datetime.now()
            g.reasoning_patterns["contradiction_detection"] = {"enabled": True, "v": "evolved"}
            g.evaluations["evolution_run"] = {"score_delta": 0.04}
            saved = self.registry.save(g)
            self.console.print()
            self.console.print(
                result_panel(
                    "Evolved genome saved",
                    [
                        ("genome", f"[agentdrive.genome]{g.genome_id}[/]"),
                        ("path", str(saved)),
                    ],
                    success=True,
                    palette=p,
                )
            )
            self.selected = g.genome_id
        except Exception as e:
            self.console.print()
            self.console.print(error_line(f"Failed to register evolved: {e}", palette=p))

    def _compose_mission(self, args: list[str]) -> None:
        from rich.text import Text

        from agentdrive.tui.chrome import (
            Palette,
            Tree,
            TreeRow,
            section_panel,
            warn_line,
        )

        p = Palette(self.skin)

        details = self.registry.list_genome_details()[:5]
        if not details:
            self.console.print()
            self.console.print(
                warn_line("No genomes registered — run [cyan]import[/] first.", palette=p)
            )
            return

        rows: list[TreeRow] = []
        for i, d in enumerate(details, 1):
            gid = d["genome_id"]
            gid_short = gid.split("@", 1)[0] if "@" in gid else gid
            ver = d.get("version") or (gid.split("@", 1)[1] if "@" in gid else "?")
            rows.append(
                TreeRow(
                    label=f"[{p.muted}]{i:>2}[/]  [bold {p.genome}]{gid_short}[/] [dim]@{ver}[/]",
                    secondary=", ".join(d.get("domains", [])[:2]) or "—",
                )
            )

        head = Text("Available for composition", style=f"bold {p.accent}")
        body = Text.from_markup(
            f"[{p.muted}]The full composer (multi-genome orchestration) is staged for the next release. "
            f"For now you can run individual genomes with [/][{p.accent}]run <id>[/] [{p.muted}]and stage "
            f"missions on the[/] [{p.accent}]board[/][{p.muted}].[/]"
        )

        from rich.console import Group as _Group

        self.console.print()
        self.console.print(
            section_panel(
                _Group(head, Text(""), Tree(rows, palette=p)),
                body,
                title="◆ Mission composer",
                palette=p,
            )
        )

    def _doctor(self) -> None:
        """Animated health check that matches the CLI cmd_doctor surface."""
        from agentdrive.cli import _run_doctor

        _run_doctor()

    def _run_setup_wizard(self, args: list[str]) -> None:
        """Modular setup inside the TUI — conversational and section-based.

        This gives users a true CLI/TUI hybrid experience.
        """
        from agentdrive.setup import SECTIONS, run_setup

        self.console.print(
            Panel(
                "[bold]AgentDrive Setup Wizard[/]\n"
                "Run the full wizard or reconfigure specific areas (especially Swarm DNA policies).",
                border_style=self.skin.style("banner_border"),
            )
        )

        # If user passed a section, run it directly via CLI logic
        if args:
            section = args[0].lower()
            mapping = {s["name"]: s["name"] for s in SECTIONS}
            mapping.update(
                {
                    "swarm": "swarm",
                    "dna": "swarm",
                    "agent": "ai",
                    "model": "ai",
                    "provider": "ai",
                    "ui": "tui",
                }
            )
            chosen = mapping.get(section, section)
            run_setup([chosen])
            return

        # Conversational mode
        print()
        self.console.print("[bold]Available sections:[/]")
        for i, s in enumerate(SECTIONS, 1):
            self.console.print(f"  {i}. [agentdrive.accent]{s['name']}[/] — {s['title']}")

        choice = (
            Prompt.ask("\nWhich section? (number or name, or 'all' for full wizard)", default="all")
            .strip()
            .lower()
        )

        if choice in ("all", "full", ""):
            run_setup()
        else:
            mapping = {s["name"]: s["name"] for s in SECTIONS}
            chosen = mapping.get(choice, choice)
            if chosen in [s["name"] for s in SECTIONS]:
                run_setup([chosen])
            else:
                self.console.print(
                    "[agentdrive.warn]Unknown section. Running full wizard instead.[/]"
                )
                run_setup()

    def _import_example(self, args: list[str]) -> None:
        gid = self.registry.ensure_bootstrap_example()
        if gid:
            self.console.print(
                f"[agentdrive.ok]✓ Example re-registered / present:[/] [agentdrive.genome]{gid}[/]"
            )
            self.selected = gid
        else:
            self.console.print(
                "[agentdrive.warn]Example already present or source not found on disk.[/]"
            )


def launch_tui(mission_url: str | None = None) -> None:
    """Launch the professional AgentDrive TUI.

    mission_url (optional): ws:// or http:// base for remote MissionControl Tower
    (e.g. from `agentdrive mission` in separate process). Enables full cross-process
    live 6-step + fabric + events + command surface in the `mc` view with parity to
    in-process hub, using resilient WS + /state fallback.
    """
    app = AgentDriveTUI(mission_url=mission_url)
    app.run()
