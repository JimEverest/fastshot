# proxy_header_fix.py
"""
简单的代理HTTP头部解析问题修复

通过monkey patching的方式修复企业代理环境中的HeaderParsingError问题
"""

import urllib3
import logging

def apply_proxy_header_fix():
    """应用代理HTTP头部解析修复"""
    
    # 保存原始的assert_header_parsing函数
    original_assert_header_parsing = urllib3.util.response.assert_header_parsing
    
    def lenient_assert_header_parsing(headers):
        """宽松的HTTP头部解析，忽略代理服务器导致的格式问题"""
        try:
            # 尝试使用原始的严格解析
            return original_assert_header_parsing(headers)
        except urllib3.exceptions.HeaderParsingError as e:
            # 如果是MissingHeaderBodySeparatorDefect，则忽略
            if "MissingHeaderBodySeparatorDefect" in str(e):
                # 记录警告但不抛出异常
                logger = logging.getLogger("fastshot.proxy_fix")
                logger.warning(f"代理HTTP头部格式问题已忽略: {e}")
                return  # 不抛出异常，继续执行
            else:
                # 其他类型的头部解析错误仍然抛出
                raise
    
    # 替换原始函数
    urllib3.util.response.assert_header_parsing = lenient_assert_header_parsing
    
    print("✓ 已应用企代HTTP头解析修复")

# 自动应用修复
apply_proxy_header_fix()