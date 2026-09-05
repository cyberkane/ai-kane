FROM alpine:latest

# Устанавливаем Python 3, pip и базовые зависимости для сборки
RUN apk add --no-cache python3 py3-pip python3-dev build-base

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

COPY . .

# Открываем порт 8000 наружу для VS Code
EXPOSE 8000

CMD ["python3", "main.py"]