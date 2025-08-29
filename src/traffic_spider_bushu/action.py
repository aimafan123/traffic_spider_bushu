import argparse
import os

import paramiko
from scp import SCPClient

# 从自定义模块导入项目路径、配置、日志记录器和服务器信息
from traffic_spider_bushu.myutils import project_path
from traffic_spider_bushu.myutils.config import config
from traffic_spider_bushu.myutils.logger import logger
from traffic_spider_bushu.server_info import servers_info


def exec_command_async(client: paramiko.SSHClient, command: str):
    """
    在远程服务器上异步执行命令，并实时打印标准输出和标准错误输出。

    Args:
        client (paramiko.SSHClient): 已建立连接的SSH客户端实例。
        command (str): 要在远程服务器上执行的命令字符串。
    """
    logger.info(f"正在执行远程命令: {command}")
    stdin, stdout, stderr = client.exec_command(command)

    while not stdout.channel.exit_status_ready():
        if stdout.channel.recv_ready():
            for line in stdout:
                print(f"STDOUT: {line.strip()}")

    # 补充读取剩余输出
    for line in stdout:
        print(f"STDOUT: {line.strip()}")

    # 读取命令执行后的所有标准错误输出
    err = stderr.read().decode().strip()
    if err:
        logger.error(f"STDERR: {err}")  # 如果有错误，则记录错误日志
        print(f"STDERR: {err}")

    # 记录命令的退出状态码
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        logger.warning(f"命令 '{command}' 以非零状态码 {exit_status} 退出。")


def get_exclude_keywords_content() -> str:
    """
    获取爬虫排除关键词的默认内容字符串。

    Returns:
        str: 包含排除关键词的字符串。
    """
    exclude_str = """register
signin
login
Help
help
policies
Policies
policy
Policy
account
"""
    return exclude_str.strip()  # 移除首尾空白符


def get_running_status_content() -> str:
    """
    获取表示爬虫运行状态的默认内容字符串。

    Returns:
        str: 包含运行状态信息的字符串。
    """
    running_str = """{"currentIndex": 0}"""
    return running_str.strip()


def run_command_sync(ssh_client: paramiko.SSHClient, command: str):
    """
    在远程服务器上同步执行命令，并记录标准输出和标准错误输出到日志。

    Args:
        ssh_client (paramiko.SSHClient): 已建立连接的SSH客户端实例。
        command (str): 要在远程服务器上执行的命令字符串。
    """
    logger.info(f"同步执行远程命令: {command}")
    stdin, stdout, stderr = ssh_client.exec_command(command)

    # 读取所有标准输出和标准错误输出
    stdout_output = stdout.read().decode().strip()
    stderr_output = stderr.read().decode().strip()

    if stdout_output:
        logger.info(f"STDOUT:\n{stdout_output}")
    if stderr_output:
        logger.error(f"STDERR:\n{stderr_output}")  # 错误信息使用 error 级别记录


def upload_file_scp(scp_client: SCPClient, local_file_path: str, remote_file_path: str):
    """
    使用 SCP 异步上传文件到远程服务器。

    Args:
        scp_client (SCPClient): 已建立连接的SCP客户端实例。
        local_file_path (str): 本地文件的完整路径。
        remote_file_path (str): 远程服务器上目标文件的完整路径。
    """
    if os.path.exists(local_file_path):
        try:
            scp_client.put(local_file_path, remote_file_path)
            logger.info(f"文件 '{local_file_path}' 成功上传到 '{remote_file_path}'。")
        except Exception as e:
            logger.error(
                f"上传文件 '{local_file_path}' 到 '{remote_file_path}' 失败: {e}"
            )
    else:
        logger.warning(f"警告: 本地文件 '{local_file_path}' 不存在，跳过上传。")


def generate_server_config_content(server_info: dict) -> str:
    """
    根据服务器信息生成服务器专属的配置文件内容字符串 (INI 格式)。

    Args:
        server_info (dict): 包含服务器配置信息的字典。

    Returns:
        str: 生成的配置文件内容字符串。
    """
    config_str = f"""[information]
name={server_info["hostname"]}
protocal={server_info["protocal"]}
site={server_info["site"]}
ip_addr={server_info["ip_addr"]}

# 这里代理xray使用http代理，tor使用socks5代理
[proxy]
host=127.0.0.1
port={server_info["proxy_port"]}

[spider]
depth=-1
time_per_website={server_info["time_per_website"]}
# 爬虫连续爬取URL的延时。单位秒
download_delay = 60
mode = {server_info["spider_mode"]}
scroll = {server_info["scroll"]}
scroll_num = {server_info["scroll_num"]}
multisite_num = {server_info["multisite_num"]}
webnum={server_info["webnum"]}
disable_quic={server_info["disable_quic"]}"""
    return config_str


