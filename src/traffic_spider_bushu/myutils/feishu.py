import json
import os

import requests

PROJECT_NAME = os.path.basename(os.path.abspath(os.curdir))

# 你的自定义机器人Webhook地址
FEISHU_WEBHOOK = (
    "https://www.feishu.cn/flow/api/trigger-webhook/fdd395200a7db298e4ff36e885fc0d58"
)


def send_feishu_message(text: str):
    headers = {"Content-Type": "application/json"}
    data = {"title": PROJECT_NAME, "content": text}
    resp = requests.post(FEISHU_WEBHOOK, headers=headers, data=json.dumps(data))
    if resp.status_code == 200:
        print(f"send feishu message success: {text}")
    else:
        print(f"send fail: {resp.status_code} {resp.text}")


# 调用示例
if __name__ == "__main__":
    send_feishu_message("你好，飞书！这是一条测试消息。")
