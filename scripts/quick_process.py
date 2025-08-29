#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速域名处理脚本
提供一键式的域名处理功能

Author: Traffic Spider Team
Version: 1.0.0
"""

import os
import sys
from domain_processor import DomainProcessor


def quick_remove_and_dedupe():
    """
    快速执行：从urls_10000.txt删除urls_100.txt中的URL，然后去重
    """
    processor = DomainProcessor()
    processor.set_verbose(True)
    
    # 检查必要文件是否存在
    required_files = ['urls_10000.txt', 'urls_100.txt']
    for file in required_files:
        if not os.path.exists(file):
            print(f"错误: 文件 {file} 不存在")
            print("请确保以下文件存在:")
            print("  - urls_10000.txt: 大的URL文件")
            print("  - urls_100.txt: 要删除的URL列表")
            return False
    
    try:
        print("=== 步骤1: 删除指定URL ===")
        removed_count, kept_count = processor.remove_urls(
            'urls_10000.txt', 'urls_100.txt', 'urls_filtered.txt'
        )
        print(f"删除了 {removed_count} 个URL，保留了 {kept_count} 个URL")
        
        print("\n=== 步骤2: 域名去重 ===")
        total_count, final_count, duplicates = processor.deduplicate_domains(
            'urls_filtered.txt', 'urls_final.txt'
        )
        print(f"去重前: {total_count} 个域名")
        print(f"去重后: {final_count} 个域名")
        print(f"删除了 {total_count - final_count} 个重复域名")
        
        print("\n=== 处理完成 ===")
        print("生成的文件:")
        print("  - urls_filtered.txt: 删除指定URL后的结果")
        print("  - urls_final.txt: 最终去重后的结果")
        
        return True
        
    except Exception as e:
        print(f"处理过程中出现错误: {e}")
        return False


def quick_dedupe_only():
    """
    快速执行：仅对urls_filtered.txt进行去重
    """
    processor = DomainProcessor()
    processor.set_verbose(True)
    
    input_file = 'urls_filtered.txt'
    if not os.path.exists(input_file):
        print(f"错误: 文件 {input_file} 不存在")
        return False
    
    try:
        print("=== 域名去重 ===")
        total_count, final_count, duplicates = processor.deduplicate_domains(
            input_file, 'urls_deduplicated.txt'
        )
        print(f"去重前: {total_count} 个域名")
        print(f"去重后: {final_count} 个域名")
        print(f"删除了 {total_count - final_count} 个重复域名")
        print(f"结果已保存到: urls_deduplicated.txt")
        
        return True
        
    except Exception as e:
        print(f"处理过程中出现错误: {e}")
        return False


def main():
    """主函数"""
    print("域名快速处理工具")
    print("==================")
    print("1. 完整处理 (删除URL + 去重)")
    print("2. 仅去重处理")
    print("3. 退出")
    
    while True:
        try:
            choice = input("\n请选择操作 (1-3): ").strip()
            
            if choice == '1':
                print("\n开始完整处理...")
                if quick_remove_and_dedupe():
                    print("\n✓ 完整处理成功完成！")
                else:
                    print("\n✗ 处理失败")
                break
                
            elif choice == '2':
                print("\n开始去重处理...")
                if quick_dedupe_only():
                    print("\n✓ 去重处理成功完成！")
                else:
                    print("\n✗ 处理失败")
                break
                
            elif choice == '3':
                print("退出程序")
                break
                
            else:
                print("无效选择，请输入 1-3")
                
        except KeyboardInterrupt:
            print("\n\n程序被用户中断")
            break
        except EOFError:
            print("\n\n程序结束")
            break


if __name__ == "__main__":
    # 切换到脚本所在目录的上级目录（项目根目录）
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    os.chdir(project_root)
    
    main()