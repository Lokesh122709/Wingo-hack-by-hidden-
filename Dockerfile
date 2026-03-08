# Use official Python image
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

# Run the script with arguments (game_id and server mode)
# Example: docker run ... 1    -> WinGo1, Server1
#         docker run ... 30 /sc -> WinGo30, Server2
CMD ["python", "/app/bigwin_wingo.py"]
