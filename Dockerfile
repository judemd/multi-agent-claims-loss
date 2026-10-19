FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY claimcascade ./claimcascade
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-cache-dir --no-deps .
COPY app.py ./
COPY fixtures ./fixtures
RUN useradd --create-home appuser && mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "python -m streamlit run app.py --server.address=0.0.0.0 --server.port=$PORT --server.headless=true --browser.gatherUsageStats=false"]
