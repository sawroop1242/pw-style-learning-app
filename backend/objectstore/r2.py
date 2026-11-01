"""A small, dependency-free Cloudflare R2 client (S3 API, SigV4).

The backend already avoids an HTTP library, so this speaks the S3 protocol with
``urllib`` and signs with ``hmac``. Only three operations are needed:

* ``check_bucket`` — prove the account id, token and bucket name belong
  together, without touching an object;
* ``presign_get`` — a short-lived URL for a private object;
* ``put_object`` / ``delete_object`` — used by ``manage.py r2_check --write``.

R2 is S3-compatible: endpoint ``https://<account id>.r2.cloudflarestorage.com``,
region ``auto``, service ``s3``, and it accepts the ``UNSIGNED-PAYLOAD`` marker
on presigned URLs.

Nothing here logs a header. An exception carries a status code and a sentence
an administrator can act on — never a signature, a token or a raw provider
traceback.
"""

from __future__ import annotations

import hashlib
import hmac
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

from django.conf import settings

__all__ = [
    "ALGORITHM",
    "Credentials",
    "R2Error",
    "BucketCheck",
    "endpoint_host",
    "endpoint_url",
    "canonical_query_string",
    "canonical_uri",
    "sign_request",
    "presign_url",
    "check_bucket",
    "presign_get",
    "put_object",
    "delete_object",
]

ALGORITHM = "AWS4-HMAC-SHA256"
SERVICE = "s3"
REGION = "auto"
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()
UNSIGNED_PAYLOAD = "UNSIGNED-PAYLOAD"
MAX_RESPONSE_BYTES = 64 * 1024


