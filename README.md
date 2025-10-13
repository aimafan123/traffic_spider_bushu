# Traffic Spider Bushu (分布式流量爬虫部署系统) - 技术文档

## 文档信息

| 项目名称 | Traffic Spider Bushu (分布式流量爬虫部署系统) |
|---------|-------------------------------------------|
| 版本号   | v1.0.0                                   |
| 编写日期 | 2024年12月                               |
| 文档类型 | 技术文档                                  |

---

## 1. 项目概述

### 1.1 项目背景与目标

**项目背景**

随着网络安全研究和流量分析需求的不断增长，需要一个能够高效、稳定地从大量网站收集网络流量数据的分布式系统。传统的单机爬虫方案存在单点故障风险高、扩展性差、网络环境限制等问题。

**项目目标**

Traffic Spider Bushu 旨在构建一个功能强大的分布式网络流量采集系统，实现：
1. **分布式部署**: 支持在多台远程服务器上自动化部署和管理爬虫容器
2. **高可用性**: 通过容器化技术确保服务稳定性和环境一致性
3. **灵活代理**: 支持多种代理模式，适应不同网络环境
4. **数据完整性**: 提供完整的数据采集、同步、存储和分析流程
5. **智能监控**: 实时监控系统状态，及时发现和处理异常

### 1.2 核心功能说明

#### 1.2.1 分布式部署管理
- **自动化部署**: 一键部署爬虫容器到多台远程服务器
- **远程控制**: 通过SSH实现对远程服务器的统一管理
- **容器编排**: 支持在单台服务器上运行多个爬虫容器实例
- **配置同步**: 自动同步配置文件和爬虫参数到各个节点

#### 1.2.2 多代理支持
- **Direct模式**: 直连访问，适用于无网络限制环境
- **Xray代理**: 支持Trojan、VMess等协议的高性能代理
- **Tor代理**: 基于Tor网络的匿名访问
- **动态切换**: 支持根据网络环境动态选择代理模式

#### 1.2.3 数据采集与处理
- **PCAP采集**: 捕获完整的网络数据包
- **元数据记录**: 记录访问时间、URL、代理信息等元数据
- **数据同步**: 使用rsync高效同步远程数据到本地
- **数据入库**: 自动解析PCAP文件并导入MySQL数据库

### 1.3 技术栈介绍

**核心技术栈**
- **Python 3.8+**: 主要开发语言
- **Docker**: 爬虫容器化部署
- **MySQL**: 数据存储
- **Xray/Tor**: 网络代理

**核心依赖库**
```python
paramiko==3.5.0          # SSH连接和远程命令执行
scp==0.15.0              # 文件传输
requests==2.32.3         # HTTP请求
pypcaptools==2.1         # PCAP文件解析
mysql-connector-python==9.1.0  # MySQL数据库连接
aiohttp==3.10.11         # 异步HTTP客户端
```

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        控制中心 (Control Center)                  │
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │   部署管理模块    │  │   数据同步模块    │  │   监控告警模块    │  │
│  │   action.py     │  │  pull_data.py   │  │server_monitoring│  │
│  └─────────────┘  └─────────────────┘  └─────────────────┘  │
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │   配置管理模块    │  │   数据入库模块    │  │   工具脚本模块    │  │
│  │   config.ini    │  │   importdb.py   │  │    scripts/     │  │
│  └─────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ SSH/SCP
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      分布式爬虫节点集群                           │
│  ┌─────────────┐  ┌─────────────────┐  ┌─────────────────┐  │
│  │   爬虫节点 1     │  │   爬虫节点 2     │  │   爬虫节点 N     │  │
│  │ ┌─────────────┐ │  │ ┌─────────────┐ │  │ ┌─────────────┐ │  │
│  │ │Docker容器   │ │  │ │Docker容器   │ │  │ │Docker容器   │ │  │
│  │ │spider_traffic│ │  │ │spider_traffic│ │  │ │spider_traffic│ │  │
│  │ └─────────────┘ │  │ └─────────────┘ │  │ └─────────────┘ │  │
│  │ ┌─────────────┐ │  │ ┌─────────────┐ │  │ ┌─────────────┐ │  │
│  │ │  代理服务    │ │  │ │  代理服务    │ │  │ │  代理服务    │ │  │
│  │ │ Xray/Tor    │ │  │ │ Xray/Tor    │ │  │ │ Xray/Tor    │ │  │
│  │ └─────────────┘ │  │ └─────────────┘ │  │ └─────────────┘ │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 模块划分与功能说明

