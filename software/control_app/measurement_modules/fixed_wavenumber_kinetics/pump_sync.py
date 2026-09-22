"""Leading-edge detection for the installed active-low Surelite sync input."""
import numpy as np


def falling_sync_ticks(timestamps, words, bit, previous_level=None):
    """Return observed HIGH-to-LOW edges and carry the last level across polls.

    An initial LOW is not an observed edge. Never infer an onset from a level,
    a return to HIGH, or a command timestamp. Keep device ticks as integers.
    """
    ticks = np.asarray(timestamps)
    levels = (np.asarray(words, dtype=np.uint64) & np.uint64(1 << bit)) != 0
    if len(ticks) != len(levels):
        raise ValueError("Missing or malformed native electrical timing stream")
    if not len(levels):
        return [], previous_level
    edges = np.empty(len(levels), dtype=bool)
    edges[0] = previous_level == 1 and not levels[0]
    edges[1:] = levels[:-1] & ~levels[1:]
    return [int(tick) for tick in ticks[edges]], int(levels[-1])
