# main.py
import os
import time
from typing import Any, Dict, List, Set

# 假设您的 pypcaptools 库可以这样导入
from pypcaptools import PcapToDatabaseHandler, initialize_database_schema
from tqdm import tqdm

# 假设您的工具和配置可以这样导入
from traffic2db.myutils import project_path
from traffic2db.myutils.config import config
from traffic2db.myutils.logger import logger

try:
    from myutils.feishu import send_feishu_message
except ImportError:

    def send_feishu_message(*args, **kwargs):
        """如果飞书模块不存在，则定义一个什么都不做的函数"""
        logger.warning("Feishu module not found, notifications will be skipped.")
        pass


# --- 常量定义 ---
# 使用 os.path.join 保证跨平台兼容性
PROCESSED_FILE_LOG = os.path.join(project_path, "data", "processed_files.log")
OS_NAME_TAG = "debian12"  # 可以根据实际情况修改或从配置读取


# --- 已处理文件管理器 ---
def load_processed_files(path: str = PROCESSED_FILE_LOG) -> Set[str]:
    """从日志文件中加载已处理过的 pcap 文件路径集合"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()


def save_processed_file(pcap_path: str, path: str = PROCESSED_FILE_LOG):
    """将新处理完的 pcap 文件路径追加到日志文件中"""
    with open(path, "a", encoding="utf-8") as f:
        f.write(pcap_path + "\n")


def find_data_pairs(source_path: str) -> List[Dict[str, str]]:
    """
    ### MODIFIED ###
    根据更新后的目录结构，递归查找所有匹配的 pcap 和 json 文件对。
    新结构: .../pcap/[url_dir]/[pcap_file] 和 .../json/[url_dir]/[json_file]

    Args:
        source_path: 数据集的顶层根目录。

    Returns:
        一个字典列表，每个字典包含 'pcap' 和 'json' 两个键。
    """
    data_pairs = []
    logger.info(f"开始从根目录 {source_path} 扫描文件...")

    if not os.path.isdir(source_path):
        logger.error(f"源目录不存在: {source_path}")
        return []

    # 遍历第一层 http_x.x.x.x 目录
    for spider_dir in os.listdir(source_path):
        if not spider_dir.startswith("spider_traffic_"):
            continue

        traffic_path = os.path.join(source_path, spider_dir)
        pcap_root = os.path.join(traffic_path, "data", "pcap")
        json_root = os.path.join(traffic_path, "data", "pcap")

        if not (os.path.isdir(pcap_root) and os.path.isdir(json_root)):
            continue

        # ### NEW ###: 增加一层循环，遍历 pcap_root 下的 [url] 目录
        for url_dir in os.listdir(pcap_root):
            pcap_url_path = os.path.join(pcap_root, url_dir)

            json_url_path = os.path.join(json_root, url_dir)

            # 确保 pcap 和 json 两边都存在对应的URL目录
            if not (os.path.isdir(pcap_url_path) and os.path.isdir(json_url_path)):
                continue

            # 在 [url] 目录下遍历 pcap 文件并查找对应的 json 文件
            for pcap_file in os.listdir(pcap_url_path):
                if not pcap_file.endswith(".pcap"):
                    continue
                pcap_name, _ = os.path.splitext(pcap_file)

                # 构建完整的文件路径
                full_pcap_path = os.path.join(pcap_url_path, pcap_file)

                json_file = f"{pcap_name}.json"
                full_json_path = os.path.join(json_url_path, json_file)

                # 最终确认文件存在
                if os.path.exists(full_json_path):
                    data_pairs.append({"pcap": full_pcap_path, "json": full_json_path})

    return data_pairs


# --- 核心处理逻辑 ---
def get_database_config() -> Dict[str, Any]:
    """从全局配置中提取数据库连接信息"""
    return {
        "host": config["mysql"]["host"],
        "user": config["mysql"]["user"],
        "port": config["mysql"]["port"],
        "password": config["mysql"]["password"],
        "database": config["mysql"]["database"],
    }


def process_file_pair(
    file_pair: Dict[str, str], db_config: Dict[str, Any], base_table_name: str
):
    """
    处理单个 pcap-json 文件对，并将其数据导入数据库。
    这是旧脚本中 `importdb` 函数的替代者。
    """
    pcap_path = file_pair["pcap"]
    json_path = file_pair["json"]
    pcap_name = os.path.basename(pcap_path)

    try:
        # 从文件名解析元数据
        parts = os.path.splitext(pcap_name)[0].split("_")
        protocol = parts[0]
        if protocol.lower() in ["http", "https"]:
            protocol = "direct"

        # 假设文件名结构固定
        # 例如: https_tls_google_jp_www.google.com_20250828231010
        site_tag = parts[3]
        domain = parts[4]
        collection_machine = f"{site_tag}_{OS_NAME_TAG}"

        # 使用新的 PcapToDatabaseHandler 接口
        handler = PcapToDatabaseHandler(
            db_config=db_config,
            base_table_name=base_table_name,
            input_pcap_file=pcap_path,
            input_json_file=json_path,
            protocol=protocol,
            accessed_website=domain,
            collection_machine=collection_machine,
        )

        # 执行入库操作
        success = handler.pcap_to_database()

        if success:
            logger.info(f"成功处理并入库: {pcap_name}")
            return True
        else:
            logger.warning(f"处理完成但未成功入库 (可能已存在或数据无效): {pcap_name}")
            return False

    except IndexError:
        logger.error(f"文件名格式不正确，无法解析: {pcap_name}")
        return False
    except Exception as e:
        logger.error(f"处理 {pcap_name} 时发生严重错误: {e}", exc_info=True)
        return False


# --- 主流程控制 ---
def run_task(source_root: str, base_table_name: str):
    """
    执行整个数据入库任务：发现文件、筛选、处理、记录。
    """
    logger.info(f"开始扫描目录: {source_root}")
    all_data_pairs = find_data_pairs(source_root)

    if not all_data_pairs:
        logger.info("未找到任何匹配的 pcap/json 文件对。")
        return

    logger.info(f"共发现 {len(all_data_pairs)} 个有效文件对。")

    processed_files = load_processed_files()
    db_config = get_database_config()
    initialize_database_schema(db_config, base_table_name)

    files_to_process = [
        pair for pair in all_data_pairs if pair["pcap"] not in processed_files
    ]

    if not files_to_process:
        logger.info("所有发现的文件都已被处理过，任务结束。")
        return

    logger.info(f"筛选出 {len(files_to_process)} 个新文件待处理。")

    success_count = 0
    fail_count = 0
    for pair in tqdm(files_to_process, desc=f"处理 {os.path.basename(source_root)}"):
        if process_file_pair(pair, db_config, base_table_name):
            success_count += 1
            save_processed_file(pair["pcap"])  # 处理成功一个，就记录一个
        else:
            fail_count += 1

    logger.info(f"处理完成。成功: {success_count}, 失败: {fail_count}。")
    return success_count, fail_count


def main():
    """
    程序主入口
    """
    try:
        source_path = config["path"]["source_path"]
        base_table_name = config["mysql"]["table"]  # 从配置读取基础表名
    except KeyError as e:
        logger.error(f"配置文件缺失关键项: {e}。请检查您的 config 文件。")
        return

    for dir_name in os.listdir(source_path):
        origin_root = os.path.join(source_path, dir_name)
        if not os.path.isdir(origin_root):
            continue

        logger.info(f"========== 开始处理批次: {dir_name} ==========")
        start_time = time.time()

        run_task(origin_root, base_table_name)

        elapsed_time = time.time() - start_time
        logger.info(f"批次 {dir_name} 处理完成，耗时 {elapsed_time:.2f} 秒。")

        # 发送飞书通知
        send_feishu_message(f"批次 {dir_name} 入库完成，耗时 {elapsed_time:.2f} 秒。")


if __name__ == "__main__":
    main()