#### 2.2.1 控制中心模块

**部署管理模块 (action.py)**
- 负责爬虫容器的部署、启动、停止和删除
- 核心方法：`handle_server_deployment()`, `start_dockers_on_server()`, `stop_dockers_on_server()`

**数据同步模块 (pull_data.py)**
- 从远程服务器同步采集的数据到本地
- 使用rsync同步PCAP文件，清理远程服务器旧数据

**监控告警模块**
- 监控服务器状态和资源使用情况
- 通过飞书机器人发送告警通知

**数据入库模块 (importdb.py)**
- 解析PCAP文件并导入数据库
- 处理流程：扫描数据目录 → 解析文件 → 提取元数据 → 导入MySQL

---

## 3. 部署指南

### 3.1 环境要求

#### 3.1.1 硬件要求
**控制节点**
- CPU: 2核心以上
- 内存: 4GB以上
- 存储: 100GB以上可用空间

**爬虫节点**
- CPU: 1核心以上 (推荐2核心)
- 内存: 2GB以上 (推荐4GB)
- 存储: 20GB以上可用空间

#### 3.1.2 软件要求
**控制节点**
- 操作系统: Linux (Ubuntu 20.04+/CentOS 7+/Debian 10+)
- Python: 3.8+
- Git: 2.0+
- SSH客户端, rsync

**爬虫节点**
- 操作系统: Linux
- Docker: 20.10+
- SSH服务器

### 3.2 安装步骤

#### 3.2.1 控制节点安装

**步骤1: 克隆项目**
```bash
git clone https://github.com/aimafan123/traffic_spider_bushu.git
cd traffic_spider_bushu
```

**步骤2: 创建虚拟环境**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**步骤3: 安装依赖**
```bash
pip install -r requirements.txt
```

**步骤4: 创建必要目录**
```bash
mkdir -p data logs
```

#### 3.2.2 爬虫节点准备

**安装Docker**
```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# CentOS/RHEL
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
```

**配置SSH免密登录**
```bash
# 在控制节点生成SSH密钥
ssh-keygen -t ed25519 -C "traffic_spider"

# 将公钥复制到爬虫节点
ssh-copy-id -i ~/.ssh/id_ed25519.pub root@<爬虫节点IP>
```

### 3.3 配置说明

#### 3.3.1 主配置文件
```bash
cp config/config.ini.example config/config.ini
```

配置内容：
```ini
[spider]
# Docker镜像名称
image_name = aimafan/spider_traffic:v2

[mysql]
# 数据库连接信息
host = 192.168.1.100
user = root
port = 3306
password = your_password
database = traffic_data
```

#### 3.3.2 服务器信息配置
```bash
cp src/traffic_spider_bushu/server_info.py.example src/traffic_spider_bushu/server_info.py
```

配置示例：
```python
servers_info = [
    {
        "hostname": "192.168.1.101",        # 服务器IP
        "username": "root",                 # SSH用户名
        "port": 22,                        # SSH端口
        "private_key_path": "/home/user/.ssh/id_ed25519",
        "docker_num": "2",                 # Docker容器数量
        "storage_path": "/root/spider_data",
        "spider_mode": "xray",             # 代理模式
        "proxy_port": "10809",
        "time_per_website": "90",          # 每网站访问时间(秒)
        "scroll": "true",
        "scroll_num": 5,
        "webnum": 1,
        "multisite_num": 3,
        "disk": "/dev/vda1",
    }
]
```

#### 3.3.3 URL列表配置
```bash
cp urls.txt.example urls.txt
```

编辑URL列表，每行一个域名：
```
example.com
google.com
github.com
```

### 3.4 执行部署

```bash
# 部署所有爬虫节点
python -m traffic_spider_bushu.action bushu

# 检查容器状态
python -m traffic_spider_bushu.action list

# 查看日志
tail -f logs/traffic_spider_bushu.log
```

---

## 4. 接口文档

### 4.1 命令行接口 (CLI)

**主控制接口**: `action.py`

```bash
python -m traffic_spider_bushu.action <action> [options]
```

**支持的操作**:

| 操作 | 描述 | 示例 |
|------|------|------|
| bushu | 部署所有爬虫容器 | `python -m traffic_spider_bushu.action bushu` |
| start | 启动所有容器 | `python -m traffic_spider_bushu.action start` |
| stop | 停止所有容器 | `python -m traffic_spider_bushu.action stop` |
| del | 删除容器和数据 | `python -m traffic_spider_bushu.action del` |
| list | 列出服务器信息 | `python -m traffic_spider_bushu.action list` |

