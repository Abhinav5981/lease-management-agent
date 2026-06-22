# ── Stage 1: install dependencies ──────────────────────────────────────────
FROM node:20-alpine AS deps

WORKDIR /app

COPY package*.json ./
RUN npm install

# ── Stage 2: build ──────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# BACKEND_URL is the internal Docker hostname used by the Next.js server
# to proxy /api/* requests. Passed as a build arg from docker-compose.
ARG BACKEND_URL=http://backend:8000
ENV BACKEND_URL=$BACKEND_URL

RUN npm run build

# ── Stage 3: production runner ──────────────────────────────────────────────
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

RUN addgroup -g 1001 nodejs && adduser -u 1001 -G nodejs -s /bin/sh -D nextjs

# public/ is optional — create empty dir if project has none
RUN mkdir -p ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

USER nextjs

EXPOSE 3000

CMD ["npm", "start"]
