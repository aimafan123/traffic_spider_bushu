# 自动部署流量采集程序

Traffic Spider 部署工具是一个 Python 脚本，旨在远程部署和管理多个服务器上的网络爬虫容器。本工具支持通过 SSH 连接到远程服务器，执行命令、上传文件、管理 Docker 容器，并根据配置自动启动爬虫任务。

docker代码项目路径 [spider_traffic.git](https://github.com/ZGC-BUPT-aimafan/spider_traffic.git)

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
5. 将服务器信息填到`src/traffic_spider_bushu/server_info.py.example`，并按照注释填写爬虫具体情况，将文件名称改为`server_info.py`
6. 在`src`目录，执行
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



## 服务器监控程序
可以运行 `bash bin/server_monitoring.sh` 检测服务器运行
> 对应执行的程序 src/traffic_spider_bushu/server_monitoring.py 中调用了wechat_bot_aimafan库，该库为私有库，运行时需要将导入和对应引用去掉