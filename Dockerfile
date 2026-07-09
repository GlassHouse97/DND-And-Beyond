# Single-container production image for DND and Beyond (Reflex app).
# Based on Reflex's official docker-example/simple-one-port:
# Caddy serves the static frontend and proxies backend routes (including the
# websocket) on ONE port, so this works on Railway, Render, Fly.io, etc.
#
# Platform checklist:
#   - Mount a persistent volume at /data (the SQLite database lives there).
#   - Set API_URL (as a build-time variable) to the app's public URL,
#     e.g. https://your-app.up.railway.app — then redeploy so the frontend
#     is compiled pointing at itself.
#   - Set APP_BASE_URL and the SMTP_* variables for verification emails.
FROM python:3.13

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

# Needed until Reflex properly passes SIGTERM on backend.
STOPSIGNAL SIGKILL

EXPOSE $PORT

CMD caddy start && \
    redis-server --daemonize yes && \
    exec reflex run --env prod --backend-only
