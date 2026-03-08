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

# Make script executable
RUN chmod +x bigwin_wingo.py

# Default command: run both games (WinGo1 and WinGo30)
# You can override with "1" or "30" to run only one game
CMD ["python", "/app/bigwin_wingo.py", "both"]
