import os
import subprocess
from datetime import datetime, timedelta  # 导入timedelta用于时间计算

import paramiko

# 尝试导入飞书消息发送函数，如果失败则定义一个空函数，确保代码可运行
try:
    from traffic_spider_bushu.myutils.feishu import send_feishu_message
except (ImportError, ModuleNotFoundError):
    # 如果导入失败，则定义一个不执行任何操作的send_feishu_message函数，避免程序崩溃
    def send_feishu_message(*args, **kwargs):
        pass


# 从自定义模块导入数据库导入主函数、项目路径、配置和日志记录器
from traffic2db.importdb import main as importdb
from traffic_spider_bushu.action import get_ssh_config
from traffic_spider_bushu.myutils import project_path
from traffic_spider_bushu.myutils.config import config
from traffic_spider_bushu.myutils.logger import logger
from traffic_spider_bushu.server_info import servers_info  # 导入服务器信息
from traffic_spider_bushu.server_monitoring import (
    action as check_usage_action,  # 导入服务器监控操作
)

# 从配置文件中获取本地数据存储的根目录
LOCAL_ROOT_DIR = config["path"]["source_path"]


def is_file_time_old(filename: str, hours_threshold: int = 4) -> bool:
    """
    判断文件名中包含的时间与当前时间是否相差指定小时数以上。
    文件名中的时间格式类似 '20241211001423'。

    Args:
        filename (str): 包含时间信息的文件名。
        hours_threshold (int): 时间差的阈值，单位小时。默认为4小时。

    Returns:
        bool: 如果时间差超过阈值返回 True，否则返回 False。
    """
    # 从文件名中提取时间字符串
    time_str = ""
    parts = filename.split("_")
    for part in parts:
        if len(part) == 14 and part.isdigit():
            time_str = part
            break

    if not time_str:
        logger.warning(f"文件名 '{filename}' 中未找到有效的时间字符串，跳过时间检查。")
        return False  # 如果没有找到时间字符串，则认为不是旧文件

    try:
        # 将提取到的时间字符串转换为 datetime 对象
        file_time = datetime.strptime(time_str, "%Y%m%d%H%M%S")
    except ValueError:
        logger.error(f"文件名 '{filename}' 中的时间字符串 '{time_str}' 格式不正确。")
        return False

    # 获取当前时间
    current_time = datetime.now()
    # 计算时间差
    time_diff = current_time - file_time
    # 将时间差转换为小时数（取绝对值，因为只关心差值大小）
    # 这里减去8小时可能是因为服务器和本地的时区差异，需要根据实际情况调整
    hours_diff = abs(time_diff.total_seconds() / 3600)

    # 返回时间差是否超过阈值
    return hours_diff > hours_threshold


def sync_data_with_rsync(
    hostname: str, username: str, remote_dir: str, protocol: str
) -> str:
    """
    使用 rsync 命令从远程服务器同步数据到本地。

    Args:
        hostname (str): 远程主机名或IP地址。
        username (str): 用于SSH连接的用户名。
        remote_dir (str): 远程服务器上待同步的目录。
        protocol (str): 协议名称，用于构建本地存储路径。

    Returns:
        str: 本地同步后的根目录路径。
    Raises:
        subprocess.CalledProcessError: 如果 rsync 命令执行失败。
    """
    # 构建本地数据存储路径，格式为：LOCAL_ROOT_DIR/protocol_hostname
    local_path = os.path.join(LOCAL_ROOT_DIR, f"{protocol}_{hostname}")
    # 确保本地目录存在，如果不存在则创建
    os.makedirs(local_path, exist_ok=True)

    logger.info(f"开始从 {hostname} 同步数据到 {local_path}...")
    # 构建 rsync 命令，-az 表示归档模式和压缩传输
    ssh_opts = "ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null"

    rsync_command = [
        "rsync",
        "-az",
        "-e",
        ssh_opts,  # 告诉 rsync 使用带有特定参数的 ssh
        f"{username}@{hostname}:{remote_dir}/",
        local_path,
    ]
    try:
        # 执行 rsync 命令，check=True 表示如果命令返回非零退出码则抛出 CalledProcessError
        subprocess.run(rsync_command, check=True, capture_output=True, text=True)
        logger.info(f"数据从 {hostname} 同步完成！")
    except subprocess.CalledProcessError as e:
        logger.error(f"从 {hostname} 同步数据失败：{e.stderr.strip()}")
        raise  # 重新抛出异常，以便上层调用者可以处理
    except FileNotFoundError:
        logger.error("rsync 命令未找到，请确认已安装 rsync。")
        raise
    return local_path


