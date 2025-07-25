import configparser
import os

from traffic2db.myutils import project_path

# 创建一个配置解析器
config = configparser.ConfigParser()

# 读取配置文件
config_defult_path = os.path.join(project_path, "config", "config.ini")
config.read(config_defult_path)
