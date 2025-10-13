#!/bin/bash

current_timestamp=$(date +%s)

find . -type f -name "*.pcap" -print0 |
while IFS= read -r -d '' pcap_file; do
  # 提取时间戳
  timestamp_str=$(echo "$pcap_file" | grep -oE '[0-9]{14}')
  [ -z "$timestamp_str" ] && continue

  if [[ "$OSTYPE" == "darwin"* ]]; then
    file_timestamp=$(date -j -f "%Y%m%d%H%M%S" "$timestamp_str" +%s)
  else
    file_timestamp=$(date -d "${timestamp_str:0:4}-${timestamp_str:4:2}-${timestamp_str:6:2} ${timestamp_str:8:2}:${timestamp_str:10:2}:${timestamp_str:12:2}" +%s)
  fi

  time_diff=$((current_timestamp - file_timestamp))

  if [ "$time_diff" -gt 28800 ]; then
    base="${pcap_file%.pcap}"
    for ext in pcap json log; do
      f="${base}.${ext}"
      if [ -f "$f" ]; then
        echo "Deleting $f"
        rm -f -- "$f"
      fi
    done
  fi
done