def split_url_file(input_file_path: str, num_parts: int) -> list[str]:
    """
    将一个文件（通常是URL列表）按指定的份数进行分割。

    Args:
        input_file_path (str): 输入文件的完整路径。
        num_parts (int): 要分割的份数。

    Returns:
        list[str]: 包含分割后每一份内容的字符串列表。
    Raises:
        FileNotFoundError: 如果输入文件不存在。
    """
    if not os.path.exists(input_file_path):
        raise FileNotFoundError(f"输入文件 '{input_file_path}' 不存在。")

    with open(input_file_path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    num_lines = len(lines)
    if num_lines == 0:
        logger.warning(f"文件 '{input_file_path}' 为空，返回空分割。")
        return [""] * num_parts  # 如果文件为空，则返回指定数量的空字符串列表

    # 计算每份的行数，向上取整以确保所有行都被分配
    chunk_size = (num_lines + num_parts - 1) // num_parts

    parts = []
    for i in range(num_parts):
        start_index = i * chunk_size
        end_index = min(start_index + chunk_size, num_lines)  # 确保不超过总行数
        chunk_lines = lines[start_index:end_index]
        parts.append("".join(chunk_lines).strip())  # 拼接并移除首尾空白符

    return parts


def handle_server_deployment(server_info: dict):
    """
    处理单个服务器的部署任务，包括初始化环境、传输文件、配置Docker容器等。

    Args:
        server_info (dict): 包含服务器详细配置信息的字典。
    Raises:
        ValueError: 如果 spider_mode 无效。
        paramiko.SSHException: 如果SSH连接或操作失败。
        FileNotFoundError: 如果文件不存在。
    """
    # 爬虫类型校验
    valid_spider_modes = ["direct", "xray", "tor"]
    if server_info["spider_mode"] not in valid_spider_modes:
        raise ValueError(
            f"spider_mode 必须是 {valid_spider_modes} 之一，当前为: {server_info['spider_mode']}"
        )

    # 提取服务器连接信息
    hostname = server_info["hostname"]
    username = server_info["username"]
    port = server_info["port"]
    private_key_path = server_info["private_key_path"]

    # 提取其他配置信息
    docker_num = int(server_info["docker_num"])
    storage_path = server_info["storage_path"]
    image_name = config["spider"]["image_name"]

    # 根据爬虫模式确定本地和远程的配置文件路径
    if server_info["spider_mode"] == "xray" or server_info["spider_mode"] == "direct":
        local_proxy_config_path = os.path.join(
            project_path, "data", "xray_config", server_info["xray_name"]
        )
        remote_proxy_config_path = "~/xray.json"
    elif server_info["spider_mode"] == "tor":
        local_proxy_config_path = os.path.join(
            project_path, "data", "torrc_s", server_info["torrc_name"]
        )
        remote_proxy_config_path = "~/torrc"
    else:  # 理论上前面已经校验过，这里作为防御性编程
        raise ValueError(f"不支持的 spider_mode: {server_info['spider_mode']}")

    # 本地删除旧 pcap 文件的脚本路径
    local_del_old_pcap_script = os.path.join(project_path, "data", "del_old_pcap.sh")
    remote_del_old_pcap_script = os.path.join(storage_path, "del_old_pcap.sh")

    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # 自动添加主机密钥

    try:
        logger.info(f"正在连接到 {hostname}:{port}...")
        # 使用私钥连接服务器
        ssh_client.connect(
            hostname, port=port, username=username, key_filename=private_key_path
        )
        logger.info(f"成功连接到 {hostname}。")

        # 获取SCP客户端
        with SCPClient(ssh_client.get_transport()) as scp_client:
            # 1. 删除并重新创建存储路径（注意：此操作会清空目录，请谨慎！）
            exec_command_async(ssh_client, f"rm -rf {storage_path}")
            exec_command_async(
                ssh_client, f"mkdir -p {storage_path}"
            )  # -p 确保父目录也一并创建

            # 2. 上传代理配置文件和 pcap 清理脚本
            upload_file_scp(
                scp_client, local_proxy_config_path, remote_proxy_config_path
            )
            upload_file_scp(
                scp_client, local_del_old_pcap_script, remote_del_old_pcap_script
            )
            exec_command_async(
                ssh_client, f"chmod +x {remote_del_old_pcap_script}"
            )  # 添加执行权限

            # 3. 配置服务器级别的网络接口
            exec_command_async(ssh_client, "ethtool -K docker0 tso off gso off gro off")

            # 统计所有主机的 Docker 容器总数，用于 URL 分割
            total_docker_num = sum(int(s["docker_num"]) for s in servers_info)
            # 计算当前服务器在所有 Docker 容器中的起始索引
            current_server_start_index = 0
            for s in servers_info:
                if s["hostname"] == hostname:
                    break
                current_server_start_index += int(s["docker_num"])

            # 分割 URL 文件，为每个 Docker 容器准备其专属的 URL 列表
            url_parts_list = split_url_file(
                os.path.join(project_path, "urls.txt"), total_docker_num
            )

            # --- 为每个 Docker 容器生成配置和启动命令 ---
            commands_to_execute = []  # 存储所有待执行的命令
            main_spider_start_commands = []  # 存储启动主爬虫进程的命令

            for i in range(docker_num):
                container_base_name = "spider_traffic"
                container_name = f"{container_base_name}_{i}"

                # 定义容器内部挂载的目录路径
                container_config_dir = os.path.join(
                    storage_path, container_name, "config"
                )
                container_data_dir = os.path.join(storage_path, container_name, "data")
                container_logs_dir = os.path.join(storage_path, container_name, "logs")

                # 停止并删除已存在的同名 Docker 容器
                commands_to_execute.append(f"docker stop {container_name}")
                commands_to_execute.append(f"docker rm {container_name}")

                # 创建容器挂载所需的目录
                commands_to_execute.append(f"mkdir -p {container_config_dir}")
                commands_to_execute.append(f"mkdir -p {container_data_dir}")
                commands_to_execute.append(f"mkdir -p {container_logs_dir}")

                # 需要先执行一波
                for cmd in commands_to_execute:
                    exec_command_async(ssh_client, cmd)

                commands_to_execute.clear()  # 清空命令列表，准备下一轮

                # 生成并写入容器的 config.ini 配置文件
                config_content = generate_server_config_content(server_info)
                commands_to_execute.append(
                    f"echo '{config_content}' > {os.path.join(container_config_dir, 'config.ini')}"
                )

                # 处理当前 Docker 容器的 URL 列表
                current_docker_url_content = url_parts_list[
                    current_server_start_index + i
                ]

                # 将当前容器的 URL 列表内容写入临时文件，并上传到远程服务器
                temp_local_url_file = os.path.join(
                    project_path,
                    "data",
                    "tmp",
                    f"{container_name}_current_docker_url_list.txt",
                )
                os.makedirs(os.path.dirname(temp_local_url_file), exist_ok=True)
                with open(temp_local_url_file, "w", encoding="utf-8") as f:
                    f.write(current_docker_url_content)

                upload_file_scp(
                    scp_client,
                    temp_local_url_file,
                    os.path.join(container_config_dir, "current_docker_url_list.txt"),
                )
                os.remove(temp_local_url_file)  # 清理本地临时文件

                # 写入排除关键词文件
                commands_to_execute.append(
                    f"echo '{get_exclude_keywords_content()}' > {os.path.join(container_config_dir, 'exclude_keywords')}"
                )

                # 启动 Docker 容器
                # --privileged 赋予容器特权模式，可能需要根据具体需求调整
                # -itd 交互式、分配伪TTY、后台运行
                # -v 挂载本地目录到容器内部
                commands_to_execute.append(
                    f"docker run -v {container_data_dir}:/app/data "
                    f"-v {container_config_dir}:/app/config "
                    f"-v {container_logs_dir}:/app/logs "
                    f"--privileged -itd --name {container_name} {image_name} /bin/bash"
                )

                # 关闭容器内网络接口的某些特性，优化网络性能
                commands_to_execute.append(
                    f"docker exec {container_name} ethtool -K eth0 tso off gso off gro off lro off"
                )

                # 将代理配置文件复制到容器内部
                commands_to_execute.append(
                    f"docker cp {remote_proxy_config_path} {container_name}:/app/config"
                )

                # 构造在容器内执行主爬虫进程的命令，并将输出重定向到日志文件
                # nohup 和 & 使得命令在后台运行，即使SSH会话关闭也能继续执行
                main_spider_start_commands.append(
                    f"nohup docker exec {container_name} bash action.sh > {os.path.join(storage_path, container_name + '.log')} 2>&1 &"
                )

            # 批量执行所有准备命令
            for cmd in commands_to_execute:
                exec_command_async(ssh_client, cmd)

            # 批量执行启动主爬虫的命令
            for cmd in main_spider_start_commands:
                exec_command_async(ssh_client, cmd)

    except paramiko.AuthenticationException:
        logger.error(f"SSH 认证失败，请检查用户名、私钥或密码。主机: {hostname}")
        raise
    except paramiko.SSHException as e:
        logger.error(f"SSH 连接或执行命令失败：{e}。主机: {hostname}")
        raise
    except FileNotFoundError as e:
        logger.error(f"所需文件未找到：{e}。请检查路径。")
        raise
    except Exception as e:
        logger.error(f"处理服务器 {hostname} 时发生未知错误：{e}")
        raise
    finally:
        if ssh_client:
            ssh_client.close()  # 确保关闭SSH连接


def start_dockers_on_server(server_info: dict):
    """
    在远程服务器上启动所有 spider_traffic 相关的 Docker 容器。

    Args:
        server_info (dict): 包含服务器连接信息的字典。
    """
    hostname = server_info["hostname"]
    username = server_info["username"]
    port = server_info["port"]
    private_key_path = server_info["private_key_path"]
    storage_path = server_info["storage_path"]
    docker_num = int(server_info["docker_num"])
    base_container_name = "spider_traffic"

    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        logger.info(f"正在连接到 {hostname}:{port}...")
        ssh_client.connect(
            hostname, port=port, username=username, key_filename=private_key_path
        )
        logger.info(f"成功连接到 {hostname}。")

        commands_to_start = []
        for i in range(docker_num):
            container_name = f"{base_container_name}_{i}"
            commands_to_start.append(f"docker start {container_name}")
            # 重新启动容器内的爬虫进程
            commands_to_start.append(
                f"nohup docker exec {container_name} bash action.sh > {os.path.join(storage_path, container_name + '.log')} 2>&1 &"
            )

        for cmd in commands_to_start:
            exec_command_async(ssh_client, cmd)

    except paramiko.AuthenticationException:
        logger.error(f"SSH 认证失败，请检查用户名、私钥或密码。主机: {hostname}")
    except paramiko.SSHException as e:
        logger.error(f"SSH 连接或执行命令失败：{e}。主机: {hostname}")
    except Exception as e:
        logger.error(f"在 {hostname} 启动 Docker 容器时发生未知错误：{e}")
    finally:
        if ssh_client:
            ssh_client.close()


def stop_dockers_on_server(server_info: dict):
    """
    在远程服务器上停止所有 spider_traffic 相关的 Docker 容器。

    Args:
        server_info (dict): 包含服务器连接信息的字典。
    """
    hostname = server_info["hostname"]
    username = server_info["username"]
    port = server_info["port"]
    private_key_path = server_info["private_key_path"]
    docker_num = int(server_info["docker_num"])
    base_container_name = "spider_traffic"

    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        logger.info(f"正在连接到 {hostname}:{port}...")
        ssh_client.connect(
            hostname, port=port, username=username, key_filename=private_key_path
        )
        logger.info(f"成功连接到 {hostname}。")

        commands_to_stop = []
        for i in range(docker_num):
            container_name = f"{base_container_name}_{i}"
            commands_to_stop.append(f"docker stop {container_name}")

        for cmd in commands_to_stop:
            exec_command_async(ssh_client, cmd)

    except paramiko.AuthenticationException:
        logger.error(f"SSH 认证失败，请检查用户名、私钥或密码。主机: {hostname}")
    except paramiko.SSHException as e:
        logger.error(f"SSH 连接或执行命令失败：{e}。主机: {hostname}")
    except Exception as e:
        logger.error(f"在 {hostname} 停止 Docker 容器时发生未知错误：{e}")
    finally:
        if ssh_client:
            ssh_client.close()


def delete_dockers_and_data_on_server(server_info: dict):
    """
    在远程服务器上删除所有 spider_traffic 相关的 Docker 容器及其挂载的数据。
    **警告：此操作会删除数据，请谨慎！**

    Args:
        server_info (dict): 包含服务器连接信息的字典。
    """
    hostname = server_info["hostname"]
    username = server_info["username"]
    port = server_info["port"]
    private_key_path = server_info["private_key_path"]
    docker_num = int(server_info["docker_num"])
    storage_path = server_info["storage_path"]
    base_container_name = "spider_traffic"

    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        logger.info(f"正在连接到 {hostname}:{port}...")
        ssh_client.connect(
            hostname, port=port, username=username, key_filename=private_key_path
        )
        logger.info(f"成功连接到 {hostname}。")

        commands_to_delete = []
        for i in range(docker_num):
            container_name = f"{base_container_name}_{i}"
            commands_to_delete.append(f"docker stop {container_name}")  # 先停止
            commands_to_delete.append(f"docker rm {container_name}")  # 再删除容器

        # 最后删除存储路径下的所有数据
        commands_to_delete.append(f"rm -rf {storage_path}")

        for cmd in commands_to_delete:
            exec_command_async(ssh_client, cmd)

    except paramiko.AuthenticationException:
        logger.error(f"SSH 认证失败，请检查用户名、私钥或密码。主机: {hostname}")
    except paramiko.SSHException as e:
        logger.error(f"SSH 连接或执行命令失败：{e}。主机: {hostname}")
    except Exception as e:
        logger.error(f"在 {hostname} 删除 Docker 容器和数据时发生未知错误：{e}")
    finally:
        if ssh_client:
            ssh_client.close()


def list_server_information(server_info: dict):
    """
    打印单个服务器的详细配置信息。

    Args:
        server_info (dict): 包含服务器信息的字典。
    """
    print("\n" + "=" * 30)  # 分隔线
    print(f"服务器信息: {server_info.get('hostname', '未知主机')}")
    print("=" * 30)

    # 定义一个字典，用于将英文键名翻译成中文，提高输出的可读性
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
        "time_per_website": "每个网站停留时间 (秒)",
        "xray_name": "Xray配置文件名",
        "torrc_name": "TorRC配置文件名",  # 添加 torrc_name 的翻译
        "spider_mode": "爬虫模式",
        "proxy_port": "代理端口",
        "scroll": "是否滚动页面",
        "scroll_num": "滚动次数",
        "multisite_num": "多站点数量",
        "webnum": "爬取网站数量",
        "disk": "磁盘",  # 如果 server_info 中包含磁盘信息
    }

    # 遍历服务器信息字典，并使用翻译后的键名打印
    for key, value in server_info.items():
        translated_key = translations.get(key, key)  # 如果没有翻译，则使用原键名
        print(
            f"{translated_key:<{len('本地私钥路径')}s}: {value}"
        )  # 格式化输出，保持对齐


