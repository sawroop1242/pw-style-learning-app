"""Minimal function used to tell "the Python runtime is broken" apart from
"this particular application fails to import".

It imports nothing beyond the standard library and the platform's own runtime,
so a failure here means the function was never built or the runtime is
mismatched -- not that Django, the database or the settings are at fault.
"""


def app(environ, start_response):
    body = b"pong"
    start_response(
        "200 OK",
        [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


handler = app
