#!/bin/sh
# Старт від root лише щоб підготувати /data (named volume від старого образу
# чи bind-каталог належить root), далі процес працює від uid 10001.
set -e
if [ "$(id -u)" = 0 ]; then
    mkdir -p /data /data/tls
    # Лише файли з чужим власником: на вже виправленому томі це швидкий no-op.
    find /data ! -user 10001 -exec chown 10001:10001 {} +
    exec setpriv --reuid=10001 --regid=10001 --clear-groups "$@"
fi
exec "$@"
