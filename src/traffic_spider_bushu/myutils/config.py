import configparser
import os
from traffic_spider_bushu.myutils import project_path

# 创建一个配置解析器
config = configparser.ConfigParser()

# 读取配置文件
config_defult_path = os.path.join(project_path, "config", "config.ini")
config.read(config_defult_path)

# 可以在这里添加一些函数来获取特定的配置项
# def get_database_config():
#     return {
#         'host': config['database']['host'],
#         'user': config['database']['user'],
#         'password': config['database']['password'],
#         'database': config['database']['database']
#     }
