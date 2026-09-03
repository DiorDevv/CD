FROM node:20-alpine

WORKDIR /app

# Docker ichida ekanini vite.config.ts bilsin (HMR polling uchun)
ENV DOCKER=1

# --- Proksi (internetsiz VM: build vaqti npm Squid orqali chiqadi) -----------
# npm standart HTTP_PROXY'ni har doim hurmat qilmaydi -> npm_config_* ham beramiz.
ARG HTTP_PROXY=
ARG HTTPS_PROXY=
ARG NO_PROXY=
ENV HTTP_PROXY=${HTTP_PROXY} \
    HTTPS_PROXY=${HTTPS_PROXY} \
    NO_PROXY=${NO_PROXY} \
    http_proxy=${HTTP_PROXY} \
    https_proxy=${HTTPS_PROXY} \
    no_proxy=${NO_PROXY} \
    npm_config_proxy=${HTTP_PROXY} \
    npm_config_https_proxy=${HTTPS_PROXY}

# Backend API manzili — docker-compose `build.args` orqali beriladi
ARG VITE_API_BASE_URL=http://localhost:8000/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev"]
