#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_CONFIG="${PROJECT_ROOT}/config/vps_init.conf"
DEFAULT_CONFIG_INI="${PROJECT_ROOT}/config/config.ini"
DEFAULT_SERVER_INFO="${PROJECT_ROOT}/src/traffic_spider_bushu/server_info.py"
DEFAULT_DATASET_ROOT="/netdisk/aimafan/traffic_datasets_new/rewf"

# shellcheck disable=SC1091
source "${SCRIPT_DIR}/vps_init_common.sh"

CONFIG_FILE="${DEFAULT_CONFIG}"
CONFIG_INI_FILE="${DEFAULT_CONFIG_INI}"
SERVER_INFO_FILE="${DEFAULT_SERVER_INFO}"
DATASET_ROOT="${DEFAULT_DATASET_ROOT}"
SKIP_KEYGEN=0
SKIP_INIT=0
SKIP_DEPLOY=0
SKIP_LOCAL_DATASET_SETUP=0
PYTHON_BIN="${PYTHON_BIN:-python3}"

while [ "$#" -gt 0 ]; do
    case "$1" in
        -c|--config)
            if [ "$#" -lt 2 ]; then
                echo "错误: --config 需要提供文件路径"
                exit 1
            fi
            CONFIG_FILE="$2"
            shift 2
            ;;
        --server-info)
            if [ "$#" -lt 2 ]; then
                echo "错误: --server-info 需要提供文件路径"
                exit 1
            fi
            SERVER_INFO_FILE="$2"
            shift 2
            ;;
        --config-ini)
            if [ "$#" -lt 2 ]; then
                echo "错误: --config-ini 需要提供文件路径"
                exit 1
            fi
            CONFIG_INI_FILE="$2"
            shift 2
            ;;
        --dataset-root)
            if [ "$#" -lt 2 ]; then
                echo "错误: --dataset-root 需要提供目录路径"
                exit 1
            fi
            DATASET_ROOT="$2"
            shift 2
            ;;
        --python)
            if [ "$#" -lt 2 ]; then
                echo "错误: --python 需要提供解释器路径"
                exit 1
            fi
            PYTHON_BIN="$2"
            shift 2
            ;;
        --skip-local-dataset-setup)
            SKIP_LOCAL_DATASET_SETUP=1
            shift
            ;;
        --skip-keygen)
            SKIP_KEYGEN=1
            shift
            ;;
        --skip-init)
            SKIP_INIT=1
            shift
            ;;
        --skip-deploy)
            SKIP_DEPLOY=1
            shift
            ;;
        -h|--help)
            cat <<USAGE
用途:
  REWF 时间漂移测试流量采集一键流程。

用法:
  bash scripts/rewf_time_drift_collect.sh [options]

选项:
  -c, --config <path>         VPS 初始化配置文件，默认 config/vps_init.conf
  --config-ini <path>         本地 config.ini 路径，默认 config/config.ini
  --server-info <path>        要更新的 server_info.py，默认 src/traffic_spider_bushu/server_info.py
  --dataset-root <path>       本地采集目录，默认 /netdisk/aimafan/traffic_datasets_new/rewf
  --python <bin>              Python 解释器，默认环境变量 PYTHON_BIN 或 python3
  --skip-local-dataset-setup  跳过本地目录创建和 config.ini 更新
  --skip-keygen               跳过第一个 VPS 的 ssh-keygen
  --skip-init                 跳过 init_vps_all.sh
  --skip-deploy               跳过最终 bushu 部署
  -h, --help                  显示帮助

说明:
  1) 创建本地目录 /netdisk/aimafan/traffic_datasets_new/rewf，并更新 config.ini 的 source_path
  2) 读取 HOSTNAMES，并从 HOSTS_FILE 解析 IP
  3) 在第一个 VPS 上确保存在 ~/.ssh/id_ed25519
  4) 执行 scripts/init_vps_all.sh（包含本地 tar 上传 + 分发 + docker load）
  5) 自动更新 server_info.py 中每个节点的 vps_name / hostname
  6) 进入 src 目录执行: python -m traffic_spider_bushu.action bushu
USAGE
            exit 0
            ;;
        *)
            echo "错误: 不支持的参数: $1"
            exit 1
            ;;
    esac
done

if [ ! -f "$SERVER_INFO_FILE" ]; then
    echo "错误: server_info 文件不存在: $SERVER_INFO_FILE"
    exit 1
fi

if [ "$SKIP_LOCAL_DATASET_SETUP" -eq 0 ] && [ ! -f "$CONFIG_INI_FILE" ]; then
    echo "错误: config.ini 文件不存在: $CONFIG_INI_FILE"
    exit 1
fi

load_vps_init_config "$CONFIG_FILE"
build_servers_from_hostnames "$HOSTS_FILE"

SOURCE_SERVER="${SERVERS[0]}"
SOURCE_HOSTNAME="${HOSTNAMES[0]}"
SSH_OPTS="${SSH_OPTS:--o StrictHostKeyChecking=no -o ConnectTimeout=10}"

