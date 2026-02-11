FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn uvicorn

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

# Verify installation
RUN python -c "from playwright.sync_api import sync_playwright; \
    p = sync_playwright().start(); \
    print(f'Chromium: {p.chromium.executable_path}'); \
    p.stop()"

# Copy application code
COPY backend/ ./backend/
COPY application.py .

EXPOSE 8000

# Environment for Playwright
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright
RUN mkdir -p /tmp/chromium-tmp
ENV TMPDIR=/tmp/chromium-tmp

CMD ["gunicorn", "application:application", \
     "-b", "0.0.0.0:8000", \
     "--workers", "1", \
     "--timeout", "300", \
     "--worker-class", "uvicorn.workers.UvicornWorker"]