### 4.2 内部模块接口

#### 4.2.1 SSH连接接口

```python
def exec_command_async(client: paramiko.SSHClient, command: str):
    """在远程服务器异步执行命令"""
    pass

def upload_file_scp(scp_client: SCPClient, local_file_path: str, remote_file_path: str):
    """通过SCP上传文件到远程服务器"""
    pass
```

#### 4.2.2 配置生成接口

```python
def generate_server_config_content(server_info: dict) -> str:
    """根据服务器信息生成配置文件内容"""
    pass
```

### 4.3 错误代码说明

| 错误代码 | 描述 | 解决方案 |
|---------|------|----------|
| SSH_001 | SSH连接失败 | 检查网络连接和SSH配置 |
| SSH_002 | SSH认证失败 | 检查用户名和密钥配置 |
| DOCKER_001 | Docker容器启动失败 | 检查Docker服务状态 |
| CONFIG_001 | 配置文件格式错误 | 检查配置文件语法 |
| DB_001 | 数据库连接失败 | 检查数据库服务和连接配置 |

---

## 5. 开发规范

### 5.1 代码风格指南

#### 5.1.1 Python代码规范
- 遵循 PEP 8 Python代码风格指南
- 使用4个空格进行缩进，不使用Tab
- 行长度限制为88字符
- 使用有意义的变量名和函数名

**命名规范**
```python
# 变量和函数名：小写字母+下划线
server_info = {}
def get_server_config():
    pass

# 类名：大驼峰命名
class ServerManager:
    pass

# 常量：全大写+下划线
MAX_RETRY_COUNT = 3
```

**文档字符串规范**
```python
def deploy_spider_container(server_info: dict, container_name: str) -> bool:
    """
    在指定服务器上部署爬虫容器。
    
    Args:
        server_info (dict): 服务器配置信息
        container_name (str): 容器名称
        
    Returns:
        bool: 部署成功返回True，失败返回False
    """
    pass
```

### 5.2 分支管理策略

#### 5.2.1 Git Flow 工作流

**主要分支**
- `main`: 主分支，包含生产环境代码
- `develop`: 开发分支，包含最新开发代码
- `feature/*`: 功能分支，用于开发新功能
- `hotfix/*`: 热修复分支，用于紧急修复

**分支命名规范**
```bash
# 功能分支
feature/add-tor-proxy-support
feature/improve-error-handling

# 修复分支
hotfix/fix-ssh-connection-timeout
```

### 5.3 提交信息规范

**Conventional Commits 规范**
```
<type>[optional scope]: <description>
```

**提交类型**
- `feat`: 新功能
- `fix`: 修复bug
- `docs`: 文档更新
- `refactor`: 代码重构
- `test`: 测试相关

**示例**
```bash
git commit -m "feat(spider): 添加Tor代理支持"
git commit -m "fix(database): 修复连接池泄漏问题"
git commit -m "docs: 更新部署指南"
```

---

## 6. 测试方案

### 6.1 单元测试说明

#### 6.1.1 测试框架
- **pytest**: 主要测试框架
- **unittest.mock**: 模拟对象
- **parameterized**: 参数化测试

**测试依赖**
```python
pytest==7.4.0
pytest-cov==4.1.0          # 代码覆盖率
pytest-mock==3.11.1        # Mock支持
```

#### 6.1.2 测试目录结构
```
tests/
├── conftest.py                 # pytest配置
├── unit/                       # 单元测试
│   ├── test_action.py         # action模块测试
│   ├── test_config.py         # 配置模块测试
│   └── test_database.py       # 数据库模块测试
├── integration/                # 集成测试
│   ├── test_deployment.py     # 部署流程测试
│   └── test_data_sync.py      # 数据同步测试
└── fixtures/                   # 测试数据
```

### 6.2 集成测试流程

#### 6.2.1 测试环境准备
```yaml
# docker-compose.test.yml
version: '3.8'
services:
  mysql-test:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: test_password
      MYSQL_DATABASE: test_traffic_data
    ports:
      - "3307:3306"
```

### 6.3 性能测试指标

**系统性能指标**

| 指标类别 | 指标名称 | 目标值 |
|---------|---------|--------|
| 响应时间 | SSH连接建立时间 | < 5秒 |
| 响应时间 | 单个容器部署时间 | < 30秒 |
| 吞吐量 | 并发容器管理数量 | > 50个 |
| 资源使用 | 内存使用峰值 | < 500MB |

