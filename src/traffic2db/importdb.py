import os
import time

from pypcaptools import PcapToDatabaseHandler
from tqdm import tqdm

from traffic2db.myutils import project_path
from traffic2db.myutils.config import config

try:
    from traffic2db.myutils.feishu import send_feishu_message
except (ImportError, ModuleNotFoundError):

    def send_feishu_message(*args, **kwargs):
        pass


from traffic2db.myutils.logger import logger

os_name = "debian12"
PROCESS_PATH = os.path.join(project_path, "data", "processed.txt")


def load_processed(path=PROCESS_PATH):
    try:
        with open(path, "r") as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()


def save_processed(processed_set, path=PROCESS_PATH):
    with open(path, "w") as f:
        for item in processed_set:
            f.write(item + "\n")


def find_large_png_linked_pcaps(root_dir: str, size_threshold_kb: int = 12):
    """
    在 spider_traffic_* 目录下，查找 screenshot 子目录及其子目录中大于 size_threshold_kb 的 PNG 文件，
    并尝试在对应的 pcap 子目录中查找同名 .pcap 文件，若存在则写入输出文件。

    :param root_dir: 根目录（例如 'http_141.164.58.43/xray_traffic'）
    :param output_file: 输出的文件路径（记录符合条件的 .pcap 文件路径）
    :param size_threshold_kb: PNG 文件大小阈值（单位 KB）
    """
    threshold_bytes = size_threshold_kb * 1024
    matched_pcaps = []

    for subdir in os.listdir(root_dir):
        if subdir.startswith("spider_traffic_"):
            traffic_path = os.path.join(root_dir, subdir)
            screenshot_root = os.path.join(traffic_path, "data", "screenshot")
            pcap_root = os.path.join(traffic_path, "data", "pcap")

            if not os.path.isdir(screenshot_root) or not os.path.isdir(pcap_root):
                continue

            # 遍历 screenshot 目录下所有 png
            for root_dirpath, _, files in os.walk(screenshot_root):
                for file in files:
                    if file.endswith(".png"):
                        png_path = os.path.join(root_dirpath, file)
                        if os.path.getsize(png_path) > threshold_bytes:
                            # 计算相对路径（相对于 screenshot 根目录）
                            rel_path = os.path.relpath(png_path, screenshot_root)
                            # 构建对应的 pcap 文件路径
                            pcap_path = os.path.join(
                                pcap_root, os.path.splitext(rel_path)[0]
                            )

                            if os.path.exists(pcap_path):
                                matched_pcaps.append(pcap_path)

    return matched_pcaps


def get_database_config():
    return {
        "host": config["mysql"]["host"],
        "user": config["mysql"]["user"],
        "port": config["mysql"]["port"],
        "password": config["mysql"]["password"],
        "database": config["mysql"]["database"],
    }


def importdb(pcap_path):
    db_config = get_database_config()
    table_name = config["mysql"]["table"]

    pcap_name = os.path.basename(pcap_path)

    parts = os.path.splitext(pcap_name)[0].split("_")
    protocol = parts[0]
    if protocol == "http" or protocol == "https":
        protocol = "direct"

    site = parts[3]  # 地区
    domain = parts[4]  # 域名

    # logger.info(f"开始处理{pcap_path}")

    handler = PcapToDatabaseHandler(
        db_config,
        pcap_path,
        protocol,
        table_name,
        domain,
        site + "_" + os_name,
    )

    try:
        handler.pcap_to_database()
    except Exception as e:
        logger.error(f"{pcap_name} error：{e}")
        pass


def action(origin_root):
    # 1. 找到对应pcap的列表
    matched_pcaps = find_large_png_linked_pcaps(origin_root)
    # 2. 将pcap导入到数据库中
    processed_set = load_processed()
    for pcap_path in matched_pcaps:
        if pcap_path in processed_set:
            logger.info(f"跳过已处理的文件：{pcap_path}")
            continue

        try:
            importdb(pcap_path)
            processed_set.add(pcap_path)
            logger.info(f"成功处理：{pcap_path}")
        except Exception as e:
            logger.error(f"处理 {pcap_path} 时出错：{e}")
    save_processed(processed_set)


def main():
    source_path = config["path"]["source_path"]

    for file in tqdm(os.listdir(source_path)):
        origin_root = os.path.join(source_path, file, "xray_traffic")
        start_time = time.time()
        logger.info(f"处理 {origin_root}")
        action(origin_root)
        end_time = time.time()
        elapsed_time = end_time - start_time
        send_feishu_message(f"{file}入库完成，入库共消耗{elapsed_time:.2f} seconds")


if __name__ == "__main__":
    main()
