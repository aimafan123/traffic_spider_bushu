# Traffic Spider Bushu (分布式流量爬虫部署系统)

`traffic_spider_bushu` 是一个功能强大的分布式网络流量采集系统，专为在多个远程服务器上部署、管理和监控流量爬虫而设计。该系统利用 Docker 实现爬虫的容器化部署，通过 SSH 进行远程控制，并支持多种代理模式，能够高效地从大量网站收集网络流量数据（pcap 文件）。

> docker代码项目路径 [spider_traffic](https://github.com/aimafan123/spider_traffic.git)

## ✨ 主要功能

- **🚀 分布式部署**: 在多台服务器上自动化部署和管理爬虫 Docker 容器。
- **💻 远程控制**: 通过 SSH 和 SCP，轻松实现对远程服务器的脚本执行、文件传输和环境配置。
- **📦 Docker 化**: 爬虫在隔离的 Docker 容器中运行，确保环境一致性和易于管理。
- **🛡️ 多代理支持**: 支持 `direct` (直连)、`xray` 和 `tor` 等多种代理模式，灵活应对不同网络环境。
- **🔄 数据同步**: 使用 `rsync` 高效地将远程服务器上采集到的 pcap 数据同步到本地。
- **📊 数据入库**: 提供将 pcap 和关联的 json 数据解析并导入到 MySQL 数据库的完整流程。
- **📈 监控与告警**: 内置服务器资源监控功能（如磁盘空间），并通过飞书（Feishu）发送实时通知。
- **🔗 URL 管理**: 包含用于分割、去重和过滤 URL 列表的实用工具脚本。

## 📂 项目结构

```
.
├── bin/                      # 常用操作的快捷执行脚本
├── config/                   # 配置文件目录
│   └── config.ini.example    # 主配置文件示例
├── data/                     # 存放数据和脚本
│   ├── del_old_pcap.sh       # 删除旧 pcap 文件的远程脚本
│   └── xray_config/          # Xray 配置文件
├── logs/                     # 日志文件目录
├── requirements.txt          # Python 依赖列表
├── scripts/                  # 实用工具脚本（如域名处理）
│   ├── domain_processor.py
│   └── quick_process.py
├── src/                      # 项目源代码
│   ├── traffic2db/           # 数据入库模块
│   │   └── importdb.py
│   └── traffic_spider_bushu/ # 核心部署与控制模块
│       ├── action.py         # 主要的部署、控制动作
│       ├── pull_data.py      # 拉取远程数据
│       ├── server_info.py.example # 服务器信息配置示例
│       └── server_monitoring.py # 服务器监控
└── urls.txt.example          # 待爬取 URL 列表示例
```

## 🛠️ 安装与配置

1.  **克隆项目**
    ```bash
    git clone https://github.com/aimafan123/traffic_spider_bushu.git
    cd traffic_spider_bushu
    ```

2.  **创建虚拟环境并安装依赖**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **配置主配置文件**
    复制 `config/config.ini.example` 为 `config/config.ini`，并根据你的环境修改以下配置：
    - `[spider]`: 爬虫 Docker 镜像名称。
    - `[mysql]`: 你的 MySQL 数据库连接信息。

4.  **配置服务器信息**
    复制 `src/traffic_spider_bushu/server_info.py.example` 为 `src/traffic_spider_bushu/server_info.py`。
    在此文件中，你可以配置一个或多个待部署的远程服务器信息，包括：
    - SSH 连接信息（主机名、用户名、端口、私钥路径）。
    - 每个服务器上运行的 Docker 容器数量。
    - 代理模式 (`xray`, `tor`, `direct`) 及相关配置。
    - 爬虫行为参数（访问时长、滚动次数等）。

5.  **准备 URL 列表**
    创建 `urls.txt` 文件，并填入需要爬取的网站域名，每行一个。

## 🚀 使用说明

### 1. 部署和管理爬虫 (`action.py`)

`action.py` 是系统的核心控制脚本，用于在所有已配置的服务器上执行操作。

- **部署爬虫 (`bushu`)**:
  初始化服务器环境，上传配置文件，并创建、启动所有 Docker 容器。
  ```bash
  python -m traffic_spider_bushu.action bushu
  ```

- **启动爬虫 (`start`)**:
  启动所有已存在的 Docker 容器。
  ```bash
  python -m traffic_spider_bushu.action start
  ```

- **停止爬虫 (`stop`)**:
  停止所有正在运行的爬虫容器。
  ```bash
  python -m traffic_spider_bushu.action stop
  ```

- **删除爬虫及数据 (`del`)**:
  **警告：此操作会删除所有爬虫容器及相关数据！**
  ```bash
  python -m traffic_spider_bushu.action del
  ```

- **删除远程镜像 (`rmi`)**:
  删除服务器上的指定 Docker 镜像。
  ```bash
  python -m traffic_spider_bushu.action rmi <image_name>
  ```

- **加载本地镜像 (`load`)**:
  将本地的 Docker 镜像 `.tar` 文件上传到服务器并加载。
  ```bash
  python -m traffic_spider_bushu.action load <path_to_image.tar>
  ```

### 2. 同步数据和监控 (`pull_data.py`)

此脚本用于从所有远程服务器拉取采集到的数据，执行远程清理，检查服务器状态，并触发数据入库流程。

```bash
python -m traffic_spider_bushu.pull_data
```
*你也可以使用 `bin/pull_data.sh` 脚本，并通过 `crontab` 设置定时任务。*

### 3. 数据入库 (`importdb.py`)

此模块负责扫描本地数据目录，并将新的 pcap 文件及其元数据导入到 MySQL 数据库。通常由 `pull_data.py` 自动调用。

### 4. 域名处理 (`scripts/`)

`scripts` 目录下的脚本提供了方便的域名列表处理功能。

- **`domain_processor.py`**: 提供去重和移除特定 URL 的功能。
  ```bash
  # 从大文件中移除小文件包含的 URL
  python scripts/domain_processor.py remove -l large_file.txt -s small_file.txt -o output.txt

  # 对域名列表进行去重
  python scripts/domain_processor.py dedupe -i input.txt -o output_deduped.txt
  ```

- **`quick_process.py`**: 提供一个交互式菜单，用于快速执行“移除+去重”的组合操作。

## ⚙️ 核心依赖

- `paramiko`: 用于 SSH 连接和远程命令执行。
- `scp`: 用于在本地和远程服务器之间传输文件。
- `requests`: 用于发送飞书通知。
- `pypcaptools`: 用于解析 pcap 文件。
- `mysql-connector-python`: 用于连接和操作 MySQL 数据库。
