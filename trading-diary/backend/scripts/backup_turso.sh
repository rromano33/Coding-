#!/bin/bash
# Backup diário do banco Turso de produção pro Mac local.
#
# Pré-requisito: Turso CLI instalado e autenticado (`turso auth login`) —
# ver trading-diary/DEPLOY_CHECKLIST.md. Roda via launchd, ver
# com.ricardoromano.trading-diary-backup.plist neste mesmo diretório.
#
# Uso: backup_turso.sh <nome-do-banco-turso>

set -euo pipefail

# launchd não carrega .bash_profile/.zprofile — garante que o turso CLI
# (instalado em ~/.turso pelo instalador oficial) é encontrado mesmo assim.
export PATH="$PATH:$HOME/.turso"

DB_NAME="${1:?Uso: backup_turso.sh <nome-do-banco-turso>}"
BACKUP_DIR="$HOME/trading-diary-backups"
RETENTION_DAYS=30

if ! command -v turso >/dev/null 2>&1; then
  echo "turso CLI não encontrado no PATH. Instale com:" >&2
  echo "  curl -sSfL https://get.tur.so/install.sh | bash" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"

STAMP="$(date +%Y-%m-%d_%H%M%S)"
OUT_FILE="$BACKUP_DIR/${DB_NAME}_${STAMP}.sql"

turso db shell "$DB_NAME" .dump > "$OUT_FILE"

if [ ! -s "$OUT_FILE" ]; then
  echo "Backup vazio ou falhou — removendo $OUT_FILE" >&2
  rm -f "$OUT_FILE"
  exit 1
fi

echo "Backup salvo em $OUT_FILE"

find "$BACKUP_DIR" -name "${DB_NAME}_*.sql" -mtime "+${RETENTION_DAYS}" -delete
