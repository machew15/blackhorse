"""
Phase 2C — Spatial Collector.

Reads GPS position from a serial NMEA device and system sensor data,
assembles SpatialRecord objects, and feeds them into the message queue.

Designed for graceful degradation: if GPS hardware is unavailable, the
collector still emits records with lat/lon = 0.0 so the node remains
visible on the mesh with whatever sensor data is available.

NMEA sentences parsed (inline, no external GPS libraries):
  $GPRMC — position, speed, date
  $GPGGA — position, altitude, fix quality
"""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional

from .spatial import SpatialRecord, SpatialPacker


# ---------------------------------------------------------------------------
# NMEA parsing (inline)
# ---------------------------------------------------------------------------

def _nmea_lat_to_decimal(value: str, direction: str) -> float:
    """
    Convert NMEA latitude string and hemisphere to decimal degrees.

    NMEA format: DDMM.MMMM where DD = degrees, MM.MMMM = minutes.
    """
    if not value:
        return 0.0
    try:
        deg = float(value[:2])
        minutes = float(value[2:])
        decimal = deg + minutes / 60.0
        return -decimal if direction == "S" else decimal
    except (ValueError, IndexError):
        return 0.0


def _nmea_lon_to_decimal(value: str, direction: str) -> float:
    """
    Convert NMEA longitude string and hemisphere to decimal degrees.

    NMEA format: DDDMM.MMMM where DDD = degrees, MM.MMMM = minutes.
    """
    if not value:
        return 0.0
    try:
        deg = float(value[:3])
        minutes = float(value[3:])
        decimal = deg + minutes / 60.0
        return -decimal if direction == "W" else decimal
    except (ValueError, IndexError):
        return 0.0


def _parse_gprmc(sentence: str) -> tuple[float, float] | None:
    """
    Parse a $GPRMC sentence and return (latitude, longitude) or None.

    $GPRMC,HHMMSS.ss,A,LLLL.LL,a,YYYYY.YY,a,...
    Field 2: status (A=valid, V=invalid)
    """
    parts = sentence.split(",")
    if len(parts) < 7:
        return None
    status = parts[2]
    if status != "A":
        return None
    lat = _nmea_lat_to_decimal(parts[3], parts[4])
    lon = _nmea_lon_to_decimal(parts[5], parts[6].split("*")[0])
    return lat, lon


def _parse_gpgga(sentence: str) -> tuple[float, float, float] | None:
    """
    Parse a $GPGGA sentence and return (latitude, longitude, altitude_m) or None.

    $GPGGA,HHMMSS.ss,LLLL.LL,a,YYYYY.YY,a,Q,NN,D.D,H.H,M,...
    Field 6: fix quality (0 = invalid)
    """
    parts = sentence.split(",")
    if len(parts) < 10:
        return None
    quality = parts[6]
    if quality == "0" or quality == "":
        return None
    lat = _nmea_lat_to_decimal(parts[2], parts[3])
    lon = _nmea_lon_to_decimal(parts[4], parts[5])
    try:
        altitude_m = float(parts[9]) if parts[9] else 0.0
    except ValueError:
        altitude_m = 0.0
    return lat, lon, altitude_m


def _parse_nmea_sentences(
    lines: list[str],
) -> tuple[float, float, float, float] | None:
    """
    Parse a list of NMEA sentence strings.

    Returns (latitude, longitude, altitude_m, accuracy_m) using the best
    available sentence. Returns None if no valid fix is found.

    accuracy_m is estimated from HDOP in $GPGGA (HDOP × 3 metres) if
    available, otherwise -1.0.
    """
    lat = lon = altitude_m = 0.0
    accuracy_m = -1.0
    got_fix = False

    for line in lines:
        line = line.strip()
        if line.startswith("$GPRMC"):
            result = _parse_gprmc(line)
            if result:
                lat, lon = result
                got_fix = True
        elif line.startswith("$GPGGA"):
            result = _parse_gpgga(line)
            if result:
                lat, lon, altitude_m = result
                got_fix = True
                # Extract HDOP for accuracy estimate
                parts = line.split(",")
                if len(parts) > 8 and parts[8]:
                    try:
                        hdop = float(parts[8])
                        accuracy_m = hdop * 3.0  # rough estimate
                    except ValueError:
                        pass

    return (lat, lon, altitude_m, accuracy_m) if got_fix else None


# ---------------------------------------------------------------------------
# Sequence counter (SQLite-backed for persistence across restarts)
# ---------------------------------------------------------------------------

_SEQ_TABLE = """
CREATE TABLE IF NOT EXISTS seq_counter (
    node_id TEXT PRIMARY KEY,
    next_seq INTEGER NOT NULL DEFAULT 0
);
"""


def _next_sequence(conn: sqlite3.Connection, node_id: str) -> int:
    """Atomically fetch-and-increment the per-node sequence counter."""
    conn.execute(_SEQ_TABLE)
    row = conn.execute(
        "SELECT next_seq FROM seq_counter WHERE node_id = ?", (node_id,)
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO seq_counter (node_id, next_seq) VALUES (?, 1)", (node_id,)
        )
        return 0
    seq = row[0]
    conn.execute(
        "UPDATE seq_counter SET next_seq = next_seq + 1 WHERE node_id = ?",
        (node_id,),
    )
    return seq


# ---------------------------------------------------------------------------
# SpatialCollector
# ---------------------------------------------------------------------------

