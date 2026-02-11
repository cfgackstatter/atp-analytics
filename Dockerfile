FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn uvicorn

# Install Playwright browsers in a consistent location
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install chromium
RUN playwright install-deps chromium

# Verify installation works
RUN python -c "from playwright.sync_api import sync_playwright; \
    p = sync_playwright().start(); \
    browser = p.chromium.launch(headless=True); \
    print('✓ Chromium installed successfully'); \
    browser.close(); \
    p.stop()"

# Copy application code
COPY backend/ ./backend/
COPY application.py .

EXPOSE 8000

# Create temp directory for Chromium
RUN mkdir -p /tmp/chromium-tmp && chmod 777 /tmp/chromium-tmp
ENV TMPDIR=/tmp/chromium-tmp

# Ensure Playwright can find browsers
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

CMD ["gunicorn", "application:application", \
     "-b", "0.0.0.0:8000", \
     "--workers", "1", \
     "--timeout", "300", \
     "--worker-class", "uvicorn.workers.UvicornWorker"]
