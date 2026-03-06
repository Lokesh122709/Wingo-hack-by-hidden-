# Use official Python 3.10 slim image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if any needed, e.g., for building some packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot script (assuming it's named bot.py in the same directory)
COPY bot.py .

# Expose Flask web server port
EXPOSE 5000

# Run the bot
CMD ["python", "bot.py"]
