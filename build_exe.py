#!/usr/bin/env python3
"""
构建脚本 - 使用 PyInstaller 将 Lua 解析器打包成可执行文件
根据各解析器的实际架构差异进行优化构建
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_dependencies():
    """检查必要的依赖"""
    print("🔍 检查依赖...")
    
    # 检查 PyInstaller
    try:
        import PyInstaller
        print(f"✅ PyInstaller 版本: {PyInstaller.__version__}")
    except ImportError:
        print("❌ 未找到 PyInstaller")
        print("💡 请运行: pip install pyinstaller")
        return False
    
    # 检查解析器文件
    required_files = [
        'lua_parser_unified.py',
        'luaparse51.py',
        'luaparse53.py', 
        'luaparse.py',
        'luajitparse.py'
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ 缺少必要文件: {', '.join(missing_files)}")
        return False
    else:
        print("✅ 所有解析器文件都存在")
    
    return True

def create_spec_file():
    """创建 PyInstaller 规格文件"""
    print("📝 创建 PyInstaller 规格文件...")
    
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

# 统一 Lua 字节码解析器 PyInstaller 规格文件
# 
# 各解析器架构说明:
# - Lua 5.1: Lua51Parser(data) -> parse() -> proto, 使用 Lua51Dumper + Lua51Analyzer
# - Lua 5.3: LuacParser(data) -> parse() -> proto, 使用 LuacDumper.dump_proto()
# - Lua 5.4: LuacParser(filename) -> parse() -> void, 使用 parser.print_proto() 方法  
# - LuaJIT: LuaJITParser(data) -> parse() -> (header, protos), 使用 LuaJITDumper
#
# 重要差异:
# 1. Lua 5.4 构造函数接收文件名而非数据
# 2. Lua 5.4 没有独立的 LuacDumper 类，直接使用 parser.print_proto()
# 3. Lua 5.1 支持分析模式 (Lua51Analyzer)
# 4. LuaJIT 返回 (header_info, protos) 元组
# 5. Lua 5.4 支持加密/解密和 opcode 对比功能

block_cipher = None

a = Analysis(
    ['lua_parser_unified.py'],
    pathex=[],
    binaries=[],
    datas=[
        # 包含所有解析器模块
        ('luaparse51.py', '.'),      # Lua 5.1: Lua51Parser + Lua51Dumper + Lua51Analyzer
        ('luaparse53.py', '.'),      # Lua 5.3: LuacParser + LuacDumper
        ('luaparse.py', '.'),        # Lua 5.4: LuacParser (特殊架构，无独立Dumper)
        ('luajitparse.py', '.'),     # LuaJIT: LuaJITParser + LuaJITDumper
    ],
    hiddenimports=[
        # 主要解析器模块
        'luaparse51',                # Lua 5.1 解析器
        'luaparse53',                # Lua 5.3 解析器
        'luaparse',                  # Lua 5.4 解析器 (特殊架构)
        'luajitparse',               # LuaJIT 解析器
        
        # 标准库模块
        'json',
        'io',
        'sys',
        'os',
        'argparse',
        'traceback',
        'datetime'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='LuaParser',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None
)
'''
    
    with open('LuaParser.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print("✅ 规格文件已创建: LuaParser.spec")

def build_executable():
    """构建可执行文件"""
    print("🔨 开始构建可执行文件...")
    
    try:
        # 使用规格文件构建
        cmd = [sys.executable, '-m', 'PyInstaller', '--clean', 'LuaParser.spec']
        
        print(f"执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ 构建成功!")
            
            # 检查输出文件
            exe_path = os.path.join('dist', 'LuaParser.exe')
            if os.path.exists(exe_path):
                size = os.path.getsize(exe_path) / (1024 * 1024)
                print(f"📦 可执行文件: {exe_path} ({size:.1f} MB)")
                return True
            else:
                print("❌ 未找到生成的可执行文件")
                return False
        else:
            print("❌ 构建失败!")
            print("错误输出:")
            print(result.stderr)
            return False
            
    except Exception as e:
        print(f"❌ 构建过程中发生错误: {e}")
        return False

def create_test_files():
    """创建测试文件"""
    print("📋 创建测试文件...")
    
    # 创建测试批处理文件
    test_bat = '''@echo off
chcp 65001 >nul
echo 🧪 测试 LuaParser.exe
echo.

if not exist "LuaParser.exe" (
    echo ❌ 错误: 未找到 LuaParser.exe
    echo 💡 请先运行构建脚本生成可执行文件
    pause
    exit /b 1
)

echo 📋 显示帮助信息:
echo ----------------------------------------
LuaParser.exe --help
echo.

echo 📝 使用示例:
echo.
echo 🔍 自动检测版本:
echo   LuaParser.exe your_file.luac
echo.
echo 📊 JSON 格式输出:
echo   LuaParser.exe your_file.luac -f json
echo.
echo 🔬 Lua 5.1 分析模式:
echo   LuaParser.exe your_file.luac -v lua51 --analyze
echo.
echo 💾 保存到文件:
echo   LuaParser.exe your_file.luac -o output.txt
echo.
echo 🛡️ Lua 5.4 特殊功能 (需要原始 luaparse.py):
echo   python luaparse.py -d your_file.luac -k password
echo   python luaparse.py -c file1.luac file2.luac
echo.

echo 💡 提示: 如果您有 Lua 字节码文件，请将文件名替换为实际路径
echo.

pause
'''
    
    with open('test_parser.bat', 'w', encoding='utf-8') as f:
        f.write(test_bat)
    
    # 创建 README
    readme = '''# Lua 字节码解析器 v2.0

## 🚀 功能特性

- 🔍 **自动版本检测**: 智能识别 Lua 5.1/5.3/5.4 和 LuaJIT 2.0/2.1 字节码
- 📊 **多种输出格式**: 支持文本和 JSON 格式输出 (LuaJIT 完整支持)
- 🔬 **深度分析**: Lua 5.1 支持全局变量、字符串常量和函数分析
- 🛡️ **加密支持**: Lua 5.4 支持加密/解密功能 (需要原始脚本)
- 📈 **对比分析**: Lua 5.4 支持 opcode 对比功能 (需要原始脚本)
- 🎯 **统一接口**: 一个程序处理所有版本的 Lua 字节码

## 📋 各版本架构详解

### Lua 5.1
- **解析架构**: `Lua51Parser(data) -> parse() -> proto`
- **输出方式**: `Lua51Dumper.dump_proto(proto)`
- **分析功能**: `Lua51Analyzer` 支持全局变量、字符串、函数分析
- **特色功能**: 
  - ✅ 分析模式 (`--analyze`)
  - ✅ 头部信息输出
  - ✅ 详细的反汇编信息

### Lua 5.3
- **解析架构**: `LuacParser(data) -> parse() -> proto`
- **输出方式**: `LuacDumper.dump_proto(proto)`
- **特色功能**:
  - ✅ 中文界面支持
  - ✅ 标准字节码反汇编
  - ✅ 头部信息自动输出

### Lua 5.4 ⭐ (特殊架构)
- **解析架构**: `LuacParser(filename) -> parse() -> void` 
- **输出方式**: `parser.print_proto(parser.main_proto)`
- **重要差异**:
  - ⚠️ 构造函数接收**文件名**而非数据
  - ⚠️ **没有独立的 LuacDumper 类**
  - ⚠️ 直接使用 `print_proto()` 方法输出
- **特色功能**:
  - 🔐 加密/解密 (`-d` + `-k password`)
  - 📊 Opcode 对比 (`-c file1 file2`)
  - 🎯 高级字节码分析

### LuaJIT 2.0/2.1
- **解析架构**: `LuaJITParser(data) -> parse() -> (header_info, protos)`
- **输出方式**: `LuaJITDumper.dump_all_protos(protos)`
- **特色功能**:
  - ✅ 完整的 JSON 导出支持
  - ✅ 多函数原型处理
  - ✅ 头部信息详细解析

## 🛠️ 使用方法

### 基本用法
```bash
# 自动检测版本并解析
LuaParser.exe game.luac

# 指定输出格式 (LuaJIT 完整支持 JSON)
LuaParser.exe game.luac -f json

# 保存到文件
LuaParser.exe game.luac -o output.txt
```

### 高级用法
```bash
# 强制指定版本
LuaParser.exe game.luac -v lua51

# Lua 5.1 深度分析模式
LuaParser.exe game.luac -v lua51 --analyze

# 显示详细帮助
LuaParser.exe --help
```

### Lua 5.4 特殊功能 (需要原始脚本)
```bash
# 解密功能
python luaparse.py -d encrypted.luac -k mypassword

# Opcode 对比
python luaparse.py -c file1.luac file2.luac
```

## 📁 支持的文件格式

- `.luac` - Lua 字节码文件
- `.out` - 编译输出文件  
- 无扩展名的字节码文件
- 加密的 Lua 字节码文件 (Lua 5.4)

## 🔍 版本检测机制

程序通过文件头部签名自动检测:
- `\\x1bLua` + 版本号 - 标准 Lua 字节码
  - `0x51` → Lua 5.1
  - `0x53` → Lua 5.3  
  - `0x54` → Lua 5.4
- `\\x1bLJ` - LuaJIT 字节码

## ⚠️ 重要注意事项

### Lua 5.4 架构特殊性
1. **构造方式不同**: 其他版本传入数据，Lua 5.4 传入文件名
2. **输出方式不同**: 其他版本使用独立 Dumper 类，Lua 5.4 直接调用方法
3. **功能更丰富**: 支持加密、解密、对比等高级功能

### JSON 输出支持
- ✅ **LuaJIT**: 完整的结构化 JSON 输出
- ⚠️ **其他版本**: 简化的 JSON 包装格式

### 分析功能
- ✅ **Lua 5.1**: 完整的分析模式 (`--analyze`)
- ❌ **其他版本**: 不支持分析模式

## 🐛 故障排除

### 常见问题
1. **"无法检测文件版本"**
   - 检查文件是否为有效的 Lua 字节码
   - 尝试使用 `-v` 参数手动指定版本

2. **"缺少必要的解析器模块"**
   - 确保所有 `.py` 文件都在同一目录
   - 重新下载完整的解析器包

3. **"Lua 5.4 解析错误"**
   - 确认文件路径正确 (Lua 5.4 需要文件名)
   - 检查文件权限

### 调试模式
```bash
# 查看详细错误信息
LuaParser.exe problematic_file.luac -v lua54
```

## 📊 性能对比

| 版本 | 解析速度 | 内存占用 | JSON支持 | 分析功能 |
|------|----------|----------|----------|----------|
| Lua 5.1 | ⭐⭐⭐ | ⭐⭐⭐ | 简化 | ✅ 完整 |
| Lua 5.3 | ⭐⭐⭐⭐ | ⭐⭐⭐ | 简化 | ❌ |
| Lua 5.4 | ⭐⭐⭐⭐⭐ | ⭐⭐ | 简化 | 🔐 加密 |
| LuaJIT | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ✅ 完整 | ❌ |

## 🔗 技术细节

### 架构设计
- **统一接口**: 所有版本通过统一的命令行接口访问
- **自动适配**: 根据检测到的版本自动选择合适的解析器
- **输出重定向**: 统一捕获各解析器的输出并格式化

### 依赖关系
- Python 3.6+
- 各版本解析器模块 (luaparse*.py)
- 标准库: json, io, sys, os, argparse

---
🏗️ 构建时间: {build_time}
📧 技术支持: 如遇问题请检查文件格式和版本兼容性
'''
    
    import datetime
    build_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open('README.txt', 'w', encoding='utf-8') as f:
        f.write(readme.format(build_time=build_time))
    
    print("✅ 测试文件已创建:")
    print("   - test_parser.bat (测试脚本)")
    print("   - README.txt (详细使用说明)")

def cleanup():
    """清理临时文件"""
    print("🧹 清理临时文件...")
    
    # 删除构建目录
    if os.path.exists('build'):
        shutil.rmtree('build')
        print("✅ 已删除 build 目录")
    
    # 删除规格文件
    if os.path.exists('LuaParser.spec'):
        os.remove('LuaParser.spec')
        print("✅ 已删除规格文件")

def main():
    """主函数"""
    print("🚀 Lua 解析器构建脚本 v2.0")
    print("=" * 60)
    print("📋 支持版本: Lua 5.1/5.3/5.4, LuaJIT 2.0/2.1")
    print("🎯 特别优化: Lua 5.4 特殊架构适配")
    print("=" * 60)
    
    # 检查依赖
    if not check_dependencies():
        print("\n❌ 依赖检查失败，请解决上述问题后重试")
        sys.exit(1)
    
    print()
    
    # 创建规格文件
    create_spec_file()
    print()
    
    # 构建可执行文件
    if not build_executable():
        print("\n❌ 构建失败")
        sys.exit(1)
    
    print()
    
    # 创建测试文件
    create_test_files()
    print()
    
    # 清理临时文件
    cleanup()
    
    print("\n🎉 构建完成!")
    print("📦 输出目录: dist/")
    print("🧪 运行 test_parser.bat 进行测试")
    print("📖 查看 README.txt 了解详细使用方法")
    print("\n💡 提示:")
    print("   - 统一解析器已适配各版本架构差异")
    print("   - Lua 5.4 特殊架构已正确处理")
    print("   - 支持自动版本检测和手动指定")

if __name__ == '__main__':
    main()