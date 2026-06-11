# Dev image — docker-compose mounts the source dir over /app for hot reload.
# A production multi-stage build (next build + standalone output) comes in Phase 5.
FROM node:22-alpine

WORKDIR /app

# Same layer-caching trick as the backend: dependencies install only re-runs
# when package.json / package-lock.json change, not on every code edit.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
