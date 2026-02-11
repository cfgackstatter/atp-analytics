FROM mcr.microsoft.com/playwright/python:v1.58.0-jammy

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# Set Playwright browser path
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install Playwright browsers with system dependencies
RUN playwright install chromium --with-deps

# Copy application code
COPY backend/ ./backend/
COPY application.py .

EXPOSE 8000

# Run with gunicorn
CMD ["gunicorn", "application:application", \
     "-b", "0.0.0.0:8000", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--timeout", "120", \
     "--preload"]
