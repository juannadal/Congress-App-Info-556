"""Find passages that share the question's words. BM25 scores a passage higher when it contains the question's words, and when those words are rare in the whole set.

BM25 (Okapi) keyword search with rank_bm25.

Tokenizing: accents removed, lowercased, split on anything that isn't a letter or digit,
NLTK English stop words removed, and (by default) Porter stemming. The same tokenizer is
used for passages and queries.

Filtering with `where` is pre-filtering: only matching passages are scored, but IDF still
comes from the full corpus, so a term's weight doesn't change with the filter.
"""

import re
import unicodedata
from functools import lru_cache

import nltk
import numpy as np
from nltk.stem import PorterStemmer
from rank_bm25 import BM25Okapi

from retrieval.corpus import DISPLAY_COLUMNS, filter_mask

# A word is a run of letters or digits.
TOKEN = re.compile(r"[a-z0-9]+")


def _stop_words():
    """Load common English words to ignore, and download the list the first time."""
    try:
        from nltk.corpus import stopwords
        return frozenset(stopwords.words("english"))
    except LookupError:
        nltk.download("stopwords", quiet=True)
        from nltk.corpus import stopwords
        return frozenset(stopwords.words("english"))


STOP_WORDS = _stop_words()
# Shorten a word to its root, and remember the result.
_stem = lru_cache(maxsize=None)(PorterStemmer().stem)


def tokenize(text, stem=True):
    """Turn text into the words to match. Drop accents and common words. Shorten each word to its root when stem is on."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    tokens = [t for t in TOKEN.findall(text) if t not in STOP_WORDS]
    return [_stem(t) for t in tokens] if stem else tokens


class BM25Index:
    """A word index that scores each passage against a question."""

    def __init__(self, passages, column="text", stem=True, k1=1.5, b=0.75):
        """Split every passage into words and build the word index."""
        self.passages = passages.reset_index(drop=True)
        self.column = column
        self.stem = stem
        corpus = [tokenize(t, stem) for t in self.passages[column]]
        # A passage gets credit for each shared word. More repeats help, but only up to a point
        # (k1, default 1.5). Rare words count more. A long passage is discounted (b, default 0.75).
        # rank_bm25 computes that formula. This file only hands it the words and those two settings.
        self.bm25 = BM25Okapi(corpus, k1=k1, b=b)

    # Score every passage for this question. Passages outside the filter get the worst score.
    def scores(self, query, where=None):
        """BM25 score for every passage; passages outside the filter get -inf."""
        terms = tokenize(query, self.stem)
        if not where:
            return self.bm25.get_scores(terms)
        mask = filter_mask(self.passages, where)
        scores = np.full(len(self.passages), -np.inf)
        ids = np.flatnonzero(mask)
        if len(ids):
            scores[ids] = self.bm25.get_batch_scores(terms, ids.tolist())
        return scores

    # Return the best passages, best first. Leave out passages that share no words with the question.
    def search(self, query, k=10, where=None):
        """Top-k passages as a DataFrame with rank and score. Passages matching no query term are left out."""
        scores = self.scores(query, where)
        top = np.argsort(-scores, kind="stable")[:k]
        top = top[scores[top] > 0]
        results = self.passages.loc[top, DISPLAY_COLUMNS].copy()
        results.insert(0, "score", scores[top])
        results.insert(0, "rank", np.arange(1, len(top) + 1))
        return results.reset_index(drop=True)
