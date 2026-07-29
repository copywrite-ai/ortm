FROM node:22-alpine

WORKDIR /opt/ortm

COPY package.json ./
COPY src ./src
COPY examples/clock-sync-server.mjs ./examples/clock-sync-server.mjs

ENV HOST=0.0.0.0
ENV PORT=9011

EXPOSE 9011

USER node

CMD ["node", "examples/clock-sync-server.mjs"]
