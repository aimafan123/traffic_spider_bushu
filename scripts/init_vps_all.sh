#!/bin/bash

# 运行之前，需要在第一个vps上创建公私钥

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_CONFIG="${PROJECT_ROOT}/config/vps_init.conf"

# shellcheck disable=SC1091
source "${SCRIPT_DIR}/vps_init_common.sh"

CONFIG_FILE="${DEFAULT_CONFIG}"
RUN_IMAGE_STAGE=1
RUN_UPLOAD_STAGE=1

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
        --skip-image)
            RUN_IMAGE_STAGE=0
            shift
            ;;
        --skip-upload)
            RUN_UPLOAD_STAGE=0
            shift
            ;;
        -h|--help)
            cat <<USAGE
用法:
  bash scripts/init_vps_all.sh [配置文件路径]
  bash scripts/init_vps_all.sh --config /path/to/vps_init.conf
  bash scripts/init_vps_all.sh --skip-image
  bash scripts/init_vps_all.sh --skip-upload

说明:
  默认会执行 3 个阶段:
  1) init_vps.sh 基础初始化
  2) 上传本地 tar 镜像到第一个 VPS（源服务器）
  3) init_vps2.sh 分发镜像并 docker load
  使用 --skip-image 可只执行基础初始化阶段（跳过 2/3）。
  使用 --skip-upload 可跳过第 2 阶段（要求第一个 VPS 上已存在镜像文件）。
USAGE
            exit 0
            ;;
        *)
            CONFIG_FILE="$1"
            shift
            ;;
    esac
done

echo "[1/3] 执行基础初始化: init_vps.sh"
bash "${SCRIPT_DIR}/init_vps.sh" --config "$CONFIG_FILE"

if [ "$RUN_IMAGE_STAGE" -eq 1 ]; then
    if [ "$RUN_UPLOAD_STAGE" -eq 1 ]; then
        load_vps_init_config "$CONFIG_FILE"
        build_servers_from_hostnames "$HOSTS_FILE"

        SOURCE_SERVER="${SERVERS[0]}"
        SOURCE_HOSTNAME="${HOSTNAMES[0]}"
        SSH_OPTS_FAST="${SSH_OPTS_FAST:--o StrictHostKeyChecking=no -o ConnectTimeout=20}"
        LOCAL_IMAGE_PATH="${LOCAL_IMAGE_PATH:-${PROJECT_ROOT}/${IMAGE_FILENAME}}"
        REMOTE_IMAGE_PATH="~/${IMAGE_FILENAME}"

        if [ ! -f "$LOCAL_IMAGE_PATH" ]; then
            echo "错误: 本地镜像文件不存在: ${LOCAL_IMAGE_PATH}"
            echo "请确认镜像文件路径，或在配置中设置 LOCAL_IMAGE_PATH。"
            exit 1
        fi

        echo "[2/3] 上传本地镜像到源服务器: ${SOURCE_SERVER} (${SOURCE_HOSTNAME})"
        scp $SSH_OPTS_FAST "$LOCAL_IMAGE_PATH" "${SSH_USER}@${SOURCE_SERVER}:${REMOTE_IMAGE_PATH}"
        echo "[2/3] 上传完成: ${LOCAL_IMAGE_PATH} -> ${SOURCE_SERVER}:${REMOTE_IMAGE_PATH}"
    else
        echo "[2/3] 已跳过镜像上传阶段 (--skip-upload)"
    fi

    echo "[3/3] 执行镜像分发与加载: init_vps2.sh"
    bash "${SCRIPT_DIR}/init_vps2.sh" --config "$CONFIG_FILE"
else
    echo "[2/3] 已跳过镜像相关阶段 (--skip-image)"
fi

echo "全部阶段执行完成。"
