FROM alpine:latest
RUN apk add --no-cache python3 py3-pip python3-dev build-base git
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python3", "main.py"]