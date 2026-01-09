#!/bin/bash
# 快速健康检查脚本 - 用于快速验证系统状态

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_status=0

echo "========================================"
echo "   Quant-Bot Health Check"
echo "========================================"
echo ""

# 检查Docker是否运行
echo -n "Docker daemon: "
if docker info >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Running${NC}"
else
    echo -e "${RED}✗ Not running${NC}"
    check_status=1
fi

# 检查容器状态
echo ""
echo "Container Status:"
containers=("quant-rsi-strategy" "quant-professional-strategy" "quant-dashboard")

for container in "${containers[@]}"; do
    echo -n "  $container: "
    if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
        # 检查健康状态
        health=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "no-healthcheck")
        if [ "$health" == "healthy" ] || [ "$health" == "no-healthcheck" ]; then
            echo -e "${GREEN}✓ Running${NC} (health: $health)"
        else
            echo -e "${YELLOW}⚠ Running${NC} (health: $health)"
            check_status=1
        fi
    else
        echo -e "${RED}✗ Not running${NC}"
        check_status=1
    fi
done

# 检查端口
echo ""
echo "Port Availability:"
ports=("8501" "8502")
for port in "${ports[@]}"; do
    echo -n "  Port $port: "
    if command -v netstat >/dev/null 2>&1; then
        if netstat -tuln 2>/dev/null | grep -q ":$port "; then
            echo -e "${GREEN}✓ Listening${NC}"
        else
            echo -e "${RED}✗ Not listening${NC}"
            check_status=1
        fi
    elif command -v ss >/dev/null 2>&1; then
        if ss -tuln 2>/dev/null | grep -q ":$port "; then
            echo -e "${GREEN}✓ Listening${NC}"
        else
            echo -e "${RED}✗ Not listening${NC}"
            check_status=1
        fi
    else
        echo -e "${YELLOW}? Unable to check${NC}"
    fi
done

# 检查数据目录
echo ""
echo "Data Directory:"
data_dir="/opt/quant-bot/data"
if [ -d "$data_dir" ]; then
    echo -n "  $data_dir: "
    echo -e "${GREEN}✓ Exists${NC}"

    # 检查关键文件
    if [ -f "$data_dir/strategy_log.json" ]; then
        echo -n "    strategy_log.json: "
        # 检查文件修改时间
        if [ "$(uname)" == "Darwin" ]; then
            last_mod=$(( $(date +%s) - $(stat -f %m "$data_dir/strategy_log.json") ))
        else
            last_mod=$(( $(date +%s) - $(stat -c %Y "$data_dir/strategy_log.json") ))
        fi

        if [ $last_mod -lt 1800 ]; then
            echo -e "${GREEN}✓ Updated ${last_mod}s ago${NC}"
        else
            echo -e "${YELLOW}⚠ Updated ${last_mod}s ago (>30min)${NC}"
            check_status=1
        fi
    else
        echo -e "    strategy_log.json: ${YELLOW}⚠ Not found${NC}"
    fi
else
    echo -e "  $data_dir: ${RED}✗ Not found${NC}"
    check_status=1
fi

# 检查磁盘空间
echo ""
echo "Disk Space:"
if [ -d "/opt/quant-bot" ]; then
    usage=$(df -h /opt/quant-bot | awk 'NR==2 {print $5}' | sed 's/%//')
    used=$(df -h /opt/quant-bot | awk 'NR==2 {print $3}')
    avail=$(df -h /opt/quant-bot | awk 'NR==2 {print $4}')
else
    usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
    used=$(df -h / | awk 'NR==2 {print $3}')
    avail=$(df -h / | awk 'NR==2 {print $4}')
fi

echo -n "  Usage: ${usage}% (Used: $used, Available: $avail) "
if [ "$usage" -lt 80 ]; then
    echo -e "${GREEN}✓ OK${NC}"
elif [ "$usage" -lt 90 ]; then
    echo -e "${YELLOW}⚠ Warning${NC}"
    check_status=1
else
    echo -e "${RED}✗ Critical${NC}"
    check_status=1
fi

# 检查内存
echo ""
echo "Memory:"
if command -v free >/dev/null 2>&1; then
    mem_usage=$(free | awk '/Mem:/ {printf "%.0f", $3/$2 * 100}')
    mem_used=$(free -h | awk '/Mem:/ {print $3}')
    mem_total=$(free -h | awk '/Mem:/ {print $2}')

    echo -n "  Usage: ${mem_usage}% (Used: $mem_used / Total: $mem_total) "
    if [ "$mem_usage" -lt 80 ]; then
        echo -e "${GREEN}✓ OK${NC}"
    elif [ "$mem_usage" -lt 90 ]; then
        echo -e "${YELLOW}⚠ Warning${NC}"
        check_status=1
    else
        echo -e "${RED}✗ Critical${NC}"
        check_status=1
    fi
else
    echo "  free command not available"
fi

# 总结
echo ""
echo "========================================"
if [ $check_status -eq 0 ]; then
    echo -e "Overall Status: ${GREEN}✓ HEALTHY${NC}"
    exit 0
else
    echo -e "Overall Status: ${YELLOW}⚠ ISSUES DETECTED${NC}"
    exit 1
fi
