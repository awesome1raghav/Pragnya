"""A gap-safe cursor over the outbox sequence.

Identity values are assigned when a row is inserted, not when its transaction commits, so a reader can see
sequence 11 before 10 commits. A reader that jumped its cursor to 11 would never see 10. This cursor only
advances over a contiguous run of seen sequences. A hole is waited for, up to `gap_timeout` seconds, then
skipped: a rolled-back transaction consumes identity values that never appear.
"""

import time


class GapSafeCursor:
    def __init__(self, start: int, *, gap_timeout: float = 15.0, clock=time.monotonic):
        self.position = start            # every sequence <= position has been handled
        self._seen: set[int] = set()     # handled sequences above position
        self._gap_since: dict[int, float] = {}
        self.gap_timeout = gap_timeout
        self.clock = clock

    def is_new(self, sequence: int) -> bool:
        return sequence > self.position and sequence not in self._seen

    def mark(self, sequence: int) -> None:
        if sequence > self.position:
            self._seen.add(sequence)
        self._advance()

    def _advance(self) -> None:
        while True:
            nxt = self.position + 1
            if nxt in self._seen:
                self._seen.remove(nxt)
                self._gap_since.pop(nxt, None)
                self.position = nxt
                continue
            if self._seen and nxt < max(self._seen):
                first = self._gap_since.setdefault(nxt, self.clock())
                if self.clock() - first >= self.gap_timeout:
                    self._gap_since.pop(nxt, None)
                    self.position = nxt
                    continue
            return

    def tick(self) -> None:
        """Re-evaluate waiting gaps (call after each poll, even an empty one)."""
        self._advance()
