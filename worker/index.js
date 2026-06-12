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

export default {
  async fetch(request, env) {
    const container = getContainer(env.FASTAPI, "api");
    return container.fetch(request);
  },
};
