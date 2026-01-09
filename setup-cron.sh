#!/bin/bash
# 自动化设置定时任务

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Setting up cron jobs for Quant-Bot..."

# 确保脚本有执行权限
chmod +x "$SCRIPT_DIR/monitor.sh"
chmod +x "$SCRIPT_DIR/backup-data.sh"

# 备份现有的crontab
crontab -l > /tmp/crontab_backup_$(date +%Y%m%d_%H%M%S) 2>/dev/null || true

# 移除旧的Quant-Bot相关任务
crontab -l 2>/dev/null | grep -v "quant-bot" | grep -v "Quant-Bot" > /tmp/crontab_new || true

# 添加新任务
cat >> /tmp/crontab_new << EOF

# ===== Quant-Bot Automated Tasks =====
# 监控检查（每10分钟）
*/10 * * * * $SCRIPT_DIR/monitor.sh >> /var/log/quant-bot-monitor.log 2>&1

# 数据备份（每天凌晨2点）
0 2 * * * $SCRIPT_DIR/backup-data.sh >> /var/log/quant-bot-backup.log 2>&1

# Docker清理（每周日凌晨3点）
0 3 * * 0 docker system prune -af --filter 'until=168h' >> /var/log/quant-bot-cleanup.log 2>&1

# 日志轮转（每天凌晨4点，保留最近7天）
0 4 * * * find $SCRIPT_DIR/logs -name "*.log" -mtime +7 -delete 2>/dev/null || true
EOF

# 安装新的crontab
crontab /tmp/crontab_new

log "✅ Cron jobs configured successfully:"
log ""
crontab -l | grep -A 10 "Quant-Bot"

log ""
log "Cron jobs summary:"
log "  - Health monitoring: Every 10 minutes"
log "  - Data backup: Daily at 2:00 AM"
log "  - Docker cleanup: Weekly on Sunday at 3:00 AM"
log "  - Log rotation: Daily at 4:00 AM"
log ""
log "Logs location:"
log "  - Monitor: /var/log/quant-bot-monitor.log"
log "  - Backup: /var/log/quant-bot-backup.log"
log "  - Cleanup: /var/log/quant-bot-cleanup.log"
