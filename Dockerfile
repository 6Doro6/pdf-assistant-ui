FROM python:3.10-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY requirements.txt .
RUN pip install -U pip wheel setuptools && pip install -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["bash","-lc","streamlit run ui/app.py --server.address 0.0.0.0 --server.port ${PORT:-8080}"]
