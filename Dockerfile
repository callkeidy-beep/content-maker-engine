FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Asia/Seoul
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY config ./config
COPY prompts ./prompts
COPY templates ./templates
COPY samples ./samples
RUN useradd -m engine && mkdir -p /app/data && chown -R engine /app/data
USER engine
EXPOSE 3100
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3100"]
