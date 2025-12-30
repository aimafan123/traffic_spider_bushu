#!/bin/bash

# ==============================================================================
# 脚本功能: (运行于独立的控制服务器上)
#   1. 在本控制机上，清理 vultr6-vultr10 的旧 SSH known_hosts 记录。
#   2. 从源服务器(vultr6)获取其公钥。
#   3. 将 vultr6 的公钥分发到所有目标服务器(vultr7-vultr10)的 authorized_keys 中。
#   4. 在所有服务器(vultr6-vultr10)上更新 /etc/hosts 文件，使其包含所有其他节点的信息。
#   5. 在所有服务器(vultr6-vultr10)上安装 Docker 引擎。
#
# 使用方法:
#   1. 确保这台控制服务器可以通过SSH密钥免密登录到下面列表中的所有服务器。
#   2. 在下面的 "配置您的服务器信息" 部分填入正确的服务器IP、SSH用户名等信息。
#   3. 将此脚本保存为 deploy_plus.sh 文件。
#   4. 添加执行权限: chmod +x deploy_plus.sh
#   5. 执行脚本: ./deploy_plus.sh
# ==============================================================================

# --- 请在这里配置您的服务器信息 ---

# 1. IP 地址数组
SERVERS=(
    "140.82.3.118"    # vultr6us
    "95.179.161.248"  # vultr24de
    "80.240.22.234"   # vultr25de
    "64.176.212.83"   # vultr20us
    "45.77.219.200"   # vultr21us
    "45.77.19.17"     # vultr22jp
    "108.61.126.194"  # vultr23jp
    "45.76.92.124"    # vultr10de
    "95.179.247.83"   # vultr11de
    "45.76.10.210"    # vultr7us
    "45.32.35.218"    # vultr8jp
    "45.32.46.59"     # vultr9jp
)

# 2. 与上面 IP 地址一一对应的主机名
HOSTNAMES=(
    "vultr6us"
    "vultr24de"
    "vultr25de"
    "vultr20us"
    "vultr21us"
    "vultr22jp"
    "vultr23jp"
    "vultr10de"
    "vultr11de"
    "vultr7us"
    "vultr8jp"
    "vultr9jp"
)

# 3. 用于SSH连接的用户名 (例如: root, ubuntu, centos)
SSH_USER="root"

# 4. 源服务器上的公钥文件路径
PUBLIC_KEY_FILE="~/.ssh/id_ed25519.pub"

# --- 脚本主体部分，通常无需修改 ---

