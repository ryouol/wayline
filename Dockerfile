FROM python:3.11.14-slim-bookworm@sha256:65a93d69fa75478d554f4ad27c85c1e69fa184956261b4301ebaf6dbb0a3543d
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home wayline \
    && mkdir /data && chown wayline:wayline /data
COPY requirements/workspace.lock /app/requirements/workspace.lock
RUN pip install --no-cache-dir --require-hashes -r requirements/workspace.lock
COPY pyproject.toml README.md LICENSE.txt SAMPLE_LICENSE.md THIRD_PARTY_NOTICES.md /app/
COPY lingbot_map /app/lingbot_map
RUN pip install --no-cache-dir setuptools==83.0.0 wheel==0.46.3 packaging==26.3 \
    && pip install --no-cache-dir --no-deps --no-build-isolation .
USER wayline
ENV LINGBOT_DATA_DIR=/data LINGBOT_ENV=production
EXPOSE 10000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request,urllib.parse; req=urllib.request.Request('http://127.0.0.1:'+os.getenv('PORT','10000')+'/healthz',headers={'Host':urllib.parse.urlsplit(os.environ['LINGBOT_PUBLIC_BASE_URL']).netloc}); urllib.request.urlopen(req,timeout=4)"
CMD ["sh", "-c", "exec wayline --host 0.0.0.0 --port ${PORT:-10000}"]
