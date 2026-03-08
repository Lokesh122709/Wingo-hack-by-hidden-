# Use official Python slim image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the main script
COPY bigwin_wingo.py .

# Make the script executable
RUN chmod +x bigwin_wingo.py

# Run the script (arguments can be passed via docker run)
ENTRYPOINT ["python", "/app/bigwin_wingo.py"]
