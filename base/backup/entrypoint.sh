#!/bin/bash
set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
RESTIC_REPOSITORY="${RESTIC_REPOSITORY:?RESTIC_REPOSITORY must be set}"
RESTIC_PASSWORD="${RESTIC_PASSWORD:?RESTIC_PASSWORD must be set}"
BACKUP_CRON_SCHEDULE="${BACKUP_CRON_SCHEDULE:-0 2 * * *}"
RESTIC_FORGET_PRUNE_ARGS="${RESTIC_FORGET_PRUNE_ARGS:---keep-daily 7 --keep-weekly 4 --keep-monthly 3}"
POSTGRES_HOST="${POSTGRES_HOST:-postgres_dev}"
POSTGRES_PORT="${POSTGRES_PORT:-9001}"
POSTGRES_USER="${POSTGRES_USER:-}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"
POSTGRES_DB="${POSTGRES_DB:-}"

export RESTIC_REPOSITORY RESTIC_PASSWORD

log() {
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"
}

# ── Initialize repository (idempotent) ────────────────────────────────────────
init_repository() {
    log "Initializing/checking restic repository: ${RESTIC_REPOSITORY}"
    if restic snapshots >/dev/null 2>&1; then
        log "Repository already initialized."
    else
        log "Repository not found or not initialized, running init..."
        restic init
        log "Repository initialized."
    fi
}

# ── Write environment for cron ────────────────────────────────────────────────
write_cron_env() {
    local env_file="/etc/restic_backup.env"
    {
        echo "RESTIC_REPOSITORY=${RESTIC_REPOSITORY}"
        echo "RESTIC_PASSWORD=${RESTIC_PASSWORD}"
        echo "RESTIC_FORGET_PRUNE_ARGS=${RESTIC_FORGET_PRUNE_ARGS}"
        echo "POSTGRES_HOST=${POSTGRES_HOST}"
        echo "POSTGRES_PORT=${POSTGRES_PORT}"
        echo "POSTGRES_USER=${POSTGRES_USER}"
        echo "POSTGRES_PASSWORD=${POSTGRES_PASSWORD}"
        echo "POSTGRES_DB=${POSTGRES_DB}"
        echo "PATH=${PATH}"
    } > "${env_file}"
    chmod 600 "${env_file}"
}

# ── Setup cron ────────────────────────────────────────────────────────────────
setup_cron() {
    write_cron_env
    local cron_job="${BACKUP_CRON_SCHEDULE} root . /etc/restic_backup.env; /app/backup.sh >> /var/log/restic_backup.log 2>&1"
    echo "${cron_job}" > /etc/cron.d/restic_backup
    chmod 644 /etc/cron.d/restic_backup
    log "Cron scheduled: ${BACKUP_CRON_SCHEDULE}"
}

# ── Main ──────────────────────────────────────────────────────────────────────
log "Starting restic backup container"
log "Repository: ${RESTIC_REPOSITORY}"
log "Cron schedule: ${BACKUP_CRON_SCHEDULE}"
log "Retention: ${RESTIC_FORGET_PRUNE_ARGS}"

init_repository
setup_cron

# Ensure log file exists before tailing
touch /var/log/restic_backup.log

# Run backup once at startup as a sanity check, then tail logs.
/app/backup.sh

# Keep container alive and stream cron logs to stdout for docker logs.
tail -F /var/log/restic_backup.log &
exec crond -f -l 8
