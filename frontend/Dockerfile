# Prism Earth frontend image (SRS §32). Next.js 14 dev server for local compose.
# A production multi-stage build (next build / next start) is added in Phase 8.
FROM node:22-alpine

WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

# Install dependencies first (cached unless package manifests change).
COPY package.json package-lock.json* ./
RUN npm install

# Copy the rest of the application.
COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