def remove_remote_docker_images(server_info: dict, image_name: str):
    """
    在远程服务器上删除指定的 Docker 镜像。

    Args:
        server_info (dict): 包含服务器连接信息的字典。
    """
    hostname = server_info["hostname"]
    username = server_info["username"]
    port = server_info["port"]
    private_key_path = server_info["private_key_path"]

    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        logger.info(f"正在连接到 {hostname}:{port}...")
        ssh_client.connect(
            hostname, port=port, username=username, key_filename=private_key_path
        )
        logger.info(f"成功连接到 {hostname}。")

        logger.info(f"正在删除 {hostname} 上的 Docker 镜像: {image_name}")
        # docker rmi 命令用于删除镜像
        exec_command_async(ssh_client, f"docker rmi {image_name}")
        logger.info(f"已请求删除 {hostname} 上的镜像 {image_name}。")

    except paramiko.AuthenticationException:
        logger.error(f"SSH 认证失败，请检查用户名、私钥或密码。主机: {hostname}")
    except paramiko.SSHException as e:
        logger.error(f"SSH 连接或执行命令失败：{e}。主机: {hostname}")
    except Exception as e:
        logger.error(f"在 {hostname} 删除 Docker 镜像时发生未知错误：{e}")
    finally:
        if ssh_client:
            ssh_client.close()


