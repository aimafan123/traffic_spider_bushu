#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
域名处理工具
提供URL删除和域名去重功能的统一接口

Author: Traffic Spider Team
Version: 1.0.0
"""

import os
import sys
import argparse
import re
from collections import OrderedDict
from typing import Set, Dict, List, Tuple


class DomainProcessor:
    """域名处理器类"""
    
    def __init__(self):
        self.verbose = False
    
    def set_verbose(self, verbose: bool):
        """设置详细输出模式"""
        self.verbose = verbose
    
    def _log(self, message: str):
        """输出日志信息"""
        if self.verbose:
            print(f"[INFO] {message}")
    
    def remove_urls(self, large_file: str, small_file: str, output_file: str) -> Tuple[int, int]:
        """
        从大文件中删除小文件中包含的URL
        
        Args:
            large_file: 大的URL文件路径
            small_file: 小的URL文件路径（要删除的URL列表）
            output_file: 输出文件路径
            
        Returns:
            Tuple[int, int]: (删除的URL数量, 保留的URL数量)
        """
        if not os.path.exists(large_file):
            raise FileNotFoundError(f"文件不存在: {large_file}")
        if not os.path.exists(small_file):
            raise FileNotFoundError(f"文件不存在: {small_file}")
        
        # 读取要删除的URL列表
        self._log(f"读取要删除的URL列表: {small_file}")
        with open(small_file, 'r', encoding='utf-8') as f:
            urls_to_remove = set(line.strip() for line in f if line.strip())
        
        self._log(f"要删除的URL数量: {len(urls_to_remove)}")
        
        # 读取大文件并过滤
        removed_count = 0
        kept_count = 0
        
        self._log(f"处理文件: {large_file}")
        with open(large_file, 'r', encoding='utf-8') as infile, \
             open(output_file, 'w', encoding='utf-8') as outfile:
            
            for line in infile:
                url = line.strip()
                if url and url not in urls_to_remove:
                    outfile.write(line)
                    kept_count += 1
                elif url in urls_to_remove:
                    removed_count += 1
                    if self.verbose:
                        self._log(f"删除URL: {url}")
        
        return removed_count, kept_count
    
    def get_second_level_domain(self, domain: str) -> str:
        """
        获取真正的二级域名
        
        Args:
            domain: 原始域名
            
        Returns:
            str: 二级域名
        """
        # 移除协议前缀
        domain = re.sub(r'^https?://', '', domain)
        # 移除路径
        domain = domain.split('/')[0]
        # 移除端口
        domain = domain.split(':')[0]
        # 转换为小写
        domain = domain.lower()
        
        # 移除www前缀
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # 特殊的国家代码顶级域名（需要保留三级域名）
        special_tlds = [
            '.co.uk', '.co.jp', '.co.kr', '.co.in', '.co.za', '.co.nz', '.co.au',
            '.com.au', '.com.br', '.com.cn', '.com.mx', '.com.ar', '.com.tr',
            '.org.uk', '.net.au', '.edu.au', '.gov.au', '.asn.au',
            '.ac.uk', '.gov.uk', '.sch.uk', '.police.uk'
        ]
        
        # 检查是否包含特殊的顶级域名
        for tld in special_tlds:
            if domain.endswith(tld):
                parts = domain.split('.')
                if len(parts) >= 3:
                    return '.'.join(parts[-3:])  # 保留三级域名
                return domain
        
        # 普通域名处理 - 保留二级域名
        parts = domain.split('.')
        if len(parts) >= 2:
            return '.'.join(parts[-2:])
        
        return domain
    
    def deduplicate_domains(self, input_file: str, output_file: str) -> Tuple[int, int, List[str]]:
        """
        去重域名文件
        
        Args:
            input_file: 输入文件路径
            output_file: 输出文件路径
            
        Returns:
            Tuple[int, int, List[str]]: (原始数量, 去重后数量, 去重示例列表)
        """
        if not os.path.exists(input_file):
            raise FileNotFoundError(f"文件不存在: {input_file}")
        
        seen_domains = OrderedDict()
        total_count = 0
        duplicates_removed = []
        
        self._log(f"处理文件: {input_file}")
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                original_domain = line.strip()
                if not original_domain:
                    continue
                    
                total_count += 1
                second_level = self.get_second_level_domain(original_domain)
                
                if second_level not in seen_domains:
                    seen_domains[second_level] = original_domain
                else:
                    # 记录被去重的域名
                    existing_domain = seen_domains[second_level]
                    duplicates_removed.append(f"{original_domain} -> {existing_domain}")
                    
                    # 选择更简洁的域名（优先选择.com，然后选择更短的）
                    if (original_domain.endswith('.com') and not existing_domain.endswith('.com')) or \
                       (original_domain.endswith('.com') == existing_domain.endswith('.com') and 
                        len(original_domain) < len(existing_domain)):
                        seen_domains[second_level] = original_domain
        
        # 写入去重后的结果
        self._log(f"写入结果到: {output_file}")
        with open(output_file, 'w', encoding='utf-8') as f:
            for domain in seen_domains.values():
                f.write(domain + '\n')
        
        return total_count, len(seen_domains), duplicates_removed


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='域名处理工具 - 提供URL删除和域名去重功能',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 从urls_10000.txt中删除urls_100.txt中的URL
  python domain_processor.py remove -l urls_10000.txt -s urls_100.txt -o urls_filtered.txt
  
  # 对域名文件进行去重
  python domain_processor.py dedupe -i urls_filtered.txt -o urls_deduplicated.txt
  
  # 组合操作：先删除再去重
  python domain_processor.py remove -l urls_10000.txt -s urls_100.txt -o temp.txt
  python domain_processor.py dedupe -i temp.txt -o final.txt
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 删除URL命令
    remove_parser = subparsers.add_parser('remove', help='从大文件中删除小文件中的URL')
    remove_parser.add_argument('-l', '--large-file', required=True, help='大的URL文件路径')
    remove_parser.add_argument('-s', '--small-file', required=True, help='小的URL文件路径（要删除的URL列表）')
    remove_parser.add_argument('-o', '--output', required=True, help='输出文件路径')
    
    # 去重命令
    dedupe_parser = subparsers.add_parser('dedupe', help='对域名文件进行去重')
    dedupe_parser.add_argument('-i', '--input', required=True, help='输入文件路径')
    dedupe_parser.add_argument('-o', '--output', required=True, help='输出文件路径')
    
    # 通用参数
    parser.add_argument('-v', '--verbose', action='store_true', help='详细输出模式')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    processor = DomainProcessor()
    processor.set_verbose(args.verbose)
    
    try:
        if args.command == 'remove':
            removed_count, kept_count = processor.remove_urls(
                args.large_file, args.small_file, args.output
            )
            print(f"\n处理完成:")
            print(f"删除的URL数量: {removed_count}")
            print(f"保留的URL数量: {kept_count}")
            print(f"结果已保存到: {args.output}")
            
        elif args.command == 'dedupe':
            total_count, final_count, duplicates = processor.deduplicate_domains(
                args.input, args.output
            )
            print(f"\n处理完成:")
            print(f"原始域名数量: {total_count}")
            print(f"去重后域名数量: {final_count}")
            print(f"删除了 {total_count - final_count} 个重复的二级域名")
            print(f"结果已保存到: {args.output}")
            
            if duplicates and args.verbose:
                print("\n前10个去重示例:")
                for i, example in enumerate(duplicates[:10]):
                    print(f"{i+1}. {example}")
    
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()