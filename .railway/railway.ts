import {
  defineRailway,
  github,
  project,
  service,
} from "railway/iac";

export default defineRailway((ctx) => {
  const api = service("procurement-retrieval-api", {
    source: github("nicolaasheru/procurement-data-modernization-workbench", {
      branch: "main",
    }),
    start: "/app/scripts/start-backend.sh",
    healthcheck: "/health/ready",
    healthcheckTimeout: 600,
    replicas: 1,
    env: {
      DATABASE_URL: ctx.shared.DATABASE_URL,
      CORS_ORIGINS: ctx.shared.CORS_ORIGINS,
      EMBEDDING_MODEL: "sentence-transformers/all-MiniLM-L6-v2",
      EMBEDDING_DIMENSIONS: "384",
      RETRIEVAL_MINIMUM_SCORE: "0.25",
      WEB_CONCURRENCY: "1",
      SKIP_RETRIEVAL_INDEX: "0",
    },
  });

  return project("procurement-data-modernization-workbench", {
    resources: [api],
  });
});
