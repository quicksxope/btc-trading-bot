FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY engine ./engine
COPY bot ./bot
COPY worker ./worker
COPY storage ./storage
COPY configs ./configs
COPY scripts ./scripts
RUN pip install --no-cache-dir -e .
CMD ["backtest-bot"]
