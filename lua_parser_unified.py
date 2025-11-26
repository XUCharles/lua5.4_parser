#!/usr/bin/env python3
"""
统一的 Lua 字节码解析器
自动检测 Lua 字节码版本并调用相应的解析器
支持 Lua 5.1, 5.3, 5.4 和 LuaJIT 2.0/2.1

各解析器架构差异:
- Lua 5.1/5.3: Parser(data) -> parse() -> proto, 使用独立的 Dumper 类
- Lua 5.4: Parser(filename) -> parse() -> void, 使用 parser.print_proto() 方法
- LuaJIT: Parser(data) -> parse() -> (header, protos), 使用独立的 Dumper 类
"""

import sys
import os
import argparse
import json
import io
from typing import Dict, Any, Optional


def detect_lua_version(file_path: str) -> str:
    """
    检测Lua字节码文件的版本
    
    Args:
        file_path: 字节码文件路径
    
    Returns:
        str: 检测到的版本字符串
    """
    try:
        with open(file_path, 'rb') as f:
            # 读取文件头
            signature = f.read(4)
            
            if signature != b'\x1bLua' and signature[:3] != b'\x1bLJ':
                return "未知格式"
            
            version = f.read(1)[0]
            format_version = f.read(1)[0]
            
            # Lua标准版本检测
            if version == 0x51:
                return "Lua 5.1"
            elif version == 0x52:
                return "Lua 5.2" 
            elif version == 0x53:
                return "Lua 5.3"
            elif version == 0x54:
                return "Lua 5.4"
            else:
                # 可能是LuaJIT，重新检测
                f.seek(0)
                data = f.read(12)
                
                # LuaJIT 2.0 签名检测
                if len(data) >= 3 and data[:3] == b'\x1bLJ':
                    version_byte = data[3] if len(data) > 3 else 0
                    if version_byte == 1:
                        return "LuaJIT 2.0"
                    elif version_byte == 2:
                        return "LuaJIT 2.1"
                    else:
                        return f"LuaJIT (未知版本: {version_byte})"
                
                return f"未知Lua版本: 0x{version:02x}"
                
    except Exception as e:
        return f"检测失败: {e}"


def parse_and_dump(file_path: str, version) -> str:
    """
    解析并转储Lua字节码文件
    
    Args:
        file_path: 字节码文件路径
        version: 检测到的版本
        mode: 分析模式 ('text' 或 'json')
        output_format: 输出格式 ('text' 或 'json')
    
    Returns:
        str: 解析结果字符串
    """
    try:
        if version.startswith('LuaJIT'):
            # 使用LuaJIT解析器
            from luajitparse import LuaJITParser, LuaJITDumper
            with open(file_path, 'rb') as f:
                data = f.read()
            parser = LuaJITParser(data)
            header_info , protos = parser.parse()
            
            LuaJITDumper.dump_header(header_info)
            LuaJITDumper.dump_all_protos(protos)
                
        elif version == 'Lua 5.1':
            # 使用Lua 5.1解析器
            from luaparse51 import Lua51Parser, Lua51Dumper
            with open(file_path, 'rb') as f:
                data = f.read()
            parser = Lua51Parser(data)
            proto = parser.parse()
            print(f"Lua 5.1 Bytecode Analysis: {file_path}")
            print("=" * 80)
            Lua51Dumper.dump_header(parser.header_info)
            print("=" * 80)
            Lua51Dumper.dump_proto(proto)
        
        elif version == 'Lua 5.2':
            # 使用Lua 5.2解析器
            from luaparse52 import Lua52Parser, Lua52Dumper
            with open(file_path, 'rb') as f:
                data = f.read()
            parser = Lua52Parser(data)
            proto = parser.parse()
            print(Lua52Dumper.dump_header(parser))
            print(Lua52Dumper.dump_proto(proto))
                
        elif version == 'Lua 5.3':
            # 使用Lua 5.3解析器
            from luaparse53 import LuacParser, LuacDumper
            with open(file_path, 'rb') as f:
                data = f.read()
            print(f"正在解析 Lua 5.3 字节码文件: {file_path}")
            print(f"文件大小: {len(data)} 字节")
            print()
            
            parser = LuacParser(data)
            proto = parser.parse()
            
            print("主函数原型:")
            print("=" * 80)
            LuacDumper.dump_proto(proto)
            print("\n解析完成!")

        elif version == 'Lua 5.4':
            # 使用Lua 5.4解析器 - 注意：luaparse.py没有LuacDumper类
            # 所有功能都集成在LuacParser类中
            from luaparse import LuacParser
            
            parser = LuacParser(file_path)
            parser.parse()
            parser.print_proto(parser.main_proto)
            
        else:
            return f"❌ 不支持的版本: {version}"
            
    except ImportError as e:
        return f"❌ 导入解析器模块失败: {e}"
    except Exception as e:
        return f"❌ 解析失败: {e}"