---

## 7. 维护手册

### 7.1 常见问题排查

#### 7.1.1 SSH连接问题

**问题**: SSH连接超时或失败
**排查步骤**:
1. 检查网络连通性: `ping <服务器IP>`
2. 检查SSH服务状态: `systemctl status ssh`
3. 验证SSH密钥: `ssh -i <私钥路径> <用户名>@<服务器IP>`
4. 检查防火墙设置

**解决方案**:
```bash
# 重启SSH服务
sudo systemctl restart ssh

# 检查SSH配置
sudo nano /etc/ssh/sshd_config

# 重新生成SSH密钥
ssh-keygen -t ed25519 -C "traffic_spider"
```

#### 7.1.2 Docker容器问题

**问题**: 容器启动失败
**排查步骤**:
1. 检查Docker服务: `systemctl status docker`
2. 查看容器日志: `docker logs <容器名>`
3. 检查镜像是否存在: `docker images`
4. 验证容器配置

**解决方案**:
```bash
# 重启Docker服务
sudo systemctl restart docker

# 清理无用容器
docker container prune

# 重新拉取镜像
docker pull aimafan/spider_traffic:v2
```

#### 7.1.3 数据库连接问题

**问题**: 数据库连接失败
**排查步骤**:
1. 检查MySQL服务状态
2. 验证连接参数
3. 检查网络连通性
4. 验证用户权限

**解决方案**:
```bash
# 检查MySQL状态
systemctl status mysql

# 测试连接
mysql -h <host> -P <port> -u <user> -p

# 重置用户权限
GRANT ALL PRIVILEGES ON *.* TO 'user'@'%';
FLUSH PRIVILEGES;
```

### 7.2 日志分析指南

#### 7.2.1 日志文件位置

**系统日志**
- 主程序日志: `logs/traffic_spider_bushu.log`
- 数据同步日志: `logs/pull_data.log`
- 数据入库日志: `logs/importdb.log`

**容器日志**
```bash
# 查看容器日志
docker logs spider_traffic_<编号>

# 实时查看日志
docker logs -f spider_traffic_<编号>
```

#### 7.2.2 日志级别说明

| 级别 | 描述 | 示例 |
|------|------|------|
| DEBUG | 调试信息 | 详细的执行步骤 |
| INFO | 一般信息 | 操作成功提示 |
| WARNING | 警告信息 | 非致命错误 |
| ERROR | 错误信息 | 操作失败 |
| CRITICAL | 严重错误 | 系统崩溃 |

#### 7.2.3 常见日志模式

**成功部署日志**
```
INFO: 开始部署服务器: 192.168.1.101
INFO: SSH连接成功
INFO: 配置文件上传完成
INFO: Docker容器创建成功: spider_traffic_1
INFO: 容器启动成功
```

**错误日志模式**
```
ERROR: SSH连接失败: 192.168.1.101, 错误: Authentication failed
ERROR: Docker容器启动失败: spider_traffic_1
ERROR: 数据库连接失败: Access denied for user
```

### 7.3 升级迁移方案

#### 7.3.1 版本升级流程

**准备阶段**
1. 备份当前配置文件
2. 备份数据库
3. 记录当前版本信息

**升级步骤**
```bash
# 1. 停止所有服务
python -m traffic_spider_bushu.action stop

# 2. 备份配置
cp -r config config_backup_$(date +%Y%m%d)

# 3. 拉取新版本
git fetch origin
git checkout v1.1.0

# 4. 更新依赖
pip install -r requirements.txt

# 5. 迁移配置
# 根据升级说明手动迁移配置文件

# 6. 重新部署
python -m traffic_spider_bushu.action bushu
```

#### 7.3.2 数据迁移

**数据库迁移**
```sql
-- 备份数据库
mysqldump -u root -p traffic_data > backup_$(date +%Y%m%d).sql

-- 创建新表结构
CREATE TABLE new_pcap_data LIKE pcap_data;

-- 迁移数据
INSERT INTO new_pcap_data SELECT * FROM pcap_data;
```

**文件迁移**
```bash
# 备份PCAP文件
rsync -av data/ data_backup_$(date +%Y%m%d)/

# 迁移到新目录结构
mkdir -p data/pcap data/json data/processed
mv data/*.pcap data/pcap/
mv data/*.json data/json/
```

