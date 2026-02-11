FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Install Playwright browsers (use default location)
RUN playwright install chromium
RUN playwright install-deps chromium

# Verify browsers are installed (build fails if not)
RUN python -c "from playwright.sync_api import sync_playwright; \
    p = sync_playwright().start(); \
    print(f'Chromium executable: {p.chromium.executable_path}'); \
    p.stop()" || (echo "ERROR: Browsers not found!" && exit 1)

# Copy application code
COPY backend/ ./backend/
COPY application.py .

EXPOSE 8000

CMD ["gunicorn", "application:application", \
     "-b", "0.0.0.0:8000", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--timeout", "120"]
