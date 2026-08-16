FROM node:20-alpine

WORKDIR /app

# Install native build tools for compiling better-sqlite3
RUN apk add --no-cache python3 make g++

COPY package.json tsconfig.json ./
RUN npm install

COPY src/ ./src/
RUN npm run build

EXPOSE 8000

CMD ["npm", "run", "start"]
