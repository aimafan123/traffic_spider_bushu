import argparse
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


# 获取排除关键词内容
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
account
"""
    return exclude_str


# 获取running内容
def get_running_content():
    running_str = """{"currentIndex": 0}"""
    return running_str


# 执行命令并打印日志
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


# 生成服务器专属配置文件内容
def get_config_content(server):
    config_str = f"""[information]
name={server["hostname"]}
protocal={server["protocal"]}
site={server["site"]}
ip_addr={server["ip_addr"]}

#这里代理xray使用http代理，tor使用socks5代理
[proxy]
host=127.0.0.1
port={server["proxy_port"]}

[spider]
depth=-1
time_per_website={server["time_per_website"]}
# 爬虫连续爬取URL的延时。单位秒
download_delay = 60
mode = {server["spider_mode"]}
scroll = {server["scroll"]}
scroll_num = {server["scroll_num"]}
multisite_num = {server["multisite_num"]}
webnum={server["webnum"]}"""
    # multisite_num={server["multisite_num"]}"""

    return config_str


# 按数量分割文件内容
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
# 部署
def handle_server(server):
    """
    处理单个服务器的部署任务，包括初始化环境、传输文件、配置Docker容器等。

    Args:
        server (dict): 包含服务器信息的字典，如主机名、用户名、端口、私钥路径等。
    """
    # 爬虫类型只有直连，tor和xray
    spider_modes = ["direct", "xray", "tor"]
    if server["spider_mode"] not in spider_modes:
        raise ValueError("spider_mode 必须是 %r 之一." % spider_modes)

    # 从服务器信息字典中提取必要的参数
    hostname = server["hostname"]
    username = server["username"]
    port = server["port"]
    private_key_path = server["private_key_path"]

    # 远程服务器上保存Docker镜像的路径
    remote_image_path = config["spider"]["remote_image_path"]

    # 根据爬虫类型选择配置文件路径
    if server["spider_mode"] == "xray" or server["spider_mode"] == "direct":
        local_config_path = os.path.join(
            project_path, "data", "xray_config", server["xray_name"]
        )
        remote_config_path = "~/xray.json"
    elif server["spider_mode"] == "tor":
        local_config_path = os.path.join(
            project_path, "data", "torrc_s", server["torrc_name"]
        )
        remote_config_path = "~/torrc"

    # 本地删除旧pcap文件的脚本路径
    del_old_pcap_path = os.path.join(project_path, "data", "del_old_pcap.sh")

    # 从服务器信息中获取Docker容器的数量
    docker_num = int(server["docker_num"])

    # 从服务器信息中获取存储路径
    storage_path = server["storage_path"]

    # 从配置文件中获取Docker镜像的名称
    image_name = config["spider"]["image_name"]

    # 初始化SSH客户端
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # 使用私钥连接服务器
    ssh.connect(hostname, port=port, username=username, key_filename=private_key_path)

    # 记录连接成功的日志
    logger.info(f"{hostname}连接成功")

    # 删除并重新创建存储路径
    exec_command(ssh, f"rm -rf {storage_path}")  # 注意：这里会删除目录，需谨慎
    exec_command(ssh, f"mkdir {storage_path}")

    transport = ssh.get_transport()
    if transport is None:
        raise RuntimeError("SSH transport not established. Did you call ssh.connect()?")

    with SCPClient(transport) as scp:
        scp.put(local_config_path, remote_config_path)
        scp.put(del_old_pcap_path, f"{storage_path}/del_old_pcap.sh")

    # 初始化服务器命令列表
    server_commands = [
        "ethtool -K docker0 tso off gso off gro off",  # 关闭Docker网络接口的某些特性
    ]

    # 初始化主命令列表
    main_commands = []

    # 基础容器名称
    base_name = "spider_traffic"

    # 统计所有主机的docker总数
    total_docker_num = sum(int(s["docker_num"]) for s in servers_info)
    # 计算当前server在所有docker中的起始索引
    start_index = 0
    for s in servers_info:
        if s["hostname"] == server["hostname"]:
            break
        start_index += int(s["docker_num"])

    # 分割URL文件
    url_parts = split_file(os.path.join(project_path, "urls.txt"), total_docker_num)

    # 为每个Docker容器生成配置和启动命令
    for i in range(docker_num):
        container_name = "_".join([base_name, str(i)])

        # 停止并删除已有的Docker容器
        server_commands.append(f"docker stop {container_name}")
        server_commands.append(f"docker rm {container_name}")

    # 加载新的Docker镜像
    # server_commands.append(f"docker load -i {remote_image_path}")

    # 为每个Docker容器创建配置目录并写入配置文件
    for i in range(docker_num):
        container_name = "_".join([base_name, str(i)])
        config_dir = os.path.join(storage_path, container_name, "config")
        exec_command(ssh, f"mkdir -p {config_dir}")

        # 生成并写入配置文件
        config_content = get_config_content(server)
        server_commands.append(
            f"echo '{config_content}' > {os.path.join(config_dir, 'config.ini')}"
        )

        # 本地生成临时url文件
        local_url_file = f"/tmp/{container_name}_current_docker_url_list.txt"
        with open(local_url_file, "w") as f:
            f.write(url_parts[start_index + i])

        # 上传到服务器
        with SCPClient(transport) as scp:
            scp.put(
                local_url_file, os.path.join(config_dir, "current_docker_url_list.txt")
            )

        # 写入排除关键词文件
        server_commands.append(
            f"echo '{get_exclude_content()}' > {os.path.join(config_dir, 'exclude_keywords')}"
        )

        # 启动Docker容器
        server_commands.append(
            f"docker run -v {os.path.join(storage_path, container_name, 'data')}:/app/data "
            f"-v {config_dir}:/app/config "
            f"-v {os.path.join(storage_path, container_name, 'logs')}:/app/logs "
            f"--privileged -itd --name {container_name} {image_name} /bin/bash"
        )

        # 关闭容器内网络接口的某些特性
        server_commands.append(
            f"docker exec  {container_name} ethtool -K eth0 tso off gso off gro off lro off"
        )

        # 将Xray配置文件复制到容器内
        server_commands.append(
            f"docker cp {remote_config_path} {container_name}:/app/config"
        )

        # 在容器内执行主命令，并将输出重定向到日志文件
        main_commands.append(
            f"nohup docker exec {container_name} bash action.sh > {os.path.join(storage_path, container_name + '.log')} 2>&1 &"
        )

    # 执行所有服务器命令
    for sever_command in server_commands:
        exec_command(ssh, sever_command)

    # 执行主命令
    for main_command in main_commands:
        exec_command(ssh, main_command)


