import json
import os

import requests

from traffic2db.myutils.config import config
from traffic2db.myutils.logger import logger

PROJECT_NAME = os.path.basename(os.path.abspath(os.curdir))


FEISHU_WEBHOOK = config["notification"]["feishu_webhook"]


def send_feishu_message(text: str):
    headers = {"Content-Type": "application/json"}
    data = {"title": PROJECT_NAME, "content": text}
    resp = requests.post(FEISHU_WEBHOOK, headers=headers, data=json.dumps(data))
    if resp.status_code == 200:
        logger.info(f"send feishu message success: {text}")
    else:
        logger.info(f"send fail: {resp.status_code} {resp.text}")


if __name__ == "__main__":
    send_feishu_message("你好，飞书！这是一条测试消息。")
