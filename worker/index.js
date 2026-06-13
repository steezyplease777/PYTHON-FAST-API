import { Container, getContainer } from "@cloudflare/containers";
import { env } from "cloudflare:workers";

export class FastApiContainer extends Container {
  defaultPort = 8080;
  sleepAfter = "15m";

  envVars = {
    SUPABASE_URL: env.SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY: env.SUPABASE_SERVICE_ROLE_KEY ?? "",
    API_TOKEN: env.API_TOKEN ?? "",
  };
}

const CORS_ALLOW_ORIGIN = "*";
const CORS_ALLOW_METHODS = "GET, POST, OPTIONS";
const CORS_ALLOW_HEADERS = "Content-Type, Authorization";
const CORS_EXPOSE_HEADERS = "Content-Disposition, X-Label-Count";
const textEncoder = new TextEncoder();

function addCorsHeaders(response) {
  const headers = new Headers(response.headers);

  headers.set("Access-Control-Allow-Origin", CORS_ALLOW_ORIGIN);
  headers.set("Access-Control-Allow-Methods", CORS_ALLOW_METHODS);
  headers.set("Access-Control-Allow-Headers", CORS_ALLOW_HEADERS);
  headers.set("Access-Control-Expose-Headers", CORS_EXPOSE_HEADERS);
  headers.set("Vary", "Origin");

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function corsPreflightResponse() {
  return new Response(null, {
    status: 204,
    headers: {
      "Access-Control-Allow-Origin": CORS_ALLOW_ORIGIN,
      "Access-Control-Allow-Methods": CORS_ALLOW_METHODS,
      "Access-Control-Allow-Headers": CORS_ALLOW_HEADERS,
      "Access-Control-Max-Age": "86400",
      "Vary": "Origin",
    },
  });
}

async function sha256(value) {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", textEncoder.encode(value)));
}

function equalBytes(left, right) {
  if (left.length !== right.length) {
    return false;
  }

  let diff = 0;
  for (let i = 0; i < left.length; i += 1) {
    diff |= left[i] ^ right[i];
  }

  return diff === 0;
}

async function isAuthorized(request, apiToken) {
  const authHeader = request.headers.get("Authorization") ?? "";
  if (!authHeader.toLowerCase().startsWith("bearer ")) {
    return false;
  }

  const candidate = authHeader.slice(7).trim();
  const [candidateHash, expectedHash] = await Promise.all([
    sha256(candidate),
    sha256(apiToken),
  ]);

  return equalBytes(candidateHash, expectedHash);
}

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return corsPreflightResponse();
    }

    if (!env.API_TOKEN) {
      return addCorsHeaders(new Response("API_TOKEN is not configured.", { status: 500 }));
    }

    if (!(await isAuthorized(request, env.API_TOKEN))) {
      return addCorsHeaders(new Response("Invalid or missing Authorization bearer token.", { status: 401 }));
    }

    const container = getContainer(env.FASTAPI, "api");
    const response = await container.fetch(request);
    return addCorsHeaders(response);
  },
};
