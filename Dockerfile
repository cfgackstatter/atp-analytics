FROM node:22-slim AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM mcr.microsoft.com/playwright/python:v1.62.0-jammy

WORKDIR /app

ENV PYTHONUNBUFFERED=1

# Install Python dependencies (includes gunicorn / uvicorn)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Official Playwright image already ships browsers; keep path consistent.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
ENV TMPDIR=/tmp/chromium-tmp
RUN mkdir -p /tmp/chromium-tmp && chmod 777 /tmp/chromium-tmp

# Copy application code
COPY backend/ ./backend/
COPY application.py .

# Copy built frontend from builder stage
COPY --from=frontend-builder /frontend/dist ./backend/static/

EXPOSE 8000

# Scrapes run in a dedicated subprocess (see backend/api/job_manager.py),
# so the web worker only needs a modest request timeout.
CMD ["gunicorn", "application:application", \
     "-b", "0.0.0.0:8000", \
     "--workers", "1", \
     "--timeout", "120", \
     "--worker-class", "uvicorn.workers.UvicornWorker"]
