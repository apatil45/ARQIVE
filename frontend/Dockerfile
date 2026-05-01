# ARQIVE frontend. Node 20 + Vite (per .cursorrules).
FROM node:20-alpine

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci 2>/dev/null || npm install
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]
