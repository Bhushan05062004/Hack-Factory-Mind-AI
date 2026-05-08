FROM python:3.12-slim

WORKDIR /app

# Install system deps for faiss
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directory
RUN mkdir -p /app/data

# Make start script executable
RUN chmod +x start.sh

EXPOSE 8000

# Seed database + FAISS on first boot, then start server
CMD ["./start.sh"]