#### 7.3.3 回滚方案

**快速回滚**
```bash
# 1. 停止新版本服务
python -m traffic_spider_bushu.action stop

# 2. 切换到旧版本
git checkout v1.0.0

# 3. 恢复配置
rm -rf config
mv config_backup_<date> config

# 4. 恢复数据库
mysql -u root -p traffic_data < backup_<date>.sql

# 5. 重启服务
python -m traffic_spider_bushu.action start
```

### 7.4 监控与告警

#### 7.4.1 系统监控指标

**服务器资源监控**
- CPU使用率 > 80% 告警
- 内存使用率 > 90% 告警
- 磁盘使用率 > 85% 告警
- 网络连接异常告警

**应用监控指标**
- 容器运行状态
- 数据同步成功率
- 数据库连接状态
- 爬虫任务完成率

#### 7.4.2 告警配置

**飞书告警配置**
```python
# 配置飞书Webhook
FEISHU_WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"

# 告警阈值
ALERT_THRESHOLDS = {
    "disk_usage": 85,      # 磁盘使用率告警阈值
    "memory_usage": 90,    # 内存使用率告警阈值
    "cpu_usage": 80,       # CPU使用率告警阈值
}
```

**定时监控脚本**
```bash
# 添加到crontab
# 每5分钟检查一次系统状态
*/5 * * * * /path/to/monitor_script.py

# 每小时同步一次数据
0 * * * * /path/to/pull_data.py

# 每天凌晨2点清理日志
0 2 * * * /path/to/cleanup_logs.sh
```

---

## 8. 附录

### 8.1 配置文件模板

#### 8.1.1 主配置文件模板
```ini
[spider]
image_name = aimafan/spider_traffic:v2

[mysql]
host = localhost
port = 3306
user = root
password = your_secure_password
database = traffic_data

[logging]
level = INFO
file = logs/traffic_spider_bushu.log
max_size = 100MB
backup_count = 5
```

#### 8.1.2 服务器配置模板
```python
servers_info = [
    {
        "hostname": "192.168.1.101",
        "username": "root",
        "port": 22,
        "private_key_path": "/home/user/.ssh/id_ed25519",
        "docker_num": "2",
        "storage_path": "/root/spider_data",
        "spider_mode": "xray",  # direct, xray, tor
        "proxy_port": "10809",
        "time_per_website": "90",
        "scroll": "true",
        "scroll_num": 5,
        "webnum": 1,
        "multisite_num": 3,
        "disk": "/dev/vda1",
    }
]
```

### 8.2 常用命令参考

#### 8.2.1 系统管理命令
```bash
# 查看系统状态
python -m traffic_spider_bushu.action list

# 部署所有节点
python -m traffic_spider_bushu.action bushu

# 启动所有容器
python -m traffic_spider_bushu.action start

# 停止所有容器
python -m traffic_spider_bushu.action stop

# 删除容器和数据
python -m traffic_spider_bushu.action del

# 同步数据
python -m traffic_spider_bushu.pull_data

# 数据入库
python -m traffic2db.importdb
```

#### 8.2.2 Docker管理命令
```bash
# 查看容器状态
docker ps -a

# 查看容器日志
docker logs spider_traffic_1

# 进入容器
docker exec -it spider_traffic_1 /bin/bash

# 清理无用容器
docker container prune

# 清理无用镜像
docker image prune
```

### 8.3 故障排除清单

#### 8.3.1 部署失败排查清单
- [ ] 检查SSH连接是否正常
- [ ] 验证服务器配置信息是否正确
- [ ] 确认Docker服务是否运行
- [ ] 检查镜像是否存在
- [ ] 验证网络连通性
- [ ] 检查磁盘空间是否充足
- [ ] 确认防火墙设置

#### 8.3.2 数据同步失败排查清单
- [ ] 检查rsync是否安装
- [ ] 验证SSH免密登录
- [ ] 确认远程路径是否存在
- [ ] 检查本地存储空间
- [ ] 验证文件权限设置
- [ ] 检查网络稳定性

#### 8.3.3 数据入库失败排查清单
- [ ] 检查MySQL服务状态
- [ ] 验证数据库连接参数
- [ ] 确认数据库表结构
- [ ] 检查PCAP文件完整性
- [ ] 验证用户权限
- [ ] 检查磁盘空间

---

**文档版本**: v1.0.0  
**最后更新**: 2024年12月  
**维护者**: Traffic Spider Bushu 开发团队
