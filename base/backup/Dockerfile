# Stage 1: получаем restic из официального образа
FROM restic/restic:0.16.1 AS restic-bin

# Stage 2: наш образ на базе alpine
FROM alpine:3.20

RUN apk add --no-cache \
    bash \
    ca-certificates \
    postgresql16-client \
    tzdata \
    jq \
    openssh-client \
    rclone \
    && rm -rf /var/cache/apk/*

# Копируем restic из официального образа
COPY --from=restic-bin /usr/bin/restic /usr/local/bin/restic

RUN mkdir -p /tmp/dumps /app /backup-target

COPY backup.sh /app/backup.sh
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/backup.sh /app/entrypoint.sh

WORKDIR /app
ENTRYPOINT ["/app/entrypoint.sh"]
