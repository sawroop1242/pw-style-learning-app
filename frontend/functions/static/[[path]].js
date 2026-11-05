import { proxyToDjango } from "../_lib/proxy.js";

export function onRequest(context) {
  return proxyToDjango(context);
}
