# Use official Python slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the main script
COPY bigwin_wingo.py .

# Make script executable (optional)
RUN chmod +x bigwin_wingo.py

# Default command: run WinGo30 with Server 1
# You can override this by passing arguments in Railway's Start Command
CMD ["python", "/app/bigwin_wingo.py", "30"]
