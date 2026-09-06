FROM alpine:latest
RUN apk add --no-cache python3 py3-pip curl
WORKDIR /app
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8977
CMD ["python3", "main.py"]