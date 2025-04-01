# Use a lightweight Python image as a base
FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Install necessary system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    curl \
    google-chrome-stable \
    chromedriver \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for Google Chrome and ChromeDriver
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROMEDRIVER_BIN=/usr/bin/chromedriver

# Copy the dependencies file and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project files
COPY . .

# Run the script
CMD ["python", "main.py"]
