#!/bin/bash

current_timestamp=$(date +%s)

# 使用 find 命令递归查找当前目录及所有子目录中的 .pcap 文件
find . -type f -name "*.pcap" | while read file; do
  # 从文件名中提取时间部分，格式假设为 http_YYYYMMDDHHMMSS
  timestamp_str=$(echo "$file" | grep -oP '\d{14}')

  # 如果无法提取到时间部分，跳过
  if [ -z "$timestamp_str" ]; then
    continue
  fi

  # 将时间字符串转换为时间戳
  file_timestamp=$(date -d "${timestamp_str:0:4}-${timestamp_str:4:2}-${timestamp_str:6:2} ${timestamp_str:8:2}:${timestamp_str:10:2}:${timestamp_str:12:2}" +%s)

  # 计算当前时间减去文件时间的差值
  time_diff=$((current_timestamp - file_timestamp))

  # 如果差值大于 8 小时（28800 秒），删除该文件
  if [ "$time_diff" -gt 28800 ]; then
    echo "Deleting $file"
    rm "$file"
  fi
done
