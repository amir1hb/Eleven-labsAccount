FROM python:3.11-slim

# نصب پیش‌نیازهای سیستمی Playwright
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && apt-get clean

WORKDIR /app

COPY . .

# ارتقاء pip و نصب وابستگی‌ها
RUN pip install --upgrade pip
RUN pip install -e .

# نصب مرورگر Chromium و وابستگی‌های سیستمی آن
RUN playwright install chromium
RUN playwright install-deps

EXPOSE 3000
CMD ["python", "-m", "src"]
