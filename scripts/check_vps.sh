#!/bin/bash

# 1. 之前的数组定义
SERVERS=(
    "vultr24de" "vultr25de" "vultr20us" "vultr21us"
    "vultr22jp" "vultr23jp" "vultr10de" "vultr11de"
    "vultr6us"  "vultr7us"  "vultr8jp"  "vultr9jp"
)

for ip in "${SERVERS[@]}"; do
    ssh  -o ConnectTimeout=3 root@$ip "echo '$ip 登录成功'"
done