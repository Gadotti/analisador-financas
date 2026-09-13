# Imagem única: o Node não tem dependências de produção (só `jest`, em
# devDependencies), então não há estágio de build nem compilador nativo — só
# o runtime do Node e o Python que roda `scripts/analisar.py`.
FROM node:22-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python-is-python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY . .

RUN mkdir -p /app/data

EXPOSE 8765

# HOST=0.0.0.0 para o docker-compose.yml publicar a porta (veja
# src/server/index.js). --sem-navegador porque não há navegador no container.
ENV HOST=0.0.0.0

CMD ["node", "src/server/index.js", "--sem-navegador"]
