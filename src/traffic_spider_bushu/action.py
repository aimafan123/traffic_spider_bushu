import os
import time

import paramiko
from scp import SCPClient

from traffic_spider_bushu.myutils import project_path
from traffic_spider_bushu.myutils.config import config
from traffic_spider_bushu.myutils.logger import logger
from traffic_spider_bushu.server_info import servers_info

index = 0


# 异步执行并监控命令输出
def exec_command(client, command):
    # logger.info(f"执行{command}")
    stdin, stdout, stderr = client.exec_command(command)

    while not stdout.channel.exit_status_ready():
        # 逐行读取输出
        line = stdout.readline()
        if line:
            print(f"{line.strip()}")
        time.sleep(1)  # 异步等待，避免阻塞

    # 读取剩余的输出
    err = stderr.read().decode()
    if err:
        print(f"{err}")


def get_exclude_content():
    exclude_str = """egister
ignin
ogin
Help
help
policies
Policies
policy
Policy
"""
    return exclude_str


def get_running_content():
    running_str = """{"currentIndex": 0}"""
    return running_str


def run_command(ssh, command):
    logger.info(command)
    stdin, stdout, stderr = ssh.exec_command(command)
    logger.info(stdout.read().decode())
    logger.info(stderr.read().decode())


# 异步上传文件
def async_upload_file(sftp, local_file, remote_file):
    if os.path.exists(local_file):
        sftp.put(local_file, remote_file)
        print(f"File '{local_file}' successfully uploaded to '{remote_file}'")
    else:
        print(f"Warning: Local file '{local_file}' does not exist.")


def get_config_content(server):
    config_str = f"""[information]
name={server["hostname"]}
protocal={server["protocal"]}
site={server["site"]}

[spider]
depth=-1
time_per_website={server["time_per_website"]}
# 爬虫连续爬取URL的延时。单位秒
download_delay = 60
image_name = aimafan/spider_traffic:latest"""

    return config_str


def split_file(input_file, num):
    # 读取文件内容
    with open(input_file, "r") as file:
        lines = file.readlines()

    # 计算每份的大小
    num_lines = len(lines)
    chunk_size = (num_lines + num - 1) // num  # 确保平均分配，最后一份可能多几行

    # 分割文件内容并组装字符串
    parts = []
    for i in range(num):
        start_index = i * chunk_size
        end_index = start_index + chunk_size
        chunk_lines = lines[start_index:end_index]
        parts.append("".join(chunk_lines).strip())  # 去掉尾部的换行符

    return parts


# 在服务器上异步执行一系列命令
def handle_server(server):
    hostname = server["hostname"]
    username = server["username"]
    port = server["port"]
    private_key_path = server["private_key_path"]
    local_image_path = os.path.join(
        project_path, "data", "spider_traffic.tar"
    )  # 本地Docker镜像文件路径
    remote_image_path = "~/spider_traffic.tar"  # 目标服务器上保存镜像的路径

    del_old_pcap_path = os.path.join(project_path, "data", "del_old_pcap.sh")
    docker_num = int(server["docker_num"])
    storage_path = server["storage_path"]
    image_name = config["spider"]["image_name"]
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # try:
    # 连接服务器,并初始化服务器
    # 使用私钥连接
    ssh.connect(hostname, port=port, username=username, key_filename=private_key_path)

    logger.info(f"{hostname}连接成功")
    exec_command(ssh, f"rm -rf {storage_path}")  # 注意，这里删除掉了目录，要注意
    exec_command(ssh, f"mkdir {storage_path}")
    # 使用SCP传送Docker镜像文件
    with SCPClient(ssh.get_transport()) as scp:
        # scp.put(local_image_path, remote_image_path)
        scp.put(del_old_pcap_path, os.path.join(storage_path, "del_old_pcap.sh"))

    # 执行命令
    server_commands = [
        "ethtool -K docker0 tso off gso off gro off",
    ]
    main_commands = []
    base_name = "spider_traffic"
    url_parts = split_file(os.path.join(project_path, "urls.txt"), docker_num)
    for i in range(docker_num):
        container_name = "_".join([base_name, str(i)])
        server_commands.append(f"docker stop {container_name}")
        server_commands.append(f"docker rm {container_name}")
    server_commands.append("docker rmi 192.168.194.63:5000/spider_traffic:v3")
    server_commands.append(f"docker load -i {remote_image_path}")
    for i in range(docker_num):
        container_name = "_".join([base_name, str(i)])

        config_dir = os.path.join(storage_path, container_name, "config")
        server_commands.append(f"mkdir -p {config_dir}")

        config_content = get_config_content(server)
        server_commands.append(
            f"echo '{config_content}' > {os.path.join(config_dir, 'config.ini')}"
        )
        server_commands.append(
            f"echo '{url_parts[i]}' > {os.path.join(config_dir, 'current_docker_url_list.txt')}"
        )
        server_commands.append(
            f"echo '{get_exclude_content()}' > {os.path.join(config_dir, 'exclude_keywords')}"
        )

        server_commands.append(
            f"docker run -v {os.path.join(storage_path, container_name, 'data')}:/app/data "
            f"-v {config_dir}:/app/config "
            f"-v {os.path.join(storage_path, container_name, 'logs')}:/app/logs "
            f"--privileged -itd --name {container_name} {image_name} /bin/bash"
        )
        server_commands.append(
            f"docker exec  {container_name} ethtool -K eth0 tso off gso off gro off lro off"
        )
        main_commands.append(
            f"nohup docker exec {container_name} bash action.sh > {os.path.join(storage_path, container_name+'.log')} 2>&1 &"
        )

    for sever_command in server_commands:
        exec_command(ssh, sever_command)

    for main_command in main_commands:
        exec_command(ssh, main_command)


# 主函数：并行处理所有服务器
def main():
    # 启动线程
    for server in servers_info:
        logger.info(f"开始处理{server["hostname"]}")
        handle_server(server)


if __name__ == "__main__":
    # 运行主程序
    main()
