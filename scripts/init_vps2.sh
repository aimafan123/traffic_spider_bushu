#!/bin/bash

# ==============================================================================
# 脚本功能: (高速版)
#   1. 从控制节点给源服务器(vultr6)下达指令。
#   2. 源服务器直接将文件rsync到所有目标服务器，速度更快。
#   3. 在所有服务器上执行 'docker load' 命令来加载镜像。
#
# 前提条件:
#   - 源服务器(vultr6)必须能免密SSH登录到所有其他目标服务器。
# ==============================================================================

# --- 请在这里配置您的服务器信息 ---

SERVERS=(
    "158.247.252.15"  # vultr6 (源服务器)
    "vultr7"   # vultr7
    "vultr8" # vultr8
    "vultr9"  # vultr9
    "vultr10"  # vultr10
)
SSH_USER="root"
FILENAME="single_spider_traffic_251013.tar"

# --- 脚本主体部分 ---

# 定义颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m'

SOURCE_SERVER=${SERVERS[0]}
DEST_SERVERS=("${SERVERS[@]:1}")
REMOTE_FILE_PATH="~/${FILENAME}"
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10"

# 预检查
echo -e "${YELLOW}--- 预检查：正在确认源文件 ${FILENAME} 是否存在于 ${SOURCE_SERVER} ...${NC}"
if ! ssh $SSH_OPTS ${SSH_USER}@${SOURCE_SERVER} "[ -f ${REMOTE_FILE_PATH} ]"; then
    echo -e "${RED}错误: 源文件 ${FILENAME} 在 ${SOURCE_SERVER} 的主目录中未找到！脚本终止。${NC}"
    exit 1
fi
echo -e "${GREEN}检查通过，源文件存在。${NC}"

# 第一部分：让源服务器直接分发文件到所有目标服务器 (使用 rsync)
echo -e "\n${GREEN}--- (1/2) 命令 ${SOURCE_SERVER} 直接将文件高速分发到其余服务器 ---${NC}"

for server in "${DEST_SERVERS[@]}"; do
    echo -e "\n${YELLOW}>>> 命令 ${SOURCE_SERVER} 将文件推送到 ${server} ...${NC}"
    
    # 构建在源服务器上执行的命令
    # rsync -avz: a=归档模式, v=详细输出, z=压缩传输
    # --progress: 显示进度条
    REMOTE_COMMAND="rsync -avz --progress ${REMOTE_FILE_PATH} ${SSH_USER}@${server}:${REMOTE_FILE_PATH}"
    
    # 从控制节点登录到源服务器，并执行上面的命令
    ssh $SSH_OPTS ${SSH_USER}@${SOURCE_SERVER} "${REMOTE_COMMAND}"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}成功将文件从 ${SOURCE_SERVER} 直接推送到 ${server}${NC}"
    else
        echo -e "${RED}文件推送失败！源: ${SOURCE_SERVER}, 目标: ${server}。${NC}"
        echo -e "${YELLOW}请检查 ${SOURCE_SERVER} 是否能免密SSH登录到 ${server}。${NC}"
        exit 1
    fi
done
echo -e "${GREEN}--- 文件分发完成 ---${NC}"

# 第二部分：在所有服务器上执行 docker load (这部分逻辑不变)
echo -e "\n${GREEN}--- (2/2) 开始在所有服务器上执行 docker load ---${NC}"
for server in "${SERVERS[@]}"; do
    echo -e "\n${YELLOW}>>> 正在 ${server} 上加载 Docker 镜像...${NC}"
    ssh $SSH_OPTS ${SSH_USER}@${server} "docker load -i ${REMOTE_FILE_PATH}"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}在 ${server} 上加载镜像成功！${NC}"
    else
        echo -e "${RED}在 ${server} 上加载镜像失败！${NC}"
    fi
done

echo -e "\n${GREEN}*** 所有任务已成功完成！ ***${NC}"