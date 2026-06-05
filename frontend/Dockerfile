# Dev-oriented image: runs the Vite dev server with the /api proxy so the
# browser talks to one origin. Swap for an nginx static build for prod.
FROM node:22-slim
WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev"]
