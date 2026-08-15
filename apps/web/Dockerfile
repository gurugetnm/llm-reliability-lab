# Built with repo root as context (see docker-compose.yml) so pnpm can
# resolve the workspace lockfile shared with the rest of the monorepo.
#
# Development image: runs `next dev` against the source bind-mounted by
# docker-compose. A production build stage will be added when the app
# ships beyond local development.
FROM node:22-slim

WORKDIR /app
RUN corepack enable

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN corepack pnpm install --frozen-lockfile

COPY apps/web apps/web

WORKDIR /app/apps/web
EXPOSE 3000

CMD ["corepack", "pnpm", "dev"]
