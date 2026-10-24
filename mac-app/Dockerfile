# For cloud hosting (Render, Railway, Fly). Reddit only works there with REDDIT_CLIENT_ID/SECRET set.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV HOST=0.0.0.0 PORT=8787 TOPIC_SCOUT_DATA=/data
EXPOSE 8787
CMD ["python", "server.py"]
