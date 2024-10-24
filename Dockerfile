# Use the official Python image from Docker Hub
FROM arm32v7/python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install system packages
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    python3-dev \
    libffi-dev \
    libssl-dev \
    && apt-get clean

# Copy the requirements file into the container
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Command to run the application
CMD ["python", "disbot.py"]