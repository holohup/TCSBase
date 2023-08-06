FROM arm64v8/python:3.11.4-slim-bullseye as base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


FROM arm64v8/python:3.11.4-slim-bullseye
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY --from=base /usr/local/lib/python3.11/site-packages/ /usr/local/lib/python3.11/site-packages/
COPY --from=base /usr/local/bin/ /usr/local/bin/
WORKDIR /app
COPY . .
CMD ["uvicorn", "main:app", "--reload", "--host", "0", "--port", "5001"]
