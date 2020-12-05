FROM caddy:2.1.1-alpine

RUN addgroup -g 1001 -S caddy && \
    adduser -u 1001 -D -S -G caddy caddy && \
    chown -R caddy:caddy /config /data

USER caddy

COPY Caddyfile /etc/caddy/Caddyfile

VOLUME [ "/data", "/config", "/app" ]

EXPOSE 8000
