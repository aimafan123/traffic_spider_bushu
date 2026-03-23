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
  bash scripts/init_vps2.sh [配置文件路径]
  bash scripts/init_vps2.sh --config /path/to/vps_init.conf

默认配置文件:
  ${PROJECT_ROOT}/config/vps_init.conf
USAGE
    exit 0
fi

load_vps_init_config "$CONFIG_FILE"
build_servers_from_hostnames "$HOSTS_FILE"

if [ -z "${IMAGE_FILENAME:-}" ]; then
    echo "错误: 配置文件中必须提供 IMAGE_FILENAME。"
    exit 1
fi

# 定义颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

SOURCE_SERVER=${SERVERS[0]}
SOURCE_HOSTNAME=${HOSTNAMES[0]}
REMOTE_FILE_PATH="~/${IMAGE_FILENAME}"
SSH_OPTS_FAST="${SSH_OPTS_FAST:--o StrictHostKeyChecking=no -o ConnectTimeout=20}"
RSYNC_SSH_OPTS="${RSYNC_SSH_OPTS:--o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20}"

# 预检查
echo -e "${YELLOW}--- 预检查：正在确认源文件 ${IMAGE_FILENAME} 是否存在于 ${SOURCE_SERVER} (${SOURCE_HOSTNAME}) ...${NC}"
if ! ssh $SSH_OPTS_FAST ${SSH_USER}@${SOURCE_SERVER} "[ -f ${REMOTE_FILE_PATH} ]"; then
    echo -e "${RED}错误: 源文件 ${IMAGE_FILENAME} 在 ${SOURCE_SERVER} 的主目录中未找到！脚本终止。${NC}"
    exit 1
fi
echo -e "${GREEN}检查通过，源文件存在。${NC}"

# 第一部分：让源服务器直接分发文件到所有目标服务器 (使用 rsync)
echo -e "\n${GREEN}--- (1/2) 命令 ${SOURCE_SERVER} (${SOURCE_HOSTNAME}) 直接将文件高速分发到其余服务器 ---${NC}"

for ((i=1; i<${#SERVERS[@]}; i++)); do
    server_ip=${SERVERS[$i]}
    server_hostname=${HOSTNAMES[$i]}
    echo -e "\n${YELLOW}>>> 命令 ${SOURCE_SERVER} 将文件推送到 ${server_ip} (${server_hostname}) ...${NC}"

    REMOTE_COMMAND="rsync -avz --progress -e \"ssh ${RSYNC_SSH_OPTS}\" ${REMOTE_FILE_PATH} ${SSH_USER}@${server_ip}:${REMOTE_FILE_PATH}"

    ssh $SSH_OPTS_FAST ${SSH_USER}@${SOURCE_SERVER} "${REMOTE_COMMAND}"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}成功将文件从 ${SOURCE_SERVER} 推送到 ${server_ip} (${server_hostname})${NC}"
    else
        echo -e "${RED}文件推送失败！源: ${SOURCE_SERVER}, 目标: ${server_ip} (${server_hostname})。${NC}"
        echo -e "${YELLOW}请检查 ${SOURCE_SERVER} 是否能免密 SSH 登录到 ${server_ip}。${NC}"
        exit 1
    fi
done
echo -e "${GREEN}--- 文件分发完成 ---${NC}"

# 第二部分：在所有服务器上执行 docker load
echo -e "\n${GREEN}--- (2/2) 开始在所有服务器上执行 docker load ---${NC}"
for ((i=0; i<${#SERVERS[@]}; i++)); do
    server_ip=${SERVERS[$i]}
    server_hostname=${HOSTNAMES[$i]}
    echo -e "\n${YELLOW}>>> 正在 ${server_ip} (${server_hostname}) 上加载 Docker 镜像...${NC}"
    ssh $SSH_OPTS_FAST ${SSH_USER}@${server_ip} "docker load -i ${REMOTE_FILE_PATH}"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}在 ${server_ip} (${server_hostname}) 上加载镜像成功！${NC}"
    else
        echo -e "${RED}在 ${server_ip} (${server_hostname}) 上加载镜像失败！${NC}"
    fi
done

echo -e "\n${GREEN}使用配置文件: ${CONFIG_FILE}${NC}"
echo -e "${GREEN}读取 hosts 文件: ${HOSTS_FILE}${NC}"
echo -e "${GREEN}*** 所有任务已成功完成！ ***${NC}"
