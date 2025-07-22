# 1. 使用rsync将数据定期从vps上拉下来
# 2. 然后入库
# 3. 入库结束，将数据归档

import os
import subprocess
from datetime import datetime

import paramiko

try:
    from traffic_spider_bushu.feishu import send_feishu_message
except (ImportError, ModuleNotFoundError):

    def send_feishu_message(*args, **kwargs):
        pass


# from pypcaptools import PcapToDatabaseHandler
from traffic_spider_bushu.myutils import project_path
from traffic_spider_bushu.myutils.logger import logger
from traffic_spider_bushu.server_info import servers_info
from traffic_spider_bushu.server_monitoring import action as check_usage_action

LOCAL_DIR_root = "/netdisk/aimafan/traffic_datasets_new/http_top_100k"
# LOCAL_DIR_root = "/home/aimafan/Multi_2"
os_name = "debian12"
PROCESSED_PATHS_FILE = os.path.join(project_path, "data", "processed_path.txt")


def load_processed_paths():
    """加载已处理的 pcap_path 集合"""
    if not os.path.exists(PROCESSED_PATHS_FILE):
        return set()
    with open(PROCESSED_PATHS_FILE, "r") as file:
        return set(line.strip() for line in file)


def save_processed_path(pcap_path):
    """将处理过的 pcap_path 保存到文件"""
    with open(PROCESSED_PATHS_FILE, "a") as file:
        file.write(f"{pcap_path}\n")


def compare_time_in_filename(filename):
    """
    对比文件名中包含的时间与当前时间是否相差2个小时以上
    :param filename: 包含时间信息的文件名，时间格式类似20241211001423
    :return: 如果相差2个小时以上返回True，否则返回False
    """
    # 从文件名中提取时间字符串
    time_str = ""
    parts = filename.split("_")
    for part in parts:
        if len(part) == 14 and part.isdigit():
            time_str = part
            break

    # 将提取到的时间字符串转为datetime对象
    file_time = datetime.strptime(time_str, "%Y%m%d%H%M%S")
    # 获取当前时间
    current_time = datetime.now()
    # 计算时间差
    time_diff = current_time - file_time
    # 转为小时数（取绝对值，因为只关心差值大小）
    hours_diff = abs(time_diff.total_seconds() / 3600) - 8
    return hours_diff > 4


# 使用rsync同步数据
def sync_data(hostname, username, remote_dir, protocal):
    """
    使用rsync命令从远程服务器同步数据到本地
    :param hostname: 远程主机名
    :param username: 用户名
    :param remote_dir: 远程目录
    :param protocal: 协议名，用于本地目录命名
    :return: 本地同步后的根目录路径
    """
    local_path = os.path.join(LOCAL_DIR_root, protocal + f"_{hostname}")
    logger.info(f"{hostname} 开始同步数据")
    rsync_command = ["rsync", "-az", f"{username}@{hostname}:{remote_dir}", local_path]
    subprocess.run(rsync_command, check=True)
    logger.info(f"{hostname} 数据同步完成！")
    # subprocess.run(rsync_command, check=True)
    # logger.info(f"{hostname} 剩余数据同步完成！")

    return local_path


# def insert_into_db(pcap_path, protocol):
#     """
#     将pcap文件入库
#     :param pcap_path: pcap文件路径
#     :param protocol: 协议名
#     """
#     db_config = get_database_config()
#     db_config["table"] = protocol
#
#     # 加载已处理的路径
#     processed_paths = load_processed_paths()
#
#     for root, _, files in os.walk(pcap_path):
#         for file_name in files:
#             if file_name.endswith(".pcap"):
#                 if not compare_time_in_filename(file_name):
#                     continue
#
#                 full_pcap_path = os.path.join(root, file_name)
#
#                 # 检查路径是否已经处理过
#                 if full_pcap_path in processed_paths:
#                     logger.info(f"跳过已处理的路径: {full_pcap_path}")
#                     continue
#
#                 # 提取 domain 和 site 信息
#                 pcap_split = os.path.splitext(file_name)[0].split("_")
#                 domain = pcap_split[-1]
#                 site = pcap_split[-2]
#
#                 logger.info(f"开始处理 {full_pcap_path}")
#
#                 # 初始化处理器并处理数据
#                 handler = PcapToDatabaseHandler(
#                     db_config,
#                     full_pcap_path,
#                     protocol,
#                     domain,
#                     site + "_" + os_name,
#                 )
#                 handler.split_flow_to_database()
#
#                 # 处理完成后保存路径
#                 save_processed_path(full_pcap_path)


def kill_remote_pcap(hostname, port, username, private_key_path, storage_path):
    """
    远程执行脚本删除旧的pcap文件
    :param hostname: 远程主机名
    :param port: SSH端口
    :param username: 用户名
    :param private_key_path: 私钥路径
    :param storage_path: 远程存储路径
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, port=port, username=username, key_filename=private_key_path)
    stdin, stdout, stderr = ssh.exec_command(
        f"bash {os.path.join(storage_path, 'del_old_pcap.sh')}"
    )
    error = stderr.read().decode()
    if error:
        logger.error(f"删除旧的pcap文件发生错误：{error}")
    else:
        logger.info("已删除旧的pcap文件")
    ssh.close()


# 主流程
def main():
    """
    主流程函数，遍历所有服务器，拉取数据、删除远程旧数据、准备pcap路径列表
    """
    for server_info in servers_info:
        logger.info(f"开始处理{server_info['hostname']}的数据")
        # 1. 拉取远程数据
        root_path = sync_data(
            server_info["hostname"],
            server_info["username"],
            server_info["storage_path"],
            server_info["protocal"],
        )
        # 2. 删除远程旧的pcap文件
        if root_path:
            kill_remote_pcap(
                server_info["hostname"],
                server_info["port"],
                server_info["username"],
                server_info["private_key_path"],
                server_info["storage_path"],
            )
        send_feishu_message(
            f"{server_info['hostname']} 数据同步完成，已删除远程旧数据。"
        )
    check_usage_action()
    # 3. 组装本地pcap目录路径列表
    # root_path = os.path.join(root_path, "xray_traffic")
    # pcap_paths = []
    # docker_num = int(server_info["docker_num"])
    # for i in range(docker_num):
    #     pcap_paths.append(
    #         os.path.join(root_path, "spider_traffic_" + str(i), "data", "pcap")
    #     )
    # 4. 遍历每个pcap目录进行入库（已注释）
    # for pcap_path in pcap_paths:
    #    insert_into_db(pcap_path, protocol=server_info["protocal"])


if __name__ == "__main__":
    main()
