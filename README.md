# 自动部署流量采集程序

Traffic Spider 部署工具是一个 Python 脚本，旨在远程部署和管理多个服务器上的网络爬虫容器。本工具支持通过 SSH 连接到远程服务器，执行命令、上传文件、管理 Docker 容器，并根据配置自动启动爬虫任务。

docker代码项目路径 [spider_traffic.git](https://github.com/aimafan123/spider_traffic.git)

## 功能特性

远程执行 SSH 命令：通过 paramiko 连接服务器并执行命令。
文件传输：使用 scp 进行远程文件上传。
Docker 容器管理：支持启动、停止、删除 Docker 容器。
代理模式：支持 xray、tor、direct 三种代理模式。
任务分配：支持 URL 文件拆分，将任务均匀分配给多个容器。

## 部署步骤

0. 前期准备
- 代码在 `python3.12.3` 下测试通过
- 需要事先使用 `spider_traffic` 项目编译docker镜像，并将docker镜像文件放在所有远程服务器的 `~` 路径，并将路径名写入到config.ini中，默认所有远程服务器的镜像路径相同
- 需事先在服务器上安装docker并配置公私钥
- 如果是非root用户登录服务器，需要手动在服务器上执行
```
ethtool -K docker0 tso off gso off gro off
```

- 提前删除重名的docker镜像，可以在 `src` 路径使用 `python -m traffic_spider_bushu.action rmi` 指令

1. 安装依赖库
```
pip install -r requirements.txt
```
2. 参照 `data/xray_config/trojan.json.example` ，将xray客户端配置文件放到`data/xray_config/`目录中
3. 参照 `urls.txt.example` ，将需要采集的网站写入到项目目录的`urls.txt`文件中，注意，每行一个付费域
4. 修改`config/config.ini.example`，并将名称修改为 `config/config.ini`
5. 重点修改镜像名称，对应单网站采集和多网站采集
6. 将服务器信息填到`src/traffic_spider_bushu/server_info.py.example`，并按照注释填写爬虫具体情况，将文件名称改为`server_info.py`
7. 在`src`目录，执行
```
python -m traffic_spider_bushu.action bushu
```
程序自动执行，部署结束

## 服务器管理
本工具提供以下管理功能：

- 启动部署
- 停止容器
- 删除容器
- 查看服务器信息
- 删除 Docker 镜像

具体可以在 `src` 路径下运行 `python -m traffic_spider_bushu.action --help` 查看

## VPS 初始化（配置驱动）

现在 `scripts/init_vps.sh` 和 `scripts/init_vps2.sh` 支持统一配置文件与自动解析 IP。
`scripts/init_vps_all.sh` 已包含：
- 基础初始化（hostname、hosts、Docker、免密）
- 从本地上传 tar 镜像到第一个 VPS
- 由第一个 VPS 分发镜像到其余 VPS 并执行 `docker load`

1. 编辑 `config/vps_init.conf`（仓库已提供默认文件）  
- 只需要维护 `HOSTNAMES=(...)`  
- 脚本会从 `HOSTS_FILE`（默认 `/etc/hosts`）自动解析每个 hostname 对应的 IP  

2. 一键执行全部初始化（推荐）  
```bash
bash scripts/init_vps_all.sh
```

3. 或按阶段执行  
```bash
bash scripts/init_vps.sh
bash scripts/init_vps2.sh
```

也可通过 `--config` 指定其他配置文件路径，或用 `--skip-image` / `--skip-upload` 控制镜像阶段。

## REWF 时间漂移测试一键流程

可直接运行：

```bash
bash scripts/rewf_time_drift_collect.sh
```

该脚本会串联：
1. 创建本地目录 `/netdisk/aimafan/traffic_datasets_new/rewf` 并更新 `config.ini` 的 `source_path`
2. 在第一个 VPS 执行 `ssh-keygen -t ed25519`（如未生成）
3. 执行 `scripts/init_vps_all.sh`
4. 自动更新 `src/traffic_spider_bushu/server_info.py` 的 `vps_name` 与 `hostname`
5. 自动执行 `python -m traffic_spider_bushu.action bushu`

详细 SOP 见：`docs/rewf_time_drift_sop.md`


## 自动拉取数据

可以运行

```bash
bash bin/pull_data.sh 
```

实现自动数据拉取

## url信息

| 文件名                        | 内容简介                                   |
|------------------------------|--------------------------------------------|
| top_100000.txt               | 排名前 10 万的域名列表                    | 
| tranco_top1M.txt             | Tranco 排名前 100 万的域名合集            | 
| tranco_top1M_without_100.txt | 去除了前 100 的 Tranco 前 100 万域名列表 | 
| urls_10000.txt               | 1 万条 URL 列表                           | 
| urls_100.txt                 | 100 条 URL 列表（监控网站）                            |
| urls.txt                     | 爬虫爬取的域名                 | 
| wangwei_1000.txt             | 1000 条特定域名              |
