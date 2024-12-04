# 自动部署流量采集程序

可以实现流量采集程序的自动部署，可以一次性在服务器上开启多个docker采集流量

docker代码项目路径 [https://github.com/ZGC-BUPT-aimafan/spider_traffic.git]()

## 部署步骤

**注意1：需事先在服务器上安装docker并配置公私钥**

**注意2：如果是非root用户登录服务器，需要手动在服务器上执行`ethtool -K docker0 tso off gso off gro off`**

1. 安装依赖库
```
pip install -r requirments.txt
```
2. 将xray客户端配置文件放到`data/xray_config/`目录中
3. 将需要采集的网站写入到项目目录的`urls.txt`文件中
4. 将docker镜像文件放在`data/spider_traffic.tar`，以便等会儿上传到服务器
5. 修改`config/config.ini`，将镜像名称修改为当前使用的镜像名称
6. 将服务器信息填到`src/traffic_spider_bushu/server_info.py.example`，并将文件名称改为`server_info.py`
7. 在`src`目录，执行
```
python -m traffic_spider_bushu.action
```
程序自动执行，部署结束


## 服务器部署指令

部署过程将在服务器上依次执行以下指令，如果不需要某些指令，可手动在代码中注释

```bash
scp -r data/spider_traffic.tar {username}@{host_name}:~/
scp -r data/xray_config/{xray_name} {username}@{host_name}:~/

ethtool -K docker0 tso off gso off gro off  #如果非root用户，该指令不会成功

docker load -i {remote_image_path}

mkdir -p {storage_path}/{container_name}/config # container_name 定义为spider_traffic_i，i是docker序号，从0开始

echo {config_content} > {config_dir}/config.ini # 写入配置文件，配置文件的内容在代码中定义
echo {url_parts[i]} > {config_dir}/current_docker_url_list.txt  # 将要访问的url写入文件，该docker要访问的url为全部url的1/n份，其中n为开启的docker的数量
echo {get_exclude_content()} > {config_dir}/exclude_keywords    # 将要排除的内容写入文件，排除的内容在代码中定义

docker stop {container_name}
docker rm {container_name}

docker run -v {storage_path}/{container_name}/data:/app/data -v {config_dir}:/app/config -v {storage_path}/{container_name}/logs:/app/logs --privileged -itd --name {container_name} {image_name} /bin/bash

docker exec  {container_name} ethtool -K eth0 tso off gso off gro off lro off   # docker内关闭合并包

docker cp {remote_xray_path} {container_name}:/app/config

nohup docker exec {container_name} bash action.sh > {storage_path}/{container_name+'.log'} 2>&1 &   # 后台执行采集指令，并输出日志
```

## 服务器监控程序
可以运行 `bash bin/server_monitoring.sh` 检测服务器运行
> 对应执行的程序 src/traffic_spider_bushu/server_monitoring.py 中调用了wechat_bot_aimafan库，该库为私有库，运行时需要将导入和对应引用去掉