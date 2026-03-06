"""
RingBuffer — fixed-capacity circular byte buffer.

Used by the Stage 3 compression engine as the look-behind window.
Push bytes in; query match offsets and lengths for previously seen data.
"""

from __future__ import annotations


class RingBuffer:
    """
    A fixed-capacity circular buffer for byte data.

    Bytes are pushed in at the "tail" and the oldest bytes fall off the
    "head" once capacity is reached.  Random reads by absolute buffer
    index are O(1) modulo arithmetic.
    """

    def __init__(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("Capacity must be a positive integer")
        self._buf: bytearray = bytearray(capacity)
        self._capacity: int = capacity
        self._head: int = 0    # index of the oldest valid byte
        self._size: int = 0    # number of valid bytes currently stored

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def capacity(self) -> int:
        """Maximum number of bytes the buffer can hold."""
        return self._capacity

    @property
    def size(self) -> int:
        """Number of valid bytes currently stored."""
        return self._size

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def push(self, data: bytes | bytearray | int) -> None:
        """
        Push one or more bytes into the buffer.

        When the buffer is full the oldest bytes are silently discarded.
        """
        if isinstance(data, int):
            data = bytes([data & 0xFF])
        for byte in data:
            write_idx = (self._head + self._size) % self._capacity
            self._buf[write_idx] = byte
            if self._size < self._capacity:
                self._size += 1
            else:
                # Buffer is full; advance head to overwrite oldest byte.
                self._head = (self._head + 1) % self._capacity

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def read(self, start: int, length: int) -> bytes:
        """
        Read *length* bytes starting at absolute buffer index *start*.

        *start* is a zero-based index where 0 is the oldest byte in the
        buffer and ``self.size - 1`` is the newest.
        """
        if start < 0 or length < 0:
            raise ValueError("start and length must be non-negative")
        if start + length > self._size:
            raise IndexError(
                f"Read [{start}:{start + length}) exceeds buffer size {self._size}"
            )
        result = bytearray(length)
        for i in range(length):
            result[i] = self._buf[(self._head + start + i) % self._capacity]
        return bytes(result)

    def peek(self, count: int | None = None) -> bytes:
        """Return the last *count* bytes (newest first if count < size)."""
        if count is None or count > self._size:
            count = self._size
        return self.read(self._size - count, count)

    def find_match(self, data: bytes, min_len: int = 3) -> tuple[int, int]:
        """
        Search the buffer for the longest prefix match against *data*.

        Returns ``(offset, length)`` where *offset* is the distance back
        from the end of the buffer (1 = most recent byte) and *length* is
        the match length.  Returns ``(0, 0)`` if no match of at least
        *min_len* bytes is found.

        This is an O(n²) brute-force search suitable for moderate window
        sizes (≤ 65 535 bytes).
        """
        if self._size == 0 or not data:
            return 0, 0

        best_offset = 0
        best_length = 0
        search_len = min(len(data), 258)  # cap match length at 258

        # Iterate over every possible start position in the buffer.
        for start in range(self._size):
            match_len = 0
            while (
                match_len < search_len
                and start + match_len < self._size
                and self._buf[(self._head + start + match_len) % self._capacity]
                == data[match_len]
            ):
                match_len += 1

            if match_len >= min_len and match_len > best_length:
                best_length = match_len
                # offset = distance from end of buffer to start of match
                best_offset = self._size - start
                if best_length == search_len:
                    break  # can't do better

        return best_offset, best_length

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __getitem__(self, idx: int) -> int:
        """Return the byte at absolute index *idx* (0 = oldest)."""
        if idx < 0:
            idx += self._size
        if idx < 0 or idx >= self._size:
            raise IndexError(f"RingBuffer index {idx} out of range")
        return self._buf[(self._head + idx) % self._capacity]

    def __len__(self) -> int:
        return self._size

    def __repr__(self) -> str:
        return f"RingBuffer(capacity={self._capacity}, size={self._size})"
