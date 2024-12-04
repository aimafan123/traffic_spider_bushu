import re

import paramiko
from wechat_bot_aimafan import wechat_send

from traffic_spider_bushu.myutils.logger import logger
from traffic_spider_bushu.server_info import servers_info


def parse_size(size_str):
    """
    将大小字符串转换为 MB。
    支持单位：K, M, G, T (大小写均可)
    """
    size_str = size_str.strip().upper()
    units = {"K": 1 / 1024, "M": 1, "G": 1024, "T": 1024 * 1024}
    for unit, multiplier in units.items():
        if size_str.endswith(unit):
            return float(size_str[:-1]) * multiplier
    raise ValueError(f"Unknown size format: {size_str}")


def sum_sizes(size_list):
    """
    计算列表中的总大小，返回以 GB 为单位的结果。
    """
    total_mb = sum(parse_size(size) for size in size_list)
    total_gb = total_mb / 1024  # 转换为 GB
    return total_gb


def check_usage(ssh, disk, directory):
    # 返回的数据
    result = {
        "websites_num": 0,
        "free_space": "",
        "docker_num_list": [],
        "docker_usage_list": [],
    }

    # 检查磁盘占用情况
    disk_command = f"df -h | grep '{disk}'"
    stdin, stdout, stderr = ssh.exec_command(disk_command)
    disk_usage = stdout.read().decode().strip() or stderr.read().decode().strip()

    # 解析磁盘信息
    if disk_usage:
        disk_info = re.split(r"\s+", disk_usage)
        result["free_space"] = disk_info[3]  # 可用空间列

    # 使用远程 find 命令查找匹配的路径
    find_command = f"find {directory} -type d -path '*/spider_traffic*/data/pcap'"
    stdin, stdout, stderr = ssh.exec_command(find_command)
    matching_dirs = stdout.read().decode().strip().split("\n")

    # 检查结果
    if matching_dirs == [""]:
        matching_dirs = []

    # 统计信息
    result["websites_num"] = len(matching_dirs)  # 网站数量
    for path in matching_dirs:
        # 获取 Docker 网站子目录数量
        count_command = f"find {path} -mindepth 1 -maxdepth 1 -type d | wc -l"
        stdin, stdout, stderr = ssh.exec_command(count_command)
        docker_num = int(stdout.read().decode().strip() or 0)
        result["docker_num_list"].append(docker_num)

        # 获取目录占用空间
        du_command = f"du -sh {path} | awk '{{print $1}}'"
        stdin, stdout, stderr = ssh.exec_command(du_command)
        docker_usage = stdout.read().decode().strip()
        result["docker_usage_list"].append(docker_usage)

    return result


if __name__ == "__main__":
    # 监控每台服务器
    messages = []
    for server in servers_info:
        hostname = server["hostname"]
        username = server["username"]
        port = server["port"]
        private_key_path = server["private_key_path"]
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(
                hostname, port=port, username=username, key_filename=private_key_path
            )
        except Exception as e:
            message = f"{hostname} can not connect: {e}"
            logger.info(message)
            messages.append(message)
            continue

        result = check_usage(ssh, server["disk"], server["storage_path"])
        message = (
            f"服务器：{hostname}\n\n"
            f"每个 Docker 采集网站数量：{result['docker_num_list']}\n"
            f"每个网站占用空间：{result['docker_usage_list']}\n"
            f"采集总占用空间：{sum_sizes(result['docker_usage_list']):.2f} GB\n"
            f"剩余空间：{result['free_space']}"
        )
        logger.info(message)
        messages.append(message)
    wechat_send("\n\n========\n\n".join(messages), "server_status")
