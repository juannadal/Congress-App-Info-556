"""Mix the word list and the meaning list into one ranking. Reciprocal rank fusion (RRF) scores a passage by its place in each list, not by the raw scores.

Hybrid search: Reciprocal Rank Fusion (RRF) of the BM25 and dense rankings.

Each method returns its top `depth` passages (default 100); a passage's fused score is
    sum over methods of 1 / (k_rrf + rank),   k_rrf = 60 (Cormack et al., 2009)
and a passage missing from one method's list gets nothing from that method. RRF uses only
ranks, so BM25 scores and cosine similarities never have to be put on the same scale.
Ties are broken by the passage's best rank in either list.

Filtering with `where` is passed to both methods, so both are pre-filtered (see bm25.py
and dense.py) and the fused list only contains matching passages.
"""

import pandas as pd

from retrieval.bm25 import BM25Index
from retrieval.corpus import DISPLAY_COLUMNS
from retrieval.dense import DenseIndex

# Softens the reward for first place. 60 is the usual setting.
K_RRF = 60
# How many passages each method may send into the blend.
DEPTH = 100


# Blend ranked lists by each passage's place, not by the raw scores.
def rrf(rankings, k_rrf=K_RRF):
    """Fuse ranked lists of passage IDs. Returns a DataFrame indexed by passage_id with
    the fused score and each list's rank (NaN where the passage wasn't retrieved)."""
    ranks = pd.DataFrame({name: pd.Series(range(1, len(ids) + 1), index=list(ids), dtype=float)
                          for name, ids in rankings.items()})
    # Each list adds 1 / (60 + rank). A passage missing from a list adds nothing from that list.
    fused = ranks.assign(score=(1 / (k_rrf + ranks)).sum(axis=1), best=ranks.min(axis=1))
    return fused.sort_values(["score", "best"], ascending=[False, True], kind="stable").drop(columns="best")


class HybridIndex:
    """Runs word search and meaning search, then blends the two lists."""

    def __init__(self, passages, column="text", bm25=None, dense=None, depth=DEPTH, k_rrf=K_RRF):
        """Hold both indexes, and remember which row each passage id belongs to."""
        self.passages = passages.reset_index(drop=True)
        self.bm25 = bm25 or BM25Index(self.passages, column=column)
        self.dense = dense or DenseIndex(self.passages, column=column)
        self.depth = depth
        self.k_rrf = k_rrf
        self.row_of = pd.Series(self.passages.index, index=self.passages["passage_id"])

    def search(self, query, k=10, where=None):
        """Top-k passages as a DataFrame with rank, RRF score, and the BM25 and dense ranks."""
        # Ask each method for its own top `depth` passages, which is 100 unless changed.
        rankings = {
            "bm25_rank": self.bm25.search(query, k=self.depth, where=where)["passage_id"],
            "dense_rank": self.dense.search(query, k=self.depth, where=where)["passage_id"],
        }
        # Blend the lists and keep the best ones.
        fused = rrf(rankings, self.k_rrf).head(k)
        # Attach the passage text, the blended score, and both places in the lists.
        results = self.passages.loc[self.row_of[fused.index].to_numpy(), DISPLAY_COLUMNS].copy()
        results.insert(0, "dense_rank", fused["dense_rank"].astype("Int64").to_numpy())
        results.insert(0, "bm25_rank", fused["bm25_rank"].astype("Int64").to_numpy())
        results.insert(0, "score", fused["score"].to_numpy())
        results.insert(0, "rank", range(1, len(fused) + 1))
        return results.reset_index(drop=True)
