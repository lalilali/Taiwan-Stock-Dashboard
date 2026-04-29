FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 80

ENV TZ=Asia/Taipei \
    PYTHONUNBUFFERED=1

# IMPORTANT: The healthcheck URL must also include the base path
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -sf http://localhost:80/k8s/rat-trade/v1/_stcore/health || exit 1

CMD ["streamlit", "run", "dashboard.py", \
     "--server.port=80", \
     "--server.address=0.0.0.0", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false", \
     "--server.baseUrlPath=/k8s/rat-trade/v1"]