echo "配置文件: ${CONFIG_FILE}"
echo "config.ini: ${CONFIG_INI_FILE}"
echo "hosts 文件: ${HOSTS_FILE}"
echo "server_info: ${SERVER_INFO_FILE}"
echo "本地数据目录: ${DATASET_ROOT}"
echo "目标节点映射:"
for ((i=0; i<${#HOSTNAMES[@]}; i++)); do
    echo "  - ${HOSTNAMES[$i]} => ${SERVERS[$i]}"
done

echo
if [ "$SKIP_LOCAL_DATASET_SETUP" -eq 0 ]; then
    echo "[1/5] 创建本地采集目录并更新 config.ini"
    mkdir -p "$DATASET_ROOT"

    config_backup_file="${CONFIG_INI_FILE}.bak.$(date +%Y%m%d%H%M%S)"
    cp "$CONFIG_INI_FILE" "$config_backup_file"
    if grep -Eq '^[[:space:]]*source_path[[:space:]]*=' "$CONFIG_INI_FILE"; then
        sed -i -E "s|^[[:space:]]*source_path[[:space:]]*=.*$|source_path = ${DATASET_ROOT}|g" "$CONFIG_INI_FILE"
    else
        {
            echo
            echo "[path]"
            echo "source_path = ${DATASET_ROOT}"
        } >> "$CONFIG_INI_FILE"
    fi
    echo "已备份 config.ini: ${config_backup_file}"
    echo "已设置 source_path = ${DATASET_ROOT}"
else
    echo "[1/5] 已跳过本地目录与 config.ini 更新 (--skip-local-dataset-setup)"
fi

echo
if [ "$SKIP_KEYGEN" -eq 0 ]; then
    echo "[2/5] 在第一个 VPS 上检查/生成 ed25519 密钥: ${SOURCE_SERVER} (${SOURCE_HOSTNAME})"
    ssh $SSH_OPTS "${SSH_USER}@${SOURCE_SERVER}" 'set -e; if [ ! -f ~/.ssh/id_ed25519 ]; then mkdir -p ~/.ssh && chmod 700 ~/.ssh && ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519; fi; [ -f ~/.ssh/id_ed25519.pub ]'
else
    echo "[2/5] 已跳过第一个 VPS ssh-keygen (--skip-keygen)"
fi

echo
if [ "$SKIP_INIT" -eq 0 ]; then
    echo "[3/5] 执行 init_vps_all.sh"
    bash "${SCRIPT_DIR}/init_vps_all.sh" --config "$CONFIG_FILE"
else
    echo "[3/5] 已跳过 init_vps_all.sh (--skip-init)"
fi

hostnames_joined="$(printf '%s\034' "${HOSTNAMES[@]}")"
hostnames_joined="${hostnames_joined%$'\034'}"
servers_joined="$(printf '%s\034' "${SERVERS[@]}")"
servers_joined="${servers_joined%$'\034'}"

backup_file="${SERVER_INFO_FILE}.bak.$(date +%Y%m%d%H%M%S)"
cp "$SERVER_INFO_FILE" "$backup_file"

echo
echo "[4/5] 更新 server_info.py 的 vps_name / hostname"
awk -v hostnames_csv="$hostnames_joined" -v ips_csv="$servers_joined" '
BEGIN {
    hcount = split(hostnames_csv, hostnames, "\034")
    ipcount = split(ips_csv, ips, "\034")
    hidx = 1
    ipidx = 1
}
{
    if ($0 ~ /"vps_name":[[:space:]]*"/ && hidx <= hcount) {
        sub(/"vps_name":[[:space:]]*"[^"]*"/, "\"vps_name\": \"" hostnames[hidx] "\"")
        hidx++
    }
    if ($0 ~ /"hostname":[[:space:]]*"/ && ipidx <= ipcount) {
        sub(/"hostname":[[:space:]]*"[^"]*"/, "\"hostname\": \"" ips[ipidx] "\"")
        ipidx++
    }
    print
}
END {
    if (hidx - 1 < hcount) {
        printf("错误: server_info.py 中 vps_name 条目不足，需 %d 个，实际替换 %d 个\n", hcount, hidx - 1) > "/dev/stderr"
        exit 2
    }
    if (ipidx - 1 < ipcount) {
        printf("错误: server_info.py 中 hostname 条目不足，需 %d 个，实际替换 %d 个\n", ipcount, ipidx - 1) > "/dev/stderr"
        exit 3
    }
}
' "$SERVER_INFO_FILE" > "${SERVER_INFO_FILE}.tmp"
mv "${SERVER_INFO_FILE}.tmp" "$SERVER_INFO_FILE"

echo "已备份原文件: ${backup_file}"
echo "已更新目标文件: ${SERVER_INFO_FILE}"

echo
if [ "$SKIP_DEPLOY" -eq 0 ]; then
    if [ "$SERVER_INFO_FILE" != "$DEFAULT_SERVER_INFO" ]; then
        deploy_server_info_backup="${DEFAULT_SERVER_INFO}.bak.$(date +%Y%m%d%H%M%S)"
        cp "$DEFAULT_SERVER_INFO" "$deploy_server_info_backup"
        cp "$SERVER_INFO_FILE" "$DEFAULT_SERVER_INFO"
        echo "提示: action.py 默认读取 ${DEFAULT_SERVER_INFO}"
        echo "已备份默认文件: ${deploy_server_info_backup}"
        echo "已同步部署配置: ${SERVER_INFO_FILE} -> ${DEFAULT_SERVER_INFO}"
    fi

    if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
        echo "错误: 找不到 Python 解释器: ${PYTHON_BIN}"
        exit 1
    fi

    echo "[5/5] 执行部署: ${PYTHON_BIN} -m traffic_spider_bushu.action bushu"
    (
        cd "${PROJECT_ROOT}/src"
        "$PYTHON_BIN" -m traffic_spider_bushu.action bushu
    )
else
    echo "[5/5] 已跳过部署阶段 (--skip-deploy)"
fi

echo
echo "REWF 时间漂移流量采集流程执行完成。"
