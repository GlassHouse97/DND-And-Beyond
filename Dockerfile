# Single-container production image for DND and Beyond (Reflex app).
# Based on Reflex's official docker-example/simple-one-port:
# Caddy serves the static frontend and proxies backend routes (including the
# websocket) on ONE port, so this works on Railway, Render, Fly.io, etc.
#
# Platform checklist:
#   - Set DATABASE_URL for Postgres on serverless platforms like Cloud Run.
#   - Set API_URL (as a build-time variable) to the app's public URL,
#     e.g. https://your-app.up.railway.app — then redeploy so the frontend
#     is compiled pointing at itself.
#   - Set APP_BASE_URL and the SMTP_* variables for verification emails.
FROM node:22-bookworm-slim AS node

FROM python:3.13-bookworm

# Reflex needs Node 22.12+ to initialize and build the frontend.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -sf ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
    ln -sf ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# Render expects 10000; Railway respects $PORT automatically.
ARG PORT=8080
# Public URL of the deployed app (frontend and backend share one origin).
ARG API_URL
ENV PORT=$PORT \
    REFLEX_API_URL=${API_URL:-http://localhost:$PORT} \
    REFLEX_REDIS_URL=redis://localhost \
    REFLEX_BACKEND_PORT=8000 \
    DND_DATA_DIR=/data \
    PYTHONUNBUFFERED=1

RUN apt-get update -y && apt-get install -y caddy redis-server && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir .

# Deploy templates and prepare app
RUN reflex init

# Compile the static frontend, baking in REFLEX_API_URL.
RUN reflex export --frontend-only --no-zip && mv .web/build/client/* /srv/ && rm -rf .web

# Persistent data lives on the platform volume mounted here.
RUN mkdir -p /data

RUN sed -i 's/\r$//' /app/cloudrun_start.sh && chmod +x /app/cloudrun_start.sh

# Needed until Reflex properly passes SIGTERM on backend.
STOPSIGNAL SIGKILL

EXPOSE $PORT

CMD ["/app/cloudrun_start.sh"]
