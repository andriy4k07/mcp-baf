"""TLS для https-транспорту: свої cert/key або самопідписаний CA у каталозі.

Без явних mcp_baf_TLS_CERT/KEY сервер один раз генерує власний CA і
серверний сертифікат, підписаний ним, у <cache_dir>/tls/. Клієнти (hermes,
дашборд) довіряють `ca.crt`. Окремий CA, а не самопідписаний лист: Python 3.13+
перевіряє ланцюжок у режимі VERIFY_X509_STRICT, і лист-як-якір там падає.
"""

from __future__ import annotations

import datetime
import ipaddress
import os
import socket

CA_CERT_NAME = "ca.crt"
SERVER_CERT_NAME = "server.crt"
SERVER_KEY_NAME = "server.key"


def self_signed_hosts(*extra: str) -> list[str]:
    """SAN за замовчуванням: localhost, loopback і hostname контейнера/хоста."""
    hosts = ["localhost", "127.0.0.1", "::1", socket.gethostname()]
    for host in extra:
        host = host.strip()
        if host and host not in ("0.0.0.0", "::") and host not in hosts:
            hosts.append(host)
    return hosts


def _san(host: str):
    from cryptography import x509

    try:
        return x509.IPAddress(ipaddress.ip_address(host))
    except ValueError:
        return x509.DNSName(host)


def ensure_self_signed(directory: str, hosts: list[str]) -> tuple[str, str, str]:
    """(ca.crt, server.crt, server.key) у directory; генерує, якщо їх нема.

    shortcut: наявні файли не перевипускаються при зміні hosts чи наближенні
    кінця строку — видаліть каталог, щоб перегенерувати.
    """
    ca_path = os.path.join(directory, CA_CERT_NAME)
    cert_path = os.path.join(directory, SERVER_CERT_NAME)
    key_path = os.path.join(directory, SERVER_KEY_NAME)
    if all(os.path.exists(p) for p in (ca_path, cert_path, key_path)):
        return ca_path, cert_path, key_path

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    now = datetime.datetime.now(datetime.timezone.utc)
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "mcp-baf local CA")])
    ca_ski = x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key())
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name).issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=False, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True,
            crl_sign=True, encipher_only=False, decipher_only=False,
        ), critical=True)
        .add_extension(ca_ski, critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    key = ec.generate_private_key(ec.SECP256R1())
    cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hosts[0])]))
        .issuer_name(ca_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        # 825 днів — межа, яку ще приймають клієнти Apple/браузери для листа.
        .not_valid_after(now + datetime.timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName([_san(h) for h in hosts]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=False,
            crl_sign=False, encipher_only=False, decipher_only=False,
        ), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_subject_key_identifier(ca_ski), critical=False
        )
        .sign(ca_key, hashes.SHA256())
    )

    os.makedirs(directory, exist_ok=True)
    # Ключ CA не зберігаємо: новий лист = новий CA (видалити каталог).
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
    with open(cert_path, "wb") as fh:
        fh.write(cert.public_bytes(serialization.Encoding.PEM))
    # ca.crt пишемо останнім: його наявність = комплект готовий.
    with open(ca_path, "wb") as fh:
        fh.write(ca_cert.public_bytes(serialization.Encoding.PEM))
    return ca_path, cert_path, key_path