def handle_lua54_special_features(args) -> bool:
    """
    处理Lua 5.4的特殊功能（加密、解密、对比）
    
    Args:
        args: 命令行参数
        
    Returns:
        bool: 如果处理了特殊功能返回True，否则返回False
    """
    from luaparse import LuacParser
    
    # 处理对比功能
    if args.compare:
        try:
            standard_file, shuffled_file = args.compare
            opcode_mapping = LuacParser.compare_opcodes(standard_file, shuffled_file)
            
            # 如果指定了输出文件，将映射结果保存到文件
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write("# OpCode 映射关系\n")
                    f.write("# 格式: 标准OpCode -> 打乱OpCode\n\n")
                    for std_opcode in sorted(opcode_mapping.keys()):
                        shuf_opcode = opcode_mapping[std_opcode]
                        f.write(f"{std_opcode} -> {shuf_opcode}\n")
                
                print(f"\n✓ 映射结果已保存到: {args.output}")
            
            return True
            
        except Exception as e:
            print(f"❌ 对比过程中发生错误: {e}")
            return True
    
    # 处理加密/解密功能
    if args.decrypt or args.encrypt:
        if not args.key:
            print("❌ 错误: 加密或解密模式需要提供密钥 (-k)")
            return True
            
        if not args.input_file:
            print("❌ 错误: 需要指定输入文件")
            return True
        
        try:
            parser = LuacParser(args.input_file)
            parser.parse()
            
            if args.decrypt:
                # 解密模式
                if not args.output:
                    # 自动生成输出文件名
                    base_name = args.input_file.rsplit('.', 1)[0]
                    args.output = f"{base_name}_decrypt.luac"
                
                # 设置解密密钥并解密
                encryption_key = args.key.encode('utf-8')
                parser.set_encryption_key(encryption_key)
                parser.decrypt_proto_code(parser.main_proto)
                
                # 写入解密后的文件
                with open(args.output, 'wb') as output_file:
                    parser._write_luac_file(output_file)
                
                print(f"✓ 解密完成，输出文件: {args.output}")
                
            elif args.encrypt:
                # 加密模式
                if not args.output:
                    # 自动生成输出文件名
                    base_name = args.input_file.rsplit('.', 1)[0]
                    args.output = f"{base_name}_encrypt.luac"
                
                # 加密并写入文件
                encryption_key = args.key.encode('utf-8')
                parser.write_encrypted_luac(args.output, encryption_key)
                
                print(f"✓ 加密完成，输出文件: {args.output}")
            
            return True
            
        except Exception as e:
            print(f"❌ 处理过程中发生错误: {e}")
            return True
    
    return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='统一的Lua字节码解析器 - 支持 Lua 5.1/5.3/5.4 和 LuaJIT 2.0/2.1',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  %(prog)s file.luac                    # 自动检测版本并解析
  %(prog)s file.luac -f json           # 输出JSON格式
  %(prog)s file.luac -v                # 仅检测版本
  %(prog)s -c std.luac shuf.luac       # 对比opcode映射（仅Lua 5.4）
  %(prog)s file.luac -d -k mykey       # 解密文件（仅Lua 5.4）
  %(prog)s file.luac -e -k mykey       # 加密文件（仅Lua 5.4）

支持的格式:
  - Lua 5.1 字节码文件
  - Lua 5.3 字节码文件  
  - Lua 5.4 字节码文件（包含加密/解密/对比功能）
  - LuaJIT 2.0/2.1 字节码文件

架构说明:
  标准架构（Lua 5.1, 5.3, LuaJIT）: Parser类 + Dumper类
  Lua 5.4 特殊架构: LuacParser类（集成解析+输出+加密+解密+对比）
        """
    )
    
    # 基本参数
    parser.add_argument('input_file', nargs='?', help='输入的字节码文件路径')
    parser.add_argument('-v', '--version-only', action='store_true', help='仅检测并显示版本信息')
    
    # Lua 5.4 特殊功能参数
    parser.add_argument('-d', '--decrypt', action='store_true', help='解密模式（仅Lua 5.4）')
    parser.add_argument('-e', '--encrypt', action='store_true', help='加密模式（仅Lua 5.4）')
    parser.add_argument('-k', '--key', help='加密/解密密钥（仅Lua 5.4）')
    parser.add_argument('-c', '--compare', nargs=2, metavar=('STANDARD_FILE', 'SHUFFLED_FILE'), 
                       help='对比两个luac文件的opcode映射关系（仅Lua 5.4）')
    
    args = parser.parse_args()
    
    # 检查参数冲突
    if args.decrypt and args.encrypt:
        print("❌ 错误: 不能同时指定加密和解密模式")
        sys.exit(1)
    
    # 处理Lua 5.4的特殊功能
    if args.compare or args.decrypt or args.encrypt:
        if handle_lua54_special_features(args):
            return
    
    # 检查输入文件
    if not args.input_file:
        print("❌ 错误: 需要指定输入文件")
        parser.print_help()
        sys.exit(1)
    
    if not os.path.exists(args.input_file):
        print(f"❌ 错误: 文件不存在: {args.input_file}")
        sys.exit(1)
    
    try:
        # 检测版本
        print("🔍 正在检测Lua字节码版本...")
        version = detect_lua_version(args.input_file)
        print(f"📋 检测结果: {version}")
        
        if args.version_only:
            return
        
        if version.startswith("未知") or version.startswith("检测失败"):
            print(f"❌ {version}")
            sys.exit(1)
        
        # 解析文件
        print(f"\n📊 正在解析文件: {args.input_file}")
        parse_and_dump(args.input_file, version)
        
        
    except KeyboardInterrupt:
        print("\n❌ 用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()