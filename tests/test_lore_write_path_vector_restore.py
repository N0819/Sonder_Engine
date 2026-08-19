"""restore_memory_vectors must verify what an archive claims about itself.

The vector store is content-addressed -- `vector_address` hashes the blob
bytes, and `put_memory_vector` is INSERT OR IGNORE with first-writer-wins on
the reasoning that the address IS the content. `restore_memory_vectors` was
the one writer that broke the premise: it filed the archive's `vkey` straight
through with no recomputation and no length check (`persist/checkpoints.py`'s
restore already recomputes; this path did not). A corrupt or mislabeled
archive could therefore park wrong bytes under a true address, and because
first-writer-wins, the poisoned row would shadow the real vector for every
later checkpoint that referenced it. Impact is bounded -- embeddings are
opaque ranking floats and `_cos` returns 0.0 on a dimension mismatch -- which
is why the fix is validation, not a rekey.

The rule: a `v1:` key must equal the address recomputed from the blobs it
arrives with, the blob length must match the claimed dimension, and a
violation RAISES so the enclosing transaction rolls the whole import back --
a partially-restored vector store is exactly the silent degradation the model
stamps were added to end. Pre-`v1:` legacy keys cannot be recomputed (the old
scheme hashed the memory document, not the bytes) and still restore on the
well-formedness checks alone.
"""

from __future__ import annotations

import base64

import numpy as np
import pytest

from core.db import q
from mind import memory


def _blob(values):
    return np.asarray(values, dtype=np.float32).tobytes()


def _b64(blob):
    return base64.b64encode(blob).decode("ascii")


def _entry(full, cue, vkey=None, dim=None):
    return {
        "vkey": vkey if vkey is not None else memory.vector_address(full, cue),
        "embedding": _b64(full),
        "cue_embedding": _b64(cue),
        "embedding_model": "test:model:4",
        "embedding_dim": dim if dim is not None else len(full) // 4,
    }


class TestRestoreValidation:
    def test_a_valid_entry_restores(self, temp_db):
        full, cue = _blob([1, 2, 3, 4]), _blob([5, 6, 7, 8])
        assert memory.restore_memory_vectors([_entry(full, cue)]) == 1
        row = q("SELECT * FROM memory_vectors", one=True)
        assert row["embedding"] == full

    def test_a_corrupt_blob_rolls_back_the_whole_restore(self, temp_db):
        full, cue = _blob([1, 2, 3, 4]), _blob([5, 6, 7, 8])
        good = _entry(full, cue)
        bad = dict(good, vkey="v1:" + "0" * 40,
                   embedding=_b64(b"\x01\x02\x03"))  # not a float32 array
        with pytest.raises(ValueError):
            memory.restore_memory_vectors([good, bad])
        # The good entry rolled back with it: all or nothing.
        assert q("SELECT COUNT(*) AS c FROM memory_vectors", one=True)["c"] == 0

    def test_a_mismatched_v1_address_is_refused(self, temp_db):
        full, cue = _blob([1, 2, 3, 4]), _blob([5, 6, 7, 8])
        wrong = memory.vector_address(cue, full)  # a real address, not THIS one
        with pytest.raises(ValueError):
            memory.restore_memory_vectors([_entry(full, cue, vkey=wrong)])
        assert q("SELECT COUNT(*) AS c FROM memory_vectors", one=True)["c"] == 0

    def test_a_dimension_lie_is_refused(self, temp_db):
        full, cue = _blob([1, 2, 3, 4]), _blob([5, 6, 7, 8])
        with pytest.raises(ValueError):
            memory.restore_memory_vectors([_entry(full, cue, dim=256)])
        assert q("SELECT COUNT(*) AS c FROM memory_vectors", one=True)["c"] == 0

    def test_a_legacy_pre_v1_key_still_restores(self, temp_db):
        """Archives dumped from a store holding old-scheme rows carry keys the
        byte-address cannot recompute; well-formedness is all that can be
        asked of them."""
        full, cue = _blob([1, 2, 3, 4]), _blob([5, 6, 7, 8])
        n = memory.restore_memory_vectors(
            [_entry(full, cue, vkey="legacy-document-hash")])
        assert n == 1

    def test_idempotent_restore_still_counts_and_keeps_one_row(self, temp_db):
        full, cue = _blob([1, 2, 3, 4]), _blob([5, 6, 7, 8])
        memory.restore_memory_vectors([_entry(full, cue)])
        memory.restore_memory_vectors([_entry(full, cue)])
        assert q("SELECT COUNT(*) AS c FROM memory_vectors", one=True)["c"] == 1