class R2Error(RuntimeError):
    """A failed R2 call, described without leaking credentials."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class BucketCheck:
    """The verdict of a connection test."""

    ok: bool
    status: int | None
    message: str


@dataclass(frozen=True)
class Credentials:
    account_id: str
    access_key_id: str
    secret_access_key: str


def endpoint_host(account_id: str) -> str:
    return f"{(account_id or '').strip().lower()}.r2.cloudflarestorage.com"


def endpoint_url(account_id: str, bucket: str = "", path: str = "") -> str:
    host = endpoint_host(account_id)
    parts = [part for part in (bucket, (path or "").lstrip("/")) if part]
    return f"https://{host}/" + "/".join(parts)


# -- signing ---------------------------------------------------------------


def _quote(value: str) -> str:
    """RFC 3986 encoding, as SigV4 requires (no ``+`` for spaces)."""
    return urllib.parse.quote(str(value), safe="-_.~")


def canonical_uri(path: str) -> str:
    """Encode a path once, keeping its separators."""
    if not path:
        return "/"
    if not path.startswith("/"):
        path = "/" + path
    return urllib.parse.quote(path, safe="/-_.~")


def canonical_query_string(params) -> str:
    items = params.items() if hasattr(params, "items") else params
    pairs = sorted((_quote(key), _quote(value)) for key, value in items)
    return "&".join(f"{key}={value}" for key, value in pairs)


def _canonical_headers(headers) -> tuple[str, str]:
    normalized = {
        str(key).lower().strip(): " ".join(str(value).split()) for key, value in headers.items()
    }
    ordered = sorted(normalized.items())
    block = "".join(f"{key}:{value}\n" for key, value in ordered)
    return block, ";".join(key for key, _ in ordered)


def _signing_key(secret: str, datestamp: str, region: str, service: str) -> bytes:
    key = hmac.new(f"AWS4{secret}".encode(), datestamp.encode(), hashlib.sha256).digest()
    key = hmac.new(key, region.encode(), hashlib.sha256).digest()
    key = hmac.new(key, service.encode(), hashlib.sha256).digest()
    return hmac.new(key, b"aws4_request", hashlib.sha256).digest()


def _scope(datestamp: str, region: str, service: str) -> str:
    return f"{datestamp}/{region}/{service}/aws4_request"


def _string_to_sign(amz_date: str, scope: str, canonical_request: str) -> str:
    return "\n".join(
        [
            ALGORITHM,
            amz_date,
            scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ]
    )


def _stamp(now: datetime | None) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)


def sign_request(
    method: str,
    url: str,
    credentials: Credentials,
    headers: dict | None = None,
    payload: bytes = b"",
    now: datetime | None = None,
) -> dict:
    """Return the headers to send, including ``Authorization``."""
    moment = _stamp(now)
    amz_date = moment.strftime("%Y%m%dT%H%M%SZ")
    datestamp = moment.strftime("%Y%m%d")
    scope = _scope(datestamp, REGION, SERVICE)

    split = urllib.parse.urlsplit(url)
    body = payload or b""
    payload_hash = hashlib.sha256(body).hexdigest()

    outgoing = dict(headers or {})
    outgoing["host"] = split.netloc
    outgoing["x-amz-date"] = amz_date
    outgoing["x-amz-content-sha256"] = payload_hash
    if body:
        outgoing["content-length"] = str(len(body))

    canonical_headers, signed_headers = _canonical_headers(outgoing)
    canonical_request = "\n".join(
        [
            method.upper(),
            canonical_uri(split.path),
            canonical_query_string(urllib.parse.parse_qsl(split.query, keep_blank_values=True)),
            canonical_headers,
            signed_headers,
            payload_hash,
        ]
    )
    signature = hmac.new(
        _signing_key(credentials.secret_access_key, datestamp, REGION, SERVICE),
        _string_to_sign(amz_date, scope, canonical_request).encode(),
        hashlib.sha256,
    ).hexdigest()
    outgoing["Authorization"] = (
        f"{ALGORITHM} Credential={credentials.access_key_id}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return outgoing


def presign_url(
    method: str,
    url: str,
    credentials: Credentials,
    expires: int = 900,
    now: datetime | None = None,
    extra_params: dict | None = None,
) -> str:
    """A query-signed URL that expires. For private buckets only."""
    moment = _stamp(now)
    amz_date = moment.strftime("%Y%m%dT%H%M%SZ")
    datestamp = moment.strftime("%Y%m%d")
    scope = _scope(datestamp, REGION, SERVICE)
    expires = max(1, min(int(expires), 604800))

    split = urllib.parse.urlsplit(url)
    params = dict(extra_params or {})
    params.update(
        {
            "X-Amz-Algorithm": ALGORITHM,
            "X-Amz-Credential": f"{credentials.access_key_id}/{scope}",
            "X-Amz-Date": amz_date,
            "X-Amz-Expires": str(expires),
            "X-Amz-SignedHeaders": "host",
        }
    )

    canonical_request = "\n".join(
        [
            method.upper(),
            canonical_uri(split.path),
            canonical_query_string(params),
            f"host:{split.netloc}\n",
            "host",
            UNSIGNED_PAYLOAD,
        ]
    )
    signature = hmac.new(
        _signing_key(credentials.secret_access_key, datestamp, REGION, SERVICE),
        _string_to_sign(amz_date, scope, canonical_request).encode(),
        hashlib.sha256,
    ).hexdigest()

    params["X-Amz-Signature"] = signature
    query = "&".join(f"{_quote(key)}={_quote(value)}" for key, value in params.items())
    return urllib.parse.urlunsplit(
        (split.scheme, split.netloc, canonical_uri(split.path), query, "")
    )


# -- transport -------------------------------------------------------------


def _timeout() -> float:
    return float(getattr(settings, "R2_REQUEST_TIMEOUT", 8))


def _perform(method: str, url: str, headers: dict, body: bytes | None = None) -> tuple[int, bytes]:
    """One bounded HTTP call. Returns (status, body) or raises R2Error."""
    request = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=_timeout()) as response:
            return response.status, response.read(MAX_RESPONSE_BYTES)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(MAX_RESPONSE_BYTES)
    except (urllib.error.URLError, socket.timeout, ssl.SSLError, TimeoutError) as exc:
        reason = getattr(exc, "reason", None) or exc
        if isinstance(reason, (socket.timeout, TimeoutError)):
            message = (
                f"Cloudflare did not answer within {_timeout():.0f} seconds. "
                "Check the server's outbound network, then try again."
            )
        else:
            message = (
                "Could not reach Cloudflare from this server "
                f"({type(reason).__name__}). Check the outbound network or a proxy."
            )
        raise R2Error(message, None) from exc


_READ_HINTS = {
    400: "Cloudflare rejected the request. Check the account id and the bucket name.",
    401: "The access key id was not recognised. Paste the token again.",
    403: "Access denied. The API token needs Object Read & Write for this bucket.",
    404: "No bucket with that name in this Cloudflare account.",
    409: "Cloudflare reported a conflict. Try again in a moment.",
    429: "Cloudflare is rate-limiting this account. Try again later.",
    500: "Cloudflare had a server error. Try again later.",
    503: "Cloudflare is unavailable right now. Try again later.",
}


def _explain(status: int) -> str:
    return _READ_HINTS.get(status, f"Cloudflare answered HTTP {status}.")


def _list_url(credentials: Credentials, bucket: str, max_keys: int = 1, prefix: str = "") -> str:
    params = {"list-type": "2", "max-keys": str(max(0, min(int(max_keys), 1000)))}
    if prefix:
        params["prefix"] = prefix
    base = endpoint_url(credentials.account_id, bucket)
    return f"{base}?{urllib.parse.urlencode(params)}"


def _parse_xml_tags(body: bytes, tag: str) -> list[str]:
    """Tiny extractor for the two S3 fields this module needs."""
    text = body.decode("utf-8", "replace")
    start_tag, end_tag = f"<{tag}>", f"</{tag}>"
    values = []
    cursor = 0
    while True:
        start = text.find(start_tag, cursor)
        if start == -1:
            break
        start += len(start_tag)
        end = text.find(end_tag, start)
        if end == -1:
            break
        values.append(text[start:end])
        cursor = end + len(end_tag)
    return values


def check_bucket(
    credentials: Credentials, bucket: str, now: datetime | None = None
) -> BucketCheck:
    """List one key from the bucket. Read-only, bounded, non-destructive."""
    if not credentials or not credentials.access_key_id or not credentials.secret_access_key:
        return BucketCheck(False, None, "No API token is stored for this account.")
    url = _list_url(credentials, bucket, max_keys=1)
    headers = sign_request("GET", url, credentials, now=now)
    try:
        status, body = _perform("GET", url, headers)
    except R2Error as exc:
        return BucketCheck(False, None, str(exc))

    if status == 200:
        keys = _parse_xml_tags(body, "Key")
        if keys:
            return BucketCheck(True, status, "Connected. The bucket answered and lists objects.")
        return BucketCheck(True, status, "Connected. The bucket is reachable and currently empty.")
    return BucketCheck(False, status, _explain(status))


def presign_get(
    credentials: Credentials,
    bucket: str,
    key: str,
    expires: int | None = None,
    now: datetime | None = None,
) -> str:
    if not key or key.startswith("/"):
        raise R2Error("An object key is required.")
    ttl = expires if expires is not None else getattr(settings, "R2_SIGNED_URL_TTL", 900)
    url = endpoint_url(credentials.account_id, bucket, key)
    return presign_url("GET", url, credentials, expires=ttl, now=now)


def put_object(
    credentials: Credentials,
    bucket: str,
    key: str,
    body: bytes,
    content_type: str = "application/octet-stream",
    now: datetime | None = None,
) -> None:
    url = endpoint_url(credentials.account_id, bucket, key)
    headers = sign_request(
        "PUT",
        url,
        credentials,
        headers={"content-type": content_type},
        payload=body,
        now=now,
    )
    status, _ = _perform("PUT", url, headers, body=body)
    if status not in (200, 201):
        raise R2Error(_explain(status), status)


def delete_object(
    credentials: Credentials, bucket: str, key: str, now: datetime | None = None
) -> None:
    url = endpoint_url(credentials.account_id, bucket, key)
    headers = sign_request("DELETE", url, credentials, now=now)
    status, _ = _perform("DELETE", url, headers)
    if status not in (200, 204, 404):
        raise R2Error(_explain(status), status)


def object_head(
    credentials: Credentials, bucket: str, key: str, now: datetime | None = None
) -> int:
    """Status of a HEAD on one object — used to prove an upload landed."""
    url = endpoint_url(credentials.account_id, bucket, key)
    headers = sign_request("HEAD", url, credentials, now=now)
    status, _ = _perform("HEAD", url, headers)
    return status
