#!/bin/bash
set -euo pipefail

log() {
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] $*"
}

DUMPS_DIR="/tmp/dumps"
mkdir -p "${DUMPS_DIR}"

# ── PostgreSQL dump ───────────────────────────────────────────────────────────
if [[ -n "${POSTGRES_USER:-}" && -n "${POSTGRES_PASSWORD:-}" && -n "${POSTGRES_DB:-}" ]]; then
    DUMP_FILE="${DUMPS_DIR}/postgres_${POSTGRES_DB}_$(date -u +'%Y%m%d_%H%M%S').sql"
    log "Creating PostgreSQL dump: ${DUMP_FILE}"
    PGPASSWORD="${POSTGRES_PASSWORD}" pg_dump \
        -h "${POSTGRES_HOST}" \
        -p "${POSTGRES_PORT}" \
        -U "${POSTGRES_USER}" \
        -d "${POSTGRES_DB}" \
        --no-owner \
        --no-privileges \
        -f "${DUMP_FILE}"
    log "PostgreSQL dump completed: $(du -h "${DUMP_FILE}" | cut -f1)"
else
    log "WARNING: Postgres credentials not fully configured, skipping pg_dump"
fi

# ── Restic backup of volumes + dumps ──────────────────────────────────────────
# NOTE: Postgres raw data files are NOT backed up (they can be inconsistent).
#       We rely on pg_dump above for a consistent logical backup.
log "Starting restic backup of volumes and dumps"
restic backup \
    --tag "docker-compose" \
    --tag "${HOSTNAME:-restic_backup}" \
    /root/.ollama \
    /home/node/.n8n \
    "${DUMPS_DIR}"
log "Restic backup completed"

# ── Forget/prune according to retention policy ────────────────────────────────
log "Applying retention policy: ${RESTIC_FORGET_PRUNE_ARGS}"
# shellcheck disable=SC2086
restic forget \
    --prune \
    ${RESTIC_FORGET_PRUNE_ARGS}
log "Retention policy applied"

# ── Check repository health periodically ──────────────────────────────────────
log "Running restic check"
restic check
log "Restic check completed"

# ── Cleanup old dumps locally (keep last dump only) ───────────────────────────
find "${DUMPS_DIR}" -maxdepth 1 -type f -name '*.sql' -mmin +60 -delete || true

log "Backup job finished"
