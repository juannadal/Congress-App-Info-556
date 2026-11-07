# Public website image for the Congress search app (Cloudflare Containers via cloudflare/, or any Docker host).
# The dense index and the MiniLM model are built into the image, so no model or index download is needed at startup.
#   docker build -t congress-search .
#   docker run -p 8080:8080 -e ANTHROPIC_API_KEY=... congress-search
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface \
    NLTK_DATA=/app/nltk_data \
    INFO556_INDEX_DIR=/app/index \
    PUBLIC_DEMO=1 \
    STREAMLIT_CLIENT_SHOW_SIDEBAR_NAVIGATION=false \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_HEADLESS=true

WORKDIR /app

# CPU-only PyTorch (the default wheel bundles GPU libraries and is several GB larger)
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
# NLTK stopwords: fetched directly (nltk.download() returns False instead of failing, and newer NLTK can refuse
# downloads behind proxies or into shared folders), then loaded once so a bad download stops the build
RUN mkdir -p /app/nltk_data/corpora \
 && python -c "import urllib.request; urllib.request.urlretrieve('https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora/stopwords.zip', '/app/nltk_data/corpora/stopwords.zip')" \
 && python -m zipfile -e /app/nltk_data/corpora/stopwords.zip /app/nltk_data/corpora/ \
 && python -c "from nltk.corpus import stopwords; n = len(stopwords.words('english')); print('stopwords:', n); assert n > 100" \
 && python -c "from retrieval.corpus import load_passages; from retrieval.dense import DenseIndex; DenseIndex(load_passages()).build()" \
 && useradd --create-home app && chown -R app /app
USER app

EXPOSE 8080
CMD ["sh", "-c", "streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8080}"]
