#!/bin/bash
# 自动化数据备份脚本

set -e

BACKUP_DIR="${BACKUP_DIR:-/opt/quant-bot-backups}"
DATA_DIR="${DATA_DIR:-/opt/quant-bot/data}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/data_backup_${TIMESTAMP}.tar.gz"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 创建备份目录
mkdir -p "$BACKUP_DIR"

log "Starting backup..."

# 检查数据目录是否存在
if [ ! -d "$DATA_DIR" ]; then
    log "ERROR: Data directory $DATA_DIR does not exist"
    exit 1
fi

# 打包数据
log "Creating backup archive..."
tar -czf "$BACKUP_FILE" -C "$DATA_DIR" . 2>/dev/null

if [ $? -eq 0 ]; then
    log "✅ Backup completed: $BACKUP_FILE"
    log "   Size: $(du -h "$BACKUP_FILE" | cut -f1)"

    # 保留最近N天的备份
    log "Cleaning old backups (keeping last $RETENTION_DAYS days)..."
    find "$BACKUP_DIR" -name "data_backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete

    # 显示当前备份列表
    log "Current backups:"
    ls -lh "$BACKUP_DIR" | tail -5

    # 可选: 上传到阿里云OSS（需要配置ossutil）
    if command -v ossutil &> /dev/null && [ -n "${OSS_BUCKET}" ]; then
        log "Uploading to Aliyun OSS..."
        ossutil cp "$BACKUP_FILE" "oss://${OSS_BUCKET}/quant-bot-backups/" || log "⚠️ OSS upload failed"
    fi

    exit 0
else
    log "❌ Backup failed"
    exit 1
fi