def load_remote_docker_image(server_info: dict, image_tar_path: str):
    """
    将本地 Docker 镜像 .tar 文件传输到远程服务器并加载。

    Args:
        server_info (dict): 包含服务器连接信息的字典。
        image_tar_path (str): 本地镜像 .tar 文件的路径。
    """
    hostname = server_info["hostname"]
    username = server_info["username"]
    port = server_info["port"]
    private_key_path = server_info["private_key_path"]

    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    sftp_client = None  # 初始化 SFTP 客户端变量

    try:
        logger.info(f"正在连接到 {hostname}:{port}...")
        ssh_client.connect(
            hostname, port=port, username=username, key_filename=private_key_path
        )
        logger.info(f"成功连接到 {hostname}。")

        # 获取本地文件名，作为远程服务器上的临时文件名
        remote_temp_path = image_tar_path

        logger.info(f"正在远程服务器上加载镜像...")
        exec_command_async(ssh_client, f"docker load -i {remote_temp_path}")
        logger.info("镜像加载命令已发送。")

        logger.info(f"正在删除远程服务器上的临时文件 '{remote_temp_path}'...")
        sftp_client.remove(remote_temp_path)
        logger.info("临时文件已成功删除。")

    except paramiko.AuthenticationException:
        logger.error(f"SSH 认证失败，请检查用户名、私钥或密码。主机: {hostname}")
    except paramiko.SSHException as e:
        logger.error(f"SSH 连接或执行命令失败：{e}。主机: {hostname}")
    except FileNotFoundError:
        logger.error(f"本地文件 '{image_rar_path}' 不存在，请检查路径。")
    except Exception as e:
        logger.error(f"在 {hostname} 加载 Docker 镜像时发生未知错误：{e}")
    finally:
        # 确保 SFTP 和 SSH 客户端都被关闭
        if sftp_client:
            sftp_client.close()
        if ssh_client:
            ssh_client.close()