# 定义颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# 检查配置
if [ ${#SERVERS[@]} -ne ${#HOSTNAMES[@]} ]; then
    echo -e "${RED}错误: 服务器IP列表和主机名列表的数量不匹配！${NC}"
    exit 1
fi

# 分离源服务器和目标服务器
SOURCE_SERVER=${SERVERS[0]}
DEST_SERVERS=("${SERVERS[@]:1}")
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10"

# 第一部分 (新增): 清理本地的 known_hosts
echo -e "${GREEN}--- (1/5) 清理本地的 known_hosts 条目 ---${NC}"
for ((i=0; i<${#HOSTNAMES[@]}; i++)); do
    HOSTNAME=${HOSTNAMES[$i]}
    IP=${SERVERS[$i]}
    echo "正在移除 ${HOSTNAME} 和 ${IP} 的旧密钥..."
    ssh-keygen -f "${HOME}/.ssh/known_hosts" -R "${HOSTNAME}" > /dev/null 2>&1
    ssh-keygen -f "${HOME}/.ssh/known_hosts" -R "${IP}" > /dev/null 2>&1
done
echo -e "${GREEN}known_hosts 清理完成。${NC}"


# 第二部分: 从源服务器获取公钥
echo -e "\n${GREEN}--- (2/5) 从源服务器 ${SOURCE_SERVER} (${HOSTNAMES[0]}) 获取公钥 ---${NC}"
SOURCE_PUB_KEY=$(ssh $SSH_OPTS ${SSH_USER}@${SOURCE_SERVER} "cat ${PUBLIC_KEY_FILE}")

if [ -z "$SOURCE_PUB_KEY" ]; then
    echo -e "${RED}错误: 无法从 ${SOURCE_SERVER} 获取公钥。${NC}"
    echo -e "${YELLOW}请检查: "
    echo "  1. 控制节点到 ${SOURCE_SERVER} 的SSH连接是否正常。"
    echo "  2. 文件 ${PUBLIC_KEY_FILE} 是否在 ${SOURCE_SERVER} 上存在。"
    exit 1
fi
echo -e "${GREEN}成功获取公钥。${NC}"

# 第三部分: 将源服务器公钥分发到所有目标服务器
echo -e "\n${GREEN}--- (3/5) 开始将公钥分发到目标服务器 ---${NC}"
for ((i=1; i<${#SERVERS[@]}; i++)); do
    server=${SERVERS[$i]}
    hostname=${HOSTNAMES[$i]}
    echo -e "\n${YELLOW}>>> 正在处理服务器: $server (${hostname})${NC}"
    
    COMMAND="mkdir -p ~/.ssh && chmod 700 ~/.ssh && \
    if ! grep -q -F '${SOURCE_PUB_KEY}' ~/.ssh/authorized_keys; then \
        echo '${SOURCE_PUB_KEY}' >> ~/.ssh/authorized_keys && \
        chmod 600 ~/.ssh/authorized_keys && \
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
        echo -e "${RED}无法将公钥添加到 $server。请检查控制节点到该服务器的SSH连接。${NC}"
    fi
done
echo -e "${GREEN}--- 所有公钥分发完成 ---${NC}"

# 第四部分 (增强): 在所有服务器上更新 /etc/hosts 文件
echo -e "\n${GREEN}--- (4/5) 开始在所有服务器上更新 /etc/hosts 文件 ---${NC}"
HOSTS_ENTRIES=""
for ((i=0; i<${#SERVERS[@]}; i++)); do
    HOSTS_ENTRIES+="${SERVERS[$i]} ${HOSTNAMES[$i]}\n"
done
HOSTS_ENTRIES=$(echo -e "$HOSTS_ENTRIES" | sed '/^$/d') # 移除空行

for ((i=0; i<${#SERVERS[@]}; i++)); do
    server=${SERVERS[$i]}
    hostname=${HOSTNAMES[$i]}
    echo -e "\n${YELLOW}>>> 正在更新服务器: $server (${hostname})${NC}"
    
    # 远程检查，避免重复添加
    if ssh $SSH_OPTS ${SSH_USER}@${server} "grep -q '${HOSTNAMES[1]}' /etc/hosts"; then
        echo -e "${YELLOW}/etc/hosts 文件在 $server 上似乎已配置，跳过写入。${NC}"
    else
        echo "正在通过SSH在 ${server} 上执行sudo命令来写入 /etc/hosts..."
        echo "$HOSTS_ENTRIES" | ssh -t $SSH_OPTS ${SSH_USER}@${server} "sudo tee -a /etc/hosts > /dev/null"

        if [ $? -eq 0 ]; then
            echo -e "${GREEN}/etc/hosts 文件更新成功！${NC}"
        else
            echo -e "${RED}/etc/hosts 文件更新失败。${NC}"
        fi
    fi
done
echo -e "${GREEN}--- /etc/hosts 文件更新完成 ---${NC}"


# 第五部分 (新增): 在所有服务器上安装 Docker
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
        # 使用官方脚本进行安装
        INSTALL_COMMAND="curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh"
        ssh -t $SSH_OPTS ${SSH_USER}@${server} "${INSTALL_COMMAND}"
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}Docker 在 $server (${hostname}) 上安装成功！${NC}"
        else
            echo -e "${RED}Docker 在 $server (${hostname}) 上安装失败。${NC}"
        fi
    fi
done
echo -e "${GREEN}--- Docker 安装任务完成 ---${NC}"

echo -e "\n${GREEN}*** 所有任务已成功完成！ ***${NC}"