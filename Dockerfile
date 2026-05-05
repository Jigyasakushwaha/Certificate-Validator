FROM python:3.10

# Install tesseract
RUN apt-get update && apt-get install -y tesseract-ocr

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Install dependencies
RUN pip install -r requirements.txt

# Run app
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]