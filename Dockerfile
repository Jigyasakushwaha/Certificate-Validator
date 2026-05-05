FROM python:3.10-slim

RUN apt-get update && apt-get install -y tesseract-ocr

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]
