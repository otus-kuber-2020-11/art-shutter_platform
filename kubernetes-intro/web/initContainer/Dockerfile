FROM alpine

RUN apk add wget --no-cache && \
    addgroup -g 1001 -S caddy && \
    adduser -u 1001 -D -S -G caddy caddy

USER caddy

VOLUME [ "/app" ]
