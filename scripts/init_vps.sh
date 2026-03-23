#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# shellcheck disable=SC1091
source "${SCRIPT_DIR}/vps_init_common.sh"

CONFIG_FILE="$(resolve_config_file "${PROJECT_ROOT}" "$@")"
if [ "${CONFIG_FILE}" = "__SHOW_HELP__" ]; then
    cat <<USAGE
用法:
  bash scripts/init_vps.sh [配置文件路径]
  bash scripts/init_vps.sh --config /path/to/vps_init.conf

默认配置文件:
  ${PROJECT_ROOT}/config/vps_init.conf
USAGE
    exit 0
fi

load_vps_init_config "$CONFIG_FILE"
build_servers_from_hostnames "$HOSTS_FILE"
build_hosts_entries

# 定义颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# 分离源服务器和目标服务器
SOURCE_SERVER=${SERVERS[0]}
SSH_OPTS="${SSH_OPTS:--o StrictHostKeyChecking=no -o ConnectTimeout=10}"

# 第1部分: 清理本地的 known_hosts
echo -e "${GREEN}--- (1/5) 清理本地的 known_hosts 条目 ---${NC}"
for ((i=0; i<${#HOSTNAMES[@]}; i++)); do
    HOSTNAME=${HOSTNAMES[$i]}
    IP=${SERVERS[$i]}
    echo "正在移除 ${HOSTNAME} 和 ${IP} 的旧密钥..."
    ssh-keygen -f "${HOME}/.ssh/known_hosts" -R "${HOSTNAME}" > /dev/null 2>&1 || true
    ssh-keygen -f "${HOME}/.ssh/known_hosts" -R "${IP}" > /dev/null 2>&1 || true
done
echo -e "${GREEN}known_hosts 清理完成。${NC}"

# 第2部分: 从源服务器获取公钥
echo -e "\n${GREEN}--- (2/5) 从源服务器 ${SOURCE_SERVER} (${HOSTNAMES[0]}) 获取公钥 ---${NC}"
SOURCE_PUB_KEY=$(ssh $SSH_OPTS ${SSH_USER}@${SOURCE_SERVER} "cat ${PUBLIC_KEY_FILE}")

if [ -z "$SOURCE_PUB_KEY" ]; then
    echo -e "${RED}错误: 无法从 ${SOURCE_SERVER} 获取公钥。${NC}"
    echo -e "${YELLOW}请检查:"
    echo "  1. 控制节点到 ${SOURCE_SERVER} 的 SSH 连接是否正常。"
    echo "  2. 文件 ${PUBLIC_KEY_FILE} 是否在 ${SOURCE_SERVER} 上存在。"
    exit 1
fi
echo -e "${GREEN}成功获取公钥。${NC}"

# 第3部分: 将源服务器公钥分发到所有目标服务器
echo -e "\n${GREEN}--- (3/5) 开始将公钥分发到目标服务器 ---${NC}"
for ((i=1; i<${#SERVERS[@]}; i++)); do
    server=${SERVERS[$i]}
    hostname=${HOSTNAMES[$i]}
    echo -e "\n${YELLOW}>>> 正在处理服务器: $server (${hostname})${NC}"

    COMMAND="mkdir -p ~/.ssh && chmod 700 ~/.ssh && \
    touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && \
    if ! grep -q -F '${SOURCE_PUB_KEY}' ~/.ssh/authorized_keys; then \
        echo '${SOURCE_PUB_KEY}' >> ~/.ssh/authorized_keys && \
        echo 'Key_Added'; \
    else \
        echo 'Key_Exists'; \
    fi"

    RESULT=$(ssh $SSH_OPTS ${SSH_USER}@${server} "${COMMAND}")

    if [[ "$RESULT" == "Key_Added" ]]; then
        echo -e "${GREEN}成功将公钥添加到 $server (${hostname})${NC}"
    elif [[ "$RESULT" == "Key_Exists" ]]; then
        echo -e "${YELLOW}公钥在 $server (${hostname}) 上已存在，跳过。${NC}"
    else
        echo -e "${RED}无法将公钥添加到 $server。请检查控制节点到该服务器的 SSH 连接。${NC}"
    fi
done
echo -e "${GREEN}--- 所有公钥分发完成 ---${NC}"

# 第4部分: 在所有服务器上设置 hostname 并更新 /etc/hosts
echo -e "\n${GREEN}--- (4/5) 开始在所有服务器上设置 hostname 并更新 /etc/hosts ---${NC}"
MANAGED_BEGIN="# >>> managed by scripts/init_vps.sh >>>"
MANAGED_END="# <<< managed by scripts/init_vps.sh <<<"
HOSTS_ENTRIES_B64=$(printf '%s' "$HOSTS_ENTRIES" | base64 | tr -d '\n')

for ((i=0; i<${#SERVERS[@]}; i++)); do
    server=${SERVERS[$i]}
    hostname=${HOSTNAMES[$i]}
    echo -e "\n${YELLOW}>>> 正在更新服务器: $server (${hostname})${NC}"

    RESULT=$(ssh $SSH_OPTS ${SSH_USER}@${server} \
        "HOSTNAME_TARGET='${hostname}' HOSTS_ENTRIES_B64='${HOSTS_ENTRIES_B64}' MANAGED_BEGIN='${MANAGED_BEGIN}' MANAGED_END='${MANAGED_END}' bash -s" <<'REMOTE_SCRIPT'
set -euo pipefail

if [ "$(id -u)" -eq 0 ]; then
    SUDO=""
else
    SUDO="sudo"
fi

if command -v hostnamectl >/dev/null 2>&1; then
    $SUDO hostnamectl set-hostname "$HOSTNAME_TARGET"
else
    echo "$HOSTNAME_TARGET" | $SUDO tee /etc/hostname >/dev/null
    $SUDO hostname "$HOSTNAME_TARGET" || true
fi

HOSTS_ENTRIES=$(printf '%s' "$HOSTS_ENTRIES_B64" | base64 -d)
TMP_FILE=$(mktemp)

awk -v begin="$MANAGED_BEGIN" -v end="$MANAGED_END" '
$0 == begin { in_block = 1; next }
$0 == end { in_block = 0; next }
!in_block { print }
' /etc/hosts > "$TMP_FILE"

{
    cat "$TMP_FILE"
    echo "$MANAGED_BEGIN"
    printf '%s\n' "$HOSTS_ENTRIES"
    echo "$MANAGED_END"
} > "${TMP_FILE}.new"

$SUDO cp "${TMP_FILE}.new" /etc/hosts
$SUDO chmod 644 /etc/hosts
rm -f "$TMP_FILE" "${TMP_FILE}.new"

echo "Hostname_And_Hosts_Updated"
REMOTE_SCRIPT
)

    if [[ "$RESULT" == *"Hostname_And_Hosts_Updated"* ]]; then
        echo -e "${GREEN}${server} (${hostname}) 的 hostname 和 /etc/hosts 更新成功。${NC}"
    else
        echo -e "${RED}${server} (${hostname}) 的 hostname 或 /etc/hosts 更新失败。${NC}"
    fi
done

echo -e "${GREEN}--- hostname 与 /etc/hosts 更新完成 ---${NC}"

# 第5部分: 在所有服务器上安装 Docker
echo -e "\n${GREEN}--- (5/5) 开始在所有服务器上安装 Docker ---${NC}"
for ((i=0; i<${#SERVERS[@]}; i++)); do
    server=${SERVERS[$i]}
    hostname=${HOSTNAMES[$i]}
    echo -e "\n${YELLOW}>>> 正在处理服务器: $server (${hostname})${NC}"

    # 检查 Docker 是否已安装
    if ssh $SSH_OPTS ${SSH_USER}@${server} "command -v docker >/dev/null 2>&1"; then
        echo -e "${YELLOW}Docker 在 $server (${hostname}) 上已安装，跳过。${NC}"
    else
        echo "正在 ${server} (${hostname}) 上安装 Docker..."
        INSTALL_COMMAND="curl -fsSL https://get.docker.com -o get-docker.sh && if command -v sudo >/dev/null 2>&1; then sudo sh get-docker.sh; else sh get-docker.sh; fi"
        ssh -t $SSH_OPTS ${SSH_USER}@${server} "${INSTALL_COMMAND}"

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}Docker 在 $server (${hostname}) 上安装成功！${NC}"
        else
            echo -e "${RED}Docker 在 $server (${hostname}) 上安装失败。${NC}"
        fi
    fi
done

echo -e "${GREEN}--- Docker 安装任务完成 ---${NC}"

echo -e "\n${GREEN}使用配置文件: ${CONFIG_FILE}${NC}"
echo -e "${GREEN}读取 hosts 文件: ${HOSTS_FILE}${NC}"
echo -e "${GREEN}*** 所有任务已成功完成！ ***${NC}"
