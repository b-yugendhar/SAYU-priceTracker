# Use official Python runtime
FROM python:3.11-slim

# Set working directory
WORKDIR /app
# Install system dependencies required for Headless Chrome and Selenium
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    ca-certificates \
    && wget -q -O /usr/share/keyrings/google-chrome.gpg https://dl.google.com/linux/linux_signing_key.pub \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Copy local requirements and install Python dependencies
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Remove webdriver-manager auto-install cache mechanisms in prod if needed, 
# although webdriver-manager handles it gracefully.

# Copy everything else
COPY . .

# Expose port (Render automatically listens on the port you expose or default)
EXPOSE 5000

# Run in production matching 1 worker and multiple threads to avoid duplicating APScheduler
CMD ["gunicorn", "-w", "1", "--threads", "4", "-b", "0.0.0.0:5000", "app:app"]
