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

# Непривилегированный пользователь uid 10001: entrypoint стартует от root,
# создаёт /data и /data/tls, чинит владельца (старые тома и bind-каталоги
# принадлежат root) и понижает права через setpriv (util-linux есть в базе).
RUN groupadd --gid 10001 mcpbaf \
    && useradd --uid 10001 --gid 10001 --home-dir /app --no-create-home \
       --shell /usr/sbin/nologin mcpbaf \
    && mkdir -p /data/tls \
    && chown -R mcpbaf:mcpbaf /data
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
# Exec-форма ENTRYPOINT требует +x; не полагаемся на бит в checkout (Windows, архивы).
RUN chmod 0755 /usr/local/bin/docker-entrypoint.sh

VOLUME ["/data"]

EXPOSE 8001

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["mcp-baf"]