def main(action: str, image_name: str = None, image_rar_path: str = None):
    """
    主函数，根据传入的动作参数，对所有配置的服务器执行相应的操作。

    Args:
        action (str): 要执行的操作。
        image_name (str): 要删除的Docker镜像名称，仅在action为"rmi"时需要。
        image_rar_path (str): 本地镜像 .rar 文件路径，仅在action为"load"时需要。
    """
    logger.info(f"--- 开始执行操作: {action} ---")

    for server_info in servers_info:
        hostname = server_info["hostname"]
        logger.info(f"\n--- 正在处理服务器: {hostname} ---")

        try:
            if action == "bushu":
                handle_server_deployment(server_info)
            elif action == "stop":
                stop_dockers_on_server(server_info)
            elif action == "start":
                start_dockers_on_server(server_info)
            elif action == "del":
                delete_dockers_and_data_on_server(server_info)
            elif action == "list":
                list_server_information(server_info)
            elif action == "rmi":
                remove_remote_docker_images(server_info, image_name)
            # 修改2: 新增 load 选项
            elif action == "load":
                load_remote_docker_image(server_info, image_name)
            else:
                logger.error(f"未知操作: {action}。")
                continue

        except Exception as e:
            logger.error(f"处理服务器 {hostname} 时发生错误: {e}")

    logger.info(f"--- 操作 '{action}' 执行完成 ---")


