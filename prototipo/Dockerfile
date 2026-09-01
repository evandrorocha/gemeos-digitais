# Imagem base Python 3.12 Slim (leve e compatível com todas as bibliotecas)
FROM python:3.12-slim

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala requisitos Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código do Gêmeo Digital e do Dashboard
COPY gemeo-digital/ ./gemeo-digital/
COPY dashboard/ ./dashboard/

# Define variáveis de ambiente padrão
ENV PYTHONUNBUFFERED=1
ENV OPCUA_SERVER_URL="opc.tcp://host.docker.internal:4840"

# Expõe a porta do Dashboard Streamlit
EXPOSE 8501

# Comando de inicialização
CMD ["streamlit", "run", "dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
