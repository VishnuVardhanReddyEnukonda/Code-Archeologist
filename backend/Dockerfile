# Stage 1: Build Stage
FROM python:3.12-slim AS builder
WORKDIR /build

# Install only the tools needed to compile packages
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install dependencies into a specific folder
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Final Runtime Stage
FROM python:3.12-slim
WORKDIR /app

# Copy only the installed packages from the builder (No GCC, No Compilers)
COPY --from=builder /install /usr/local
COPY . .

# Ensure temp excavation directory exists
RUN mkdir -p /tmp/excavation_site && chmod 777 /tmp/excavation_site

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]