FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir poetry==1.8.2 && poetry config virtualenvs.create false && poetry install --no-dev --no-interaction --no-ansi
CMD ["uvicorn", "flight_delay_bayes.api.main:app", "--host", "0.0.0.0", "--port", "8000"] 