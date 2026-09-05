FROM alpine:latest

# Устанавливаем только Python 3 и менеджер пакетов pip
RUN apk add --no-cache python3 py3-pip

WORKDIR /app

# Копируем и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

# Копируем все остальные файлы проекта
COPY . .

CMD ["python3", "main.py"]