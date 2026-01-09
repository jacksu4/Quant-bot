#!/bin/bash
# 自动化监控脚本 - 检查容器状态、磁盘空间、日志更新等

set -e

LOG_FILE="/var/log/quant-bot-monitor.log"
DATA_DIR="/opt/quant-bot/data"
ALERT_EMAIL="${ALERT_EMAIL:-}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

send_alert() {
    local title=$1
    local message=$2

    log "ALERT: $title - $message"

    # 如果配置了邮件，发送告警
    if [ -n "$ALERT_EMAIL" ]; then
        echo "$message" | mail -s "⚠️ Quant-Bot Alert: $title" "$ALERT_EMAIL" 2>/dev/null || true
    fi
}

# 检查容器状态
check_containers() {
    log "=== Checking container status ==="

    containers=("quant-rsi-strategy" "quant-professional-strategy" "quant-dashboard")
    all_healthy=true

    for container in "${containers[@]}"; do
        if docker ps --filter "name=$container" --filter "status=running" | grep -q "$container"; then
            # 检查健康状态
            health_status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "unknown")
            log "✅ $container is running (health: $health_status)"

            if [ "$health_status" == "unhealthy" ]; then
                log "⚠️ Container $container is unhealthy"
                all_healthy=false
                send_alert "Container Unhealthy" "$container health check failed"
            fi
        else
            log "❌ $container is NOT running - attempting restart"
            cd /opt/quant-bot
            docker-compose -f docker-compose.prod.yml restart "$container" || docker-compose restart "$container" || true
            all_healthy=false
            send_alert "Container Down" "$container was restarted automatically"
        fi
    done

    return $([ "$all_healthy" = true ] && echo 0 || echo 1)
}

# 检查磁盘空间
check_disk_space() {
    log "=== Checking disk space ==="

    if [ -d "/opt/quant-bot" ]; then
        usage=$(df -h /opt/quant-bot | awk 'NR==2 {print $5}' | sed 's/%//')
    else
        usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
    fi

    log "Disk usage: ${usage}%"

    if [ "$usage" -gt 85 ]; then
        log "⚠️ WARNING: Disk usage at ${usage}%"
        send_alert "Disk Space Critical" "Disk usage: ${usage}%"
        return 1
    fi
    return 0
}

# 检查日志更新时间
check_log_freshness() {
    log "=== Checking log freshness ==="

    log_files=("$DATA_DIR/strategy_log.json" "$DATA_DIR/professional_strategy_log.json")

    for log_file in "${log_files[@]}"; do
        if [ -f "$log_file" ]; then
            if [ "$(uname)" == "Darwin" ]; then
                last_modified=$(stat -f %m "$log_file")
            else
                last_modified=$(stat -c %Y "$log_file")
            fi
            current_time=$(date +%s)
            diff=$((current_time - last_modified))

            log "$(basename $log_file) last updated: $((diff/60)) minutes ago"

            # 超过30分钟没更新则告警
            if [ $diff -gt 1800 ]; then
                log "⚠️ WARNING: $(basename $log_file) not updated for 30 minutes"
                send_alert "Strategy Inactive" "$(basename $log_file) has not been updated in 30 minutes"
                return 1
            fi
        else
            log "⚠️ WARNING: $(basename $log_file) not found"
            return 1
        fi
    done
    return 0
}

# 检查内存使用
check_memory() {
    log "=== Checking memory usage ==="

    if command -v free &> /dev/null; then
        mem_usage=$(free | awk '/Mem:/ {printf "%.0f", $3/$2 * 100}')
        log "Memory usage: ${mem_usage}%"

        if [ "$mem_usage" -gt 85 ]; then
            log "⚠️ WARNING: Memory usage at ${mem_usage}%"
            send_alert "Memory Critical" "Memory usage: ${mem_usage}%"
            return 1
        fi
    else
        log "⚠️ free command not available, skipping memory check"
    fi
    return 0
}

# 检查API连接（可选 - 需要Python环境）
check_api_connection() {
    log "=== Checking API connection ==="

    if docker ps | grep -q "quant-rsi-strategy"; then
        result=$(docker exec quant-rsi-strategy python -c "
from exchange import BinanceClient
try:
    client = BinanceClient()
    balance = client.get_usdt_balance()
    print('OK')
except Exception as e:
    print(f'ERROR: {e}')
" 2>&1 || echo "FAILED")

        if [[ "$result" == "OK" ]]; then
            log "✅ API connection healthy"
            return 0
        else
            log "❌ API connection failed: $result"
            send_alert "API Connection Failed" "$result"
            return 1
        fi
    else
        log "⚠️ Strategy container not running, skipping API check"
        return 1
    fi
}

# 主执行逻辑
main() {
    log "========== Monitor Check Started =========="

    failed_checks=0

    check_containers || ((failed_checks++))
    check_disk_space || ((failed_checks++))
    check_log_freshness || ((failed_checks++))
    check_memory || ((failed_checks++))
    check_api_connection || ((failed_checks++))

    if [ $failed_checks -eq 0 ]; then
        log "✅ All checks passed"
        exit 0
    else
        log "❌ $failed_checks check(s) failed"
        exit 1
    fi
}

# 运行主函数
main
