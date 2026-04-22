FROM node:20-alpine

WORKDIR /app

COPY src/package.json src/package-lock.json* src/yarn.lock* src/pnpm-lock.yaml* ./
RUN npm install

COPY src/ .

EXPOSE 3000

CMD ["sh", "-c", "npm install && npm run dev -- --host 0.0.0.0 --port 3000"]
