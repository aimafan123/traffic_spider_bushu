#!/bin/bash

resolve_config_file() {
    local project_root="$1"
    shift || true

    local config_file="${project_root}/config/vps_init.conf"

    if [ "$#" -eq 0 ]; then
        echo "$config_file"
        return 0
    fi

    case "$1" in
        -c|--config)
            if [ "$#" -lt 2 ]; then
                echo "错误: --config 需要提供文件路径" >&2
                return 1
            fi
            echo "$2"
            ;;
        -h|--help)
            echo "__SHOW_HELP__"
            ;;
        *)
            echo "$1"
            ;;
    esac
}

load_vps_init_config() {
    local config_file="$1"

    if [ ! -f "$config_file" ]; then
        echo "错误: 配置文件不存在: $config_file" >&2
        if [ -f "${config_file}.example" ]; then
            echo "提示: 可以先复制 ${config_file}.example 到 ${config_file} 再修改。" >&2
        fi
        return 1
    fi

    # 默认值，可在配置文件覆盖
    SSH_USER="root"
    PUBLIC_KEY_FILE="~/.ssh/id_ed25519.pub"
    IMAGE_FILENAME="single_spider_traffic_260319.tar"
    HOSTS_FILE="/etc/hosts"
    SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10"
    SSH_OPTS_FAST="-o StrictHostKeyChecking=no -o ConnectTimeout=20"
    RSYNC_SSH_OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=20"

    # shellcheck disable=SC1090
    source "$config_file"

    if ! declare -p HOSTNAMES >/dev/null 2>&1; then
        echo "错误: 配置文件中必须定义 HOSTNAMES 数组。" >&2
        return 1
    fi

    if [ "${#HOSTNAMES[@]}" -eq 0 ]; then
        echo "错误: HOSTNAMES 不能为空。" >&2
        return 1
    fi

    if [ ! -f "$HOSTS_FILE" ]; then
        echo "错误: HOSTS_FILE 不存在: $HOSTS_FILE" >&2
        return 1
    fi
}

resolve_ip_from_hosts() {
    local hostname="$1"
    local hosts_file="$2"

    awk -v target="$hostname" '
        /^[[:space:]]*#/ { next }
        NF < 2 { next }
        {
            ip = $1
            for (i = 2; i <= NF; i++) {
                if ($i == target) {
                    # 优先使用 IPv4，避免拿到 ::1 等 IPv6 本地回环地址。
                    if (ip ~ /^[0-9]+\./) {
                        print ip
                        exit
                    }
                    if (fallback == "") {
                        fallback = ip
                    }
                }
            }
        }
        END {
            if (fallback != "") {
                print fallback
            }
        }
    ' "$hosts_file"
}

build_servers_from_hostnames() {
    local hosts_file="$1"
    SERVERS=()

    local hostname ip
    for hostname in "${HOSTNAMES[@]}"; do
        ip="$(resolve_ip_from_hosts "$hostname" "$hosts_file")"
        if [ -z "$ip" ]; then
            echo "错误: 在 ${hosts_file} 中找不到 hostname: ${hostname}" >&2
            return 1
        fi
        SERVERS+=("$ip")
    done
}

build_hosts_entries() {
    HOSTS_ENTRIES=""
    local i
    for ((i=0; i<${#SERVERS[@]}; i++)); do
        HOSTS_ENTRIES+="${SERVERS[$i]} ${HOSTNAMES[$i]}"$'\n'
    done
    HOSTS_ENTRIES="${HOSTS_ENTRIES%$'\n'}"
}
