# Use the official Python image with version 3.10 as a base image
FROM python:3.10

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt /app/

# Install any dependencies specified in requirements.txt
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . /app

# Define the command to run your application
CMD ["python3", "main.py"]
