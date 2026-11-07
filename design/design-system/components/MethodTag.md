# MethodTag

Names one of the three retrieval methods being compared: Keyword (BM25), Meaning (MiniLM embeddings) or Hybrid (Reciprocal Rank Fusion).

**You provide:** `method` ("keyword", "semantic" or "hybrid"), and `detail={false}` to drop the technique name where space is tight.

- Use it as the heading of each column in a side-by-side comparison, and beside any score or metric that belongs to one method.
- Always list the methods in the same order: Keyword, Meaning, Hybrid.
- The three method colours are the only categorical colours in the system. In a chart, pair each with a direct label; do not rely on a legend of colour swatches alone.
- Say "Meaning" in the interface; "semantic" is the name in code and in the report.