# 命令行参数解析
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="服务器部署与管理脚本。")
    parser.add_argument(
        "action",
        # 修改3: 在 choices 中添加 "load"
        choices=["bushu", "stop", "del", "list", "rmi", "start", "load"],
        help="选择要执行的操作: \n"
        "  bushu: 部署所有爬虫Docker容器并启动。\n"
        "  stop: 暂停所有爬虫Docker容器。\n"
        "  del: 删除所有爬虫Docker容器及其数据（**警告：数据将丢失**）。\n"
        "  list: 列出所有配置的服务器信息。\n"
        "  rmi: 删除指定的Docker镜像。**需要额外提供镜像名称**。\n"
        "  start: 启动所有已存在的爬虫Docker容器。\n"
        "  load: 将本地镜像 rar 包传输并加载到服务器。**需要额外提供 tar 文件路径**。",
    )
    parser.add_argument(
        "image_name",
        nargs="?",
        help="要删除的Docker镜像名称。当'action'为'rmi'时，此参数必填。",
    )

    args = parser.parse_args()

    # 检查 rmi 操作是否提供了 image_name
    if args.action == "rmi" and not args.image_name:
        parser.error("执行 'rmi' 操作必须提供一个镜像名称。")

    # 修改5: 增加检查 load 操作是否提供了 image_rar_path
    if args.action == "load" and not args.image_name:
        parser.error("执行 'load' 操作必须提供一个镜像 .tar 文件路径。")

    # 修改6: 调用主函数时，传入所有参数
    main(args.action, args.image_name)
