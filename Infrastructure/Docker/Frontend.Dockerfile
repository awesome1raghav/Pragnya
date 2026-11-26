# syntax=docker/dockerfile:1
# NEXTRON web frontend (Next.js), production build served by the standalone Node server.
# Build from the repository root:
#   docker build -f Infrastructure/Docker/Frontend.Dockerfile --build-arg NEXT_PUBLIC_NEXTRON_API=http://localhost:8100/api/v1 -t nextron-web .
# The API address is compiled into the client bundle, so it is a build argument, not a runtime setting.

FROM node:24.22.0-bookworm-slim AS build
WORKDIR /app
COPY Frontend/Web/package.json Frontend/Web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY Frontend/Web/ ./
ARG NEXT_PUBLIC_NEXTRON_API=http://localhost:8100/api/v1
ENV NEXT_PUBLIC_NEXTRON_API=$NEXT_PUBLIC_NEXTRON_API NEXT_TELEMETRY_DISABLED=1 NEXT_OUTPUT=standalone
RUN npm run typecheck && npm run build

FROM node:24.22.0-bookworm-slim AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=8080 HOSTNAME=0.0.0.0
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=15s --retries=5 \
  CMD node -e "fetch('http://127.0.0.1:8080/').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"
CMD ["node", "server.js"]