# 启动服务器中的docker
def start_docker(server):
    # 开始服务器中docker运行
    base_name = "spider_traffic"
    hostname = server["hostname"]
    username = server["username"]
    port = server["port"]
    private_key_path = server["private_key_path"]
    storage_path = server["storage_path"]

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # try:
    # 连接服务器,并初始化服务器
    # 使用私钥连接
    ssh.connect(hostname, port=port, username=username, key_filename=private_key_path)

    logger.info(f"{hostname}连接成功")
    docker_num = int(server["docker_num"])
    server_commands = []

    for i in range(docker_num):
        container_name = "_".join([base_name, str(i)])
        server_commands.append(f"docker start {container_name}")
        server_commands.append(
            f"nohup docker exec {container_name} bash action.sh > {os.path.join(storage_path, container_name + '.log')} 2>&1 &"
        )
    for sever_command in server_commands:
        exec_command(ssh, sever_command)


# 暂停服务器中的docker
def stop_docker(server):
    # 暂停服务器中docker运行
    base_name = "spider_traffic"
    hostname = server["hostname"]
    username = server["username"]
    port = server["port"]
    private_key_path = server["private_key_path"]

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # try:
    # 连接服务器,并初始化服务器
    # 使用私钥连接
    ssh.connect(hostname, port=port, username=username, key_filename=private_key_path)

    logger.info(f"{hostname}连接成功")
    docker_num = int(server["docker_num"])
    server_commands = []

    for i in range(docker_num):
        container_name = "_".join([base_name, str(i)])
        server_commands.append(f"docker stop {container_name}")
    for sever_command in server_commands:
        exec_command(ssh, sever_command)


# 删除服务器中的docker及数据
def del_docker(server):
    # 暂停服务器中docker运行
    base_name = "spider_traffic"
    hostname = server["hostname"]
    username = server["username"]
    port = server["port"]
    private_key_path = server["private_key_path"]

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # try:
    # 连接服务器,并初始化服务器
    # 使用私钥连接
    ssh.connect(hostname, port=port, username=username, key_filename=private_key_path)

    logger.info(f"{hostname}连接成功")
    docker_num = int(server["docker_num"])
    storage_path = server["storage_path"]
    server_commands = []

    for i in range(docker_num):
        container_name = "_".join([base_name, str(i)])
        server_commands.append(f"docker stop {container_name}")
        server_commands.append(f"docker rm {container_name}")

    server_commands.append(f"rm -rf {storage_path}")
    for sever_command in server_commands:
        exec_command(ssh, sever_command)


# 列出服务器信息
def list_infomation(server):
    print("=================")
    translations = {
        "hostname": "主机名",
        "username": "用户名",
        "port": "端口号",
        "private_key_path": "本地私钥路径",
        "docker_num": "Docker容器数",
        "storage_path": "存储路径",
        "protocal": "协议",
        "site": "站点",
        "ip_addr": "IP地址",
        "time_per_website": "每个网站时间",
        "xray_name": "Xray配置文件",
        "disk": "磁盘",
    }
    for key, value in server.items():
        try:
            print(f"{translations[key]}：{value}")
        except KeyError:
            continue


# 删除服务器中的镜像
def rmi_images(server):
    # 暂停服务器中docker运行
    base_name = "spider_traffic"
    hostname = server["hostname"]
    username = server["username"]
    port = server["port"]
    private_key_path = server["private_key_path"]
    image_name = "192.168.194.63:5000/aimafan_spider_traffic:250127_ubuntu24"

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    # try:
    # 连接服务器,并初始化服务器
    # 使用私钥连接
    ssh.connect(hostname, port=port, username=username, key_filename=private_key_path)

    logger.info(f"{hostname}连接成功")
    server_commands = []

    server_commands.append(f"docker rmi {image_name}")
    for sever_command in server_commands:
        exec_command(ssh, sever_command)


# 主函数：并行处理所有服务器
def main(action):
    # 启动线程
    for server in servers_info:
        if action != "list":
            logger.info(f"开始处理{server['hostname']}")
        if action == "bushu":
            handle_server(server)
        elif action == "stop":
            stop_docker(server)
        elif action == "start":
            start_docker(server)
        elif action == "del":
            del_docker(server)
        elif action == "list":
            list_infomation(server)
        elif action == "rmi":
            rmi_images(server)


# 命令行参数解析入口
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="服务器处理脚本")
    parser.add_argument(
        "action",
        choices=["bushu", "stop", "del", "list", "rmi", "start"],
        help="bushu（服务器部署），stop（暂停所有docker），del（删除所有docker和存储数据）,list（列出所有操作的服务器信息）, rmi（删除制定的镜像），start（继续开始docker）",
    )
    args = parser.parse_args()

    main(args.action)
