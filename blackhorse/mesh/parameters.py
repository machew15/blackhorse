"""
Phase 3C — Participation Policy.

Parametric governance over what a node will and will not relay.
All checks are local, fast, and require no network consensus.

Check order in should_relay():
  1. Queue size < max_queue_size            (flood protection gate)
  2. packet_size_bytes <= max_bytes_per_relay
  3. priority >= priority_threshold
  4. Hourly relay count < max_relays_per_hour
  5. Trust score >= min_trust_score
     (unless relay_unknown_nodes=True and node has no ledger entry)

No token. No blockchain. Local math only.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field

from .ledger import ContributionLedger


# ---------------------------------------------------------------------------
# PolicyConfig
# ---------------------------------------------------------------------------

@dataclass
class PolicyConfig:
    """
    Operational parameters for a node's relay participation policy.

    Attributes
    ----------
    max_bytes_per_relay   : Maximum packet size (bytes) this node will relay.
    max_relays_per_hour   : Rate limit — maximum relays per 60-minute window.
    max_queue_size        : Flood gate — refuse relay if local queue exceeds this.
    min_trust_score       : Minimum ledger trust score required to relay for a node.
    relay_unknown_nodes   : If True, relay for nodes not yet in the ledger.
    priority_threshold    : Minimum priority level required (1=normal, 2=high, 3=critical).
    bandwidth_reserve_pct : Fraction of relay capacity reserved for high-priority traffic.
    """

    max_bytes_per_relay: int = 1_048_576       # 1 MiB
    max_relays_per_hour: int = 100
    max_queue_size: int = 10_000               # flood protection
    min_trust_score: float = 0.0
    relay_unknown_nodes: bool = True
    priority_threshold: int = 1
    bandwidth_reserve_pct: float = 0.2

    def to_dict(self) -> dict:
        """Serialise to a plain dict."""
        return {
            "max_bytes_per_relay": self.max_bytes_per_relay,
            "max_relays_per_hour": self.max_relays_per_hour,
            "max_queue_size": self.max_queue_size,
            "min_trust_score": self.min_trust_score,
            "relay_unknown_nodes": self.relay_unknown_nodes,
            "priority_threshold": self.priority_threshold,
            "bandwidth_reserve_pct": self.bandwidth_reserve_pct,
        }


# ---------------------------------------------------------------------------
# ParticipationPolicy
# ---------------------------------------------------------------------------

class ParticipationPolicy:
    """
    Enforces relay participation rules defined in PolicyConfig.

    Checks are applied in order; the first failing check is returned as the
    rejection reason. Approved relays are tracked for rate limiting.

    Parameters
    ----------
    config : PolicyConfig instance.
    ledger : ContributionLedger used for trust score lookups.
    queue  : MessageQueue used for queue-size flood-gate check.
             Pass None to disable the queue-size check.
    """

    def __init__(
        self,
        config: PolicyConfig,
        ledger: ContributionLedger,
        queue: object | None = None,
    ) -> None:
        self._config = config
        self._ledger = ledger
        self._queue = queue
        # Hourly window tracking: {node_id: [(timestamp, bytes), ...]}
        self._relay_log: dict[str, list[float]] = defaultdict(list)

    def should_relay(
        self,
        origin_node_id: str,
        packet_size_bytes: int,
        priority: int,
    ) -> tuple[bool, str]:
        """
        Decide whether to relay a packet from the given origin node.

        Parameters
        ----------
        origin_node_id    : node_id of the packet's originating node.
        packet_size_bytes : Size of the packet in bytes.
        priority          : Packet priority (1=normal, 2=high, 3=critical).

        Returns
        -------
        tuple[bool, str]
            (True, "APPROVED") or (False, rejection_reason).
        """
        cfg = self._config

        # 1. Flood protection — queue size gate
        if self._queue is not None:
            report = self._queue.status_report()
            pending = report.get("PENDING", 0) + report.get("SENT", 0)
            if pending >= cfg.max_queue_size:
                return False, (
                    f"QUEUE_FULL: local queue has {pending} pending items "
                    f"(max {cfg.max_queue_size})"
                )

        # 2. Packet size limit
        if packet_size_bytes > cfg.max_bytes_per_relay:
            return False, (
                f"PACKET_TOO_LARGE: {packet_size_bytes} bytes "
                f"> max {cfg.max_bytes_per_relay} bytes"
            )

        # 3. Priority threshold
        if priority < cfg.priority_threshold:
            return False, (
                f"PRIORITY_TOO_LOW: priority {priority} "
                f"< threshold {cfg.priority_threshold}"
            )

        # 4. Hourly rate limit
        now = time.monotonic()
        window_start = now - 3600.0
        log = self._relay_log[origin_node_id]
        # Trim entries outside the 1-hour window
        log[:] = [t for t in log if t >= window_start]
        if len(log) >= cfg.max_relays_per_hour:
            return False, (
                f"RATE_LIMITED: {len(log)} relays in the last hour "
                f"(max {cfg.max_relays_per_hour})"
            )

        # 5. Trust score
        trust = self._ledger.get_trust_score(origin_node_id)
        if trust == 0.0:
            # Node unknown (no ledger entry)
            if not cfg.relay_unknown_nodes:
                return False, (
                    f"UNKNOWN_NODE: {origin_node_id[:16]}... has no ledger entry "
                    "and relay_unknown_nodes=False"
                )
        elif trust < cfg.min_trust_score:
            return False, (
                f"TRUST_TOO_LOW: node {origin_node_id[:16]}... "
                f"score={trust:.3f} < min={cfg.min_trust_score:.3f}"
            )

        return True, "APPROVED"

    def record_relay(self, origin_node_id: str, bytes_relayed: int) -> None:
        """
        Record that a relay was performed.

        Updates the rate-limit log for hourly count tracking.

        Parameters
        ----------
        origin_node_id : node_id of the packet's originator.
        bytes_relayed  : Number of bytes relayed.
        """
        self._relay_log[origin_node_id].append(time.monotonic())

    def get_policy_report(self) -> dict:
        """
        Return the current policy configuration and runtime statistics.

        Returns
        -------
        dict
            Config fields plus per-node hourly relay counts.
        """
        now = time.monotonic()
        window_start = now - 3600.0
        hourly_counts = {
            nid: len([t for t in ts if t >= window_start])
            for nid, ts in self._relay_log.items()
        }
        return {
            "config": self._config.to_dict(),
            "hourly_relay_counts": hourly_counts,
        }