class SpatialCollector:
    """
    Collects GPS position and system sensor readings into SpatialRecord objects.

    Designed for Raspberry Pi / embedded Linux. Degrades gracefully if GPS
    hardware or sensor paths are absent — the node still participates in the
    mesh with available data.

    Parameters
    ----------
    node_id               : This node's hex SHA-256 node_id.
    signing_key           : 32-byte HMAC key for signing packed records.
    packer                : SpatialPacker used to encode records.
    queue                 : MessageQueue for enqueuing packed records.
    gps_device            : Serial device path for NMEA GPS receiver.
    baud                  : Serial baud rate.
    poll_interval_seconds : How often to collect a reading.
    seq_db_path           : SQLite path for the persistent sequence counter.
    """

    def __init__(
        self,
        node_id: str,
        signing_key: bytes,
        packer: SpatialPacker,
        queue: object,
        gps_device: str = "/dev/ttyUSB0",
        baud: int = 9600,
        poll_interval_seconds: int = 60,
        seq_db_path: str = ":memory:",
    ) -> None:
        self._node_id = node_id
        self._signing_key = signing_key
        self._packer = packer
        self._queue = queue
        self._gps_device = gps_device
        self._baud = baud
        self._interval = poll_interval_seconds
        self._seq_conn = sqlite3.connect(seq_db_path, check_same_thread=False)
        self._seq_conn.isolation_level = None
        self._bg_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # GPS reading
    # ------------------------------------------------------------------

    def read_gps(self) -> tuple[float, float, float, float] | None:
        """
        Attempt to read a GPS fix from the configured serial device.

        Reads up to 20 NMEA lines and parses $GPRMC / $GPGGA sentences.
        Returns None gracefully if the device is absent or produces no fix.

        Returns
        -------
        tuple[float, float, float, float] | None
            (latitude, longitude, altitude_m, accuracy_m) or None.
        """
        try:
            import serial  # type: ignore[import]
        except ImportError:
            return None

        lines: list[str] = []
        try:
            with serial.Serial(self._gps_device, self._baud, timeout=2) as port:
                for _ in range(20):
                    try:
                        raw = port.readline()
                        line = raw.decode("ascii", errors="ignore")
                        lines.append(line)
                    except Exception:
                        break
        except (OSError, Exception):
            return None

        return _parse_nmea_sentences(lines)

    # ------------------------------------------------------------------
    # Sensor reading
    # ------------------------------------------------------------------

    def read_sensors(self) -> dict:
        """
        Read available system sensor data.

        Attempts to read:
        - CPU temperature from /sys/class/thermal/thermal_zone0/temp
        - Free disk space in bytes from the root filesystem
        - wlan0 signal strength from /proc/net/wireless

        Returns an empty dict if nothing is available; never raises.

        Returns
        -------
        dict
            Sensor key-value pairs, e.g. {"temp_c": 42.3, "disk_free_bytes": 1234}.
        """
        data: dict = {}

        # CPU temperature
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                raw = int(f.read().strip())
                data["temp_c"] = round(raw / 1000.0, 1)
        except (OSError, ValueError):
            pass

        # Disk free space
        try:
            st = os.statvfs("/")
            data["disk_free_bytes"] = st.f_bavail * st.f_frsize
        except OSError:
            pass

        # wlan0 signal strength (RSSI)
        try:
            with open("/proc/net/wireless") as f:
                for line in f:
                    if "wlan0" in line:
                        parts = line.split()
                        if len(parts) >= 4:
                            # Format: wlan0: status link level noise
                            rssi_str = parts[3].rstrip(".")
                            data["wlan0_rssi_dbm"] = int(float(rssi_str))
                        break
        except (OSError, ValueError, IndexError):
            pass

        return data

    # ------------------------------------------------------------------
    # Collect
    # ------------------------------------------------------------------

    def collect(self) -> Optional[SpatialRecord]:
        """
        Assemble a SpatialRecord from current GPS and sensor readings.

        If GPS is unavailable, latitude/longitude are 0.0 and accuracy_m is -1.0
        — the node still participates in the mesh with whatever sensor data exists.

        Returns
        -------
        SpatialRecord | None
            Always returns a SpatialRecord (even without GPS). Returns None
            only if a fatal internal error occurs.
        """
        try:
            gps = self.read_gps()
            sensors = self.read_sensors()

            if gps is not None:
                lat, lon, alt, acc = gps
            else:
                lat, lon, alt, acc = 0.0, 0.0, 0.0, -1.0

            seq = _next_sequence(self._seq_conn, self._node_id)

            return SpatialRecord(
                node_id=self._node_id,
                latitude=lat,
                longitude=lon,
                altitude_m=alt,
                accuracy_m=acc,
                timestamp=datetime.now(timezone.utc),
                sensor_data=sensors,
                sequence=seq,
            )
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Background collection
    # ------------------------------------------------------------------

    def start_background_collection(self) -> None:
        """
        Start collecting spatial records in a background daemon thread.

        Each collected record is packed via SpatialPacker and enqueued at
        priority 1 (normal). Runs until stop() is called.
        """
        if self._bg_thread and self._bg_thread.is_alive():
            return
        self._stop_event.clear()
        self._bg_thread = threading.Thread(
            target=self._collection_loop,
            daemon=True,
            name="bhp-spatial-collector",
        )
        self._bg_thread.start()

    def _collection_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                record = self.collect()
                if record is not None:
                    packet_bytes = self._packer.pack(record)
                    self._queue.enqueue(packet_bytes, b"\x00" * 32, priority=1)
            except Exception:
                pass
            self._stop_event.wait(timeout=self._interval)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def stop(self) -> None:
        """Stop the background collection thread cleanly."""
        self._stop_event.set()
        if self._bg_thread:
            self._bg_thread.join(timeout=self._interval + 1)
