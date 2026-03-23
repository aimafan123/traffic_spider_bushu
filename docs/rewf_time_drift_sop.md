# REWF 时间漂移测试流量采集 SOP

本文档对应仓库中的一键脚本：`scripts/rewf_time_drift_collect.sh`。

## 0. 前置准备

1. 在 Vultr 租用多台 VPS（建议同区域，便于控制网络变量）。
2. 在本机 `HOSTS_FILE`（默认 `/etc/hosts`）写入别名和 IP 映射。  
   你提到的是 `/etc/host`，Linux 实际文件通常是 `/etc/hosts`。

示例：

```text
66.135.22.157 vv6
66.135.8.79   vv7
107.191.42.143 vv8
45.77.202.166 vv9
```

3. 修改 `config/vps_init.conf`：
- `HOSTNAMES=(...)` 顺序要和你计划部署顺序一致
- `IMAGE_FILENAME="single_spider_traffic_260319.tar"`
- 如镜像不在项目根目录，增加 `LOCAL_IMAGE_PATH="/abs/path/to/xxx.tar"`


## 1. 一键执行 REWF 流程

在项目根目录运行：

```bash
bash scripts/rewf_time_drift_collect.sh
```

脚本会自动执行以下步骤：

1. 创建本地目录 `/netdisk/aimafan/traffic_datasets_new/rewf`，并更新 `config.ini` 的 `source_path`。
2. 在第一个 VPS 上检查并生成 `~/.ssh/id_ed25519`（不存在时自动 `ssh-keygen -t ed25519`）。
3. 调用 `scripts/init_vps_all.sh`：
- 基础初始化（hostname、/etc/hosts、Docker、免密）
- 将本地 tar 镜像上传到第一个 VPS
- 由第一个 VPS 分发镜像到其余 VPS 并 `docker load`
4. 自动更新 `src/traffic_spider_bushu/server_info.py` 的 `vps_name` 和 `hostname`。
5. 进入 `src` 后执行部署：`python -m traffic_spider_bushu.action bushu`。

## 2. 常用参数

```bash
# 指定配置文件
bash scripts/rewf_time_drift_collect.sh --config config/vps_init.conf

# 指定 server_info 文件
bash scripts/rewf_time_drift_collect.sh --server-info src/traffic_spider_bushu/server_info.py

# 指定本地数据目录和 config.ini
bash scripts/rewf_time_drift_collect.sh --dataset-root /netdisk/aimafan/traffic_datasets_new/rewf --config-ini config/config.ini

# 只做初始化和配置同步，不触发最终部署
bash scripts/rewf_time_drift_collect.sh --skip-deploy
```

## 3. 关键注意事项

1. `HOSTNAMES` 必须都能在 `HOSTS_FILE` 中解析到 IP，否则脚本会直接失败。
2. 脚本默认更新 `server_info.py` 的前 N 个节点（N=HOSTNAMES 数量）。
3. 更新 `server_info.py` 前会自动创建备份：`server_info.py.bak.YYYYMMDDHHMMSS`。


**warning：在执行完之后，要创建对应的流量保存目录，并且修改 config.ini 中的配置，并且 crontab 定时启动**