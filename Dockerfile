FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install system dependencies (optional)
RUN apt-get update && apt-get install -y curl

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 7860

# Default command for web (can be overridden by deploy/runtime platform)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
