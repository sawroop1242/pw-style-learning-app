const DEFAULT_BACKEND_ORIGIN = "https://studyspace-swroopss487-4609.vercel.app";

export async function proxyToDjango(context) {
  const incoming = new URL(context.request.url);
  const backendOrigin = (context.env.BACKEND_ORIGIN || DEFAULT_BACKEND_ORIGIN).replace(/\/$/, "");
  const upstreamUrl = new URL(incoming.pathname + incoming.search, backendOrigin);
  const headers = new Headers(context.request.headers);

  // The browser talks to this Pages origin. Present the trusted backend origin
  // upstream so Django's CSRF Origin validation sees the backend host.
  if (headers.has("Origin")) headers.set("Origin", backendOrigin);
  headers.set("X-Forwarded-Host", incoming.host);
  headers.set("X-Forwarded-Proto", incoming.protocol.replace(":", ""));
  headers.delete("Host");

  const method = context.request.method.toUpperCase();
  const init = {
    method,
    headers,
    redirect: "manual",
  };
  if (method !== "GET" && method !== "HEAD") init.body = context.request.body;

  const upstream = await fetch(new Request(upstreamUrl, init));
  const responseHeaders = new Headers(upstream.headers);

  // Keep redirects on the public frontend origin instead of sending students
  // back to the backend's Vercel hostname.
  const location = responseHeaders.get("Location");
  if (location) {
    try {
      const redirectUrl = new URL(location, backendOrigin);
      if (redirectUrl.origin === backendOrigin) {
        responseHeaders.set("Location", incoming.origin + redirectUrl.pathname + redirectUrl.search + redirectUrl.hash);
      }
    } catch {
      // Preserve non-URL Location values unchanged.
    }
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}
