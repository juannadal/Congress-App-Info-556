"""Find passages whose meaning is close to the question. An embedding turns text into numbers so similar meanings land near each other.

Dense (semantic) search: all-MiniLM-L6-v2 embeddings stored and searched in ChromaDB.

Passages are embedded once with sentence-transformers (normalized, so cosine similarity is
a dot product) and saved in a ChromaDB folder outside the project. The default is
~/.info556/chroma. Set INFO556_INDEX_DIR to use another folder.

Each text column gets its own collection. The collection stores a fingerprint of the
model and passages; if the passages change (e.g. the chunker is rerun), the website
re-embeds them the next time it starts.

Filtering with `where` is pre-filtering: ChromaDB's `where` filter restricts the search to
matching passages.
"""

import hashlib
import os
from pathlib import Path

import numpy as np
import pandas as pd

from retrieval.corpus import DISPLAY_COLUMNS, FILTER_FIELDS

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
INDEX_DIR = Path(os.environ.get("INFO556_INDEX_DIR", Path.home() / ".info556" / "chroma"))
ADD_BATCH = 2000  # ChromaDB caps how many records one add() call can take


def fingerprint(passages, column, model_name):
    """Make a short stamp of the model and the passages, so a later change is easy to see."""
    h = hashlib.sha256(model_name.encode())
    for pid, text in zip(passages["passage_id"], passages[column]):
        h.update(pid.encode())
        h.update(text.encode())
    return h.hexdigest()[:16]


# Turn a simple filter into the form the index expects.
def chroma_where(where):
    """{"chamber": "Senate", "state_code": ["CA", "TX"]} -> a ChromaDB where clause."""
    # One check per field. Several values mean any of these.
    clauses = []
    for field, value in (where or {}).items():
        if field not in FILTER_FIELDS:
            raise ValueError(f"can't filter on {field!r}; use one of {FILTER_FIELDS}")
        if isinstance(value, (list, tuple, set)):
            clauses.append({field: {"$in": list(value)}})
        else:
            clauses.append({field: {"$eq": value}})
    # No filter searches everything. Two or more filters must all match.
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


class DenseIndex:
    """Stores each passage as numbers so a question can find passages with a similar meaning."""

    def __init__(self, passages, column="text", model_name=MODEL_NAME, index_dir=INDEX_DIR, congress=119):
        """Load the meaning model and open the saved index for this text column."""
        import chromadb
        from chromadb.config import Settings
        from sentence_transformers import SentenceTransformer

        # Keep a stable row order and load the model that turns text into numbers.
        self.passages = passages.reset_index(drop=True)
        self.column = column
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        # Open the index folder on disk, and create it the first time.
        index_dir = Path(index_dir)
        index_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(index_dir), settings=Settings(anonymized_telemetry=False))
        self.client = client
        # One index per Congress and text column. It compares meaning, not exact words.
        self.name = f"passages_{congress}_{column}"
        self.collection = client.get_or_create_collection(
            self.name, embedding_function=None, configuration={"hnsw": {"space": "cosine"}})
        # Map each passage id back to its row.
        self.row_of = pd.Series(self.passages.index, index=self.passages["passage_id"])

    def is_current(self):
        """True when the saved index still matches this model and these passages."""
        meta = self.collection.metadata or {}
        return (meta.get("fingerprint") == fingerprint(self.passages, self.column, self.model_name)
                and self.collection.count() == len(self.passages))

    # Turn every passage into numbers and store them in the index.
    def build(self, batch_size=64):
        """Embed every passage and (re)fill the collection."""
        # Throw away the old index and stamp the new one with the model and the passages.
        self.client.delete_collection(self.name)
        self.collection = self.client.create_collection(
            self.name, embedding_function=None, configuration={"hnsw": {"space": "cosine"}},
            metadata={"fingerprint": fingerprint(self.passages, self.column, self.model_name),
                      "model": self.model_name, "column": self.column})
        # Turn every passage into numbers.
        embeddings = self.model.encode(self.passages[self.column].tolist(), batch_size=batch_size,
                                       normalize_embeddings=True, show_progress_bar=True)
        # Save those numbers in batches, with the fields a filter can use.
        meta_cols = ["bioguide_id", *FILTER_FIELDS]
        for start in range(0, len(self.passages), ADD_BATCH):
            chunk = self.passages.iloc[start:start + ADD_BATCH]
            self.collection.add(ids=chunk["passage_id"].tolist(),
                                embeddings=embeddings[start:start + ADD_BATCH],
                                metadatas=chunk[meta_cols].to_dict("records"))

    # Return the closest passages. The score is how similar the meanings are.
    def search(self, query, k=10, where=None):
        """Top-k passages as a DataFrame with rank and score (cosine similarity)."""
        vector = self.model.encode([query], normalize_embeddings=True)
        hits = self.collection.query(query_embeddings=vector, n_results=k, where=chroma_where(where),
                                     include=["distances"])
        ids, distances = hits["ids"][0], np.array(hits["distances"][0])
        results = self.passages.loc[self.row_of[ids].to_numpy(), DISPLAY_COLUMNS].copy()
        # The vectors are scaled to length 1, so cosine similarity is their dot product.
        # Chroma returns the distance. 1 - distance turns it back into similarity:
        # 1 means the same meaning, and 0 means unrelated.
        results.insert(0, "score", 1 - distances)
        results.insert(0, "rank", np.arange(1, len(ids) + 1))
        return results.reset_index(drop=True)
