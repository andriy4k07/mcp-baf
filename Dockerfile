# mcp-baf як мережевий сервіс: streamable-http за TLS на :8001/mcp (read-only 1С).
# Без mcp_baf_TLS_CERT/KEY сервер сам генерує CA у /data/tls/ (клієнти довіряють ca.crt).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    mcp_baf_TRANSPORT=https \
    mcp_baf_HTTP_HOST=0.0.0.0 \
    mcp_baf_HTTP_PORT=8001 \
    mcp_baf_CACHE_DIR=/data \
    mcp_baf_NO_TTY=1

WORKDIR /app

# LICENSE потрібен hatchling (pyproject: license-files)
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install .

RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8001

CMD ["mcp-baf"]
