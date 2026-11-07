"""Find passages that match a question.

BM25 scores a passage higher when it contains the question's words, and when those words are rare.
Dense search matches meaning. Hybrid mixes both lists. The re-ranker reorders that mix, and the
overview writes a short answer from the passages that were found.
"""
