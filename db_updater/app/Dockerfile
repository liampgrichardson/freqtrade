# Use a Python base image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy your local project files to the container
COPY . .

# Install dependencies
RUN pip install -r requirements.txt

# Set the command to run your script
CMD ["python", "app.py"]
