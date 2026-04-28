FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

# Install dependencies first (layer caching)
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy source
COPY src ./src
COPY scripts ./scripts

# Playwright browsers come pre-installed in this base image.
# Kameleo is a desktop app — it can't run inside the container, so the Docker
# image defaults to plain Playwright. To use Kameleo, run the bot on the host:
#     pip install -e . && playwright install chromium && python -m src
ENV PYTHONUNBUFFERED=1 \
    HEADLESS=true \
    BROWSER_MODE=playwright

CMD ["python", "-m", "src"]