def execute_remote_script(
    hostname: str, port: int, username: str, private_key_path: str, script_path: str
):
    """
    通过 SSH 在远程服务器上执行指定的 shell 脚本。

    Args:
        hostname (str): 远程主机名或IP地址。
        port (int): SSH 连接端口。
        username (str): 用于SSH连接的用户名。
        private_key_path (str): SSH 私钥文件的路径。
        script_path (str): 远程服务器上要执行的脚本的完整路径。
    """
    ssh_client = paramiko.SSHClient()
    # 自动添加远程主机的密钥，不进行严格的主机密钥检查（首次连接时可能需要用户确认）
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    user_config = get_ssh_config(hostname)
    proxy = None
    if "proxycommand" in user_config:
        proxy = paramiko.ProxyCommand(user_config["proxycommand"])

    try:
        logger.info(f"正在连接到 {hostname}:{port}...")
        ssh_client.connect(
            hostname,
            port=port,
            username=username,
            key_filename=private_key_path,
            sock=proxy,
        )
        logger.info(f"已连接到 {hostname}，正在执行远程脚本：{script_path}")
        # 执行远程命令，stdin, stdout, stderr 是文件对象
        stdin, stdout, stderr = ssh_client.exec_command(f"bash {script_path}")

        # 读取标准错误输出
        error_output = stderr.read().decode().strip()
        # 读取标准输出
        output = stdout.read().decode().strip()

        if output:
            logger.info(f"远程脚本输出：\n{output}")
        if error_output:
            logger.error(f"远程脚本执行错误：\n{error_output}")
            # send_feishu_message(
            #     f"警告：在 {hostname} 上执行远程脚本 '{script_path}' 时发生错误：{error_output}"
            # )
        else:
            logger.info(f"在 {hostname} 上成功执行远程脚本 '{script_path}'。")
    except paramiko.AuthenticationException:
        logger.error(f"SSH 认证失败，请检查用户名、私钥或密码。主机: {hostname}")
        # send_feishu_message(f"错误：SSH 认证失败，主机: {hostname}")
    except paramiko.SSHException as e:
        logger.error(f"SSH 连接或执行命令失败：{e}")
        # send_feishu_message(
        # f"错误：SSH 连接或执行命令失败，主机: {hostname}，错误: {e}"
        # )
    except Exception as e:
        logger.error(f"执行远程脚本时发生未知错误：{e}")
        # send_feishu_message(f"错误：在 {hostname} 上执行远程脚本时发生未知错误：{e}")
    finally:
        # 确保SSH连接关闭
        if ssh_client:
            ssh_client.close()


def main():
    """
    主程序入口：遍历所有配置的服务器，执行数据同步、远程清理和数据入库操作。
    """
    logger.info("--- 数据同步和入库流程开始 ---")

    for server_info in servers_info:
        hostname = server_info["hostname"]
        username = server_info["username"]
        storage_path = server_info["storage_path"]
        protocol = server_info["protocal"]
        port = server_info["port"]
        private_key_path = server_info["private_key_path"]

        logger.info(f"\n--- 正在处理服务器: {hostname} ---")

        try:
            # 1. 使用 rsync 从远程服务器拉取数据到本地
            local_data_root_path = sync_data_with_rsync(
                hostname, username, storage_path, protocol
            )

            # 2. 在远程服务器上执行脚本删除旧的 pcap 文件
            # 假设远程清理脚本的路径是 storage_path 下的 del_old_pcap.sh
            remote_cleanup_script_path = os.path.join(storage_path, "del_old_pcap.sh")
            execute_remote_script(
                hostname, port, username, private_key_path, remote_cleanup_script_path
            )

            # send_feishu_message(f"🎉 {hostname} 数据同步及远程旧数据清理完成！")

        except Exception as e:
            logger.error(f"处理 {hostname} 时发生错误：{e}")
            # send_feishu_message(f"❌ 处理 {hostname} 失败：{e}")
            # 如果某个服务器处理失败，可以选择跳过或继续处理下一个
            continue

    # --- 分隔线：所有服务器数据拉取和远程清理完成后 ---
    logger.info("\n--- 所有服务器数据拉取和远程清理完成，开始本地操作 ---")

    # 3. 检查服务器资源使用情况（例如磁盘、内存等）
    logger.info("开始检查服务器资源使用情况...")
    check_usage_action()
    # send_feishu_message("✅ 服务器资源使用情况检查完成。")

    # # 4. 将本地同步下来的数据导入数据库
    # logger.info("开始将数据导入数据库...")
    # try:
    #     importdb()  # 调用导入数据库的主函数
    #     logger.info("数据成功导入数据库！")
    #     send_feishu_message("✅ 所有本地数据已成功导入数据库！")
    # except Exception as e:
    #     logger.error(f"数据导入数据库失败：{e}")
    #     send_feishu_message(f"❌ 数据导入数据库失败：{e}")

    logger.info("\n--- 数据同步和入库流程结束 ---")


if __name__ == "__main__":
    main()
