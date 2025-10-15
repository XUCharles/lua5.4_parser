#!/usr/bin/env python3
"""
Lua 5.3 Bytecode Parser
解析 luac 5.3 版本的字节码文件
"""

import struct
import sys
from enum import IntEnum
from dataclasses import dataclass
from typing import List, Optional, Union, BinaryIO

# Lua 5.3 常量
LUA_SIGNATURE = b"\x1bLua"
LUAC_VERSION = 0x53
LUAC_FORMAT = 0
LUAC_DATA = b"\x19\x93\r\n\x1a\n"
SIZEOF_INT = 4
SIZEOF_SIZET = 8
SIZEOF_INSTRUCTION = 4
SIZEOF_LUA_INTEGER = 8
SIZEOF_LUA_NUMBER = 8

# Lua 值类型
class LuaType(IntEnum):
    TNIL = 0
    TBOOLEAN = 1
    TLIGHTUSERDATA = 2
    TNUMBER = 3
    TSTRING = 4
    TTABLE = 5
    TFUNCTION = 6
    TUSERDATA = 7
    TTHREAD = 8
    TNUMFLT = 3 | (0 << 4)  # float
    TNUMINT = 3 | (1 << 4)  # integer
    TSHRSTR = 4 | (0 << 4)  # short string
    TLNGSTR = 4 | (1 << 4)  # long string

# Lua 操作码
class OpCode(IntEnum):
    OP_MOVE = 0
    OP_LOADK = 1
    OP_LOADKX = 2
    OP_LOADBOOL = 3
    OP_LOADNIL = 4
    OP_GETUPVAL = 5
    OP_GETTABUP = 6
    OP_GETTABLE = 7
    OP_SETTABUP = 8
    OP_SETUPVAL = 9
    OP_SETTABLE = 10
    OP_NEWTABLE = 11
    OP_SELF = 12
    OP_ADD = 13
    OP_SUB = 14
    OP_MUL = 15
    OP_MOD = 16
    OP_POW = 17
    OP_DIV = 18
    OP_IDIV = 19
    OP_BAND = 20
    OP_BOR = 21
    OP_BXOR = 22
    OP_SHL = 23
    OP_SHR = 24
    OP_UNM = 25
    OP_BNOT = 26
    OP_NOT = 27
    OP_LEN = 28
    OP_CONCAT = 29
    OP_JMP = 30
    OP_EQ = 31
    OP_LT = 32
    OP_LE = 33
    OP_TEST = 34
    OP_TESTSET = 35
    OP_CALL = 36
    OP_TAILCALL = 37
    OP_RETURN = 38
    OP_FORLOOP = 39
    OP_FORPREP = 40
    OP_TFORCALL = 41
    OP_TFORLOOP = 42
    OP_SETLIST = 43
    OP_CLOSURE = 44
    OP_VARARG = 45
    OP_EXTRAARG = 46

@dataclass
class Instruction:
    """Lua 指令"""
    opcode: OpCode
    a: int
    b: int
    c: int
    bx: int
    sbx: int
    ax: int
    raw: int

    def __str__(self):
        return f"{self.opcode.name:<12} A={self.a} B={self.b} C={self.c}"

@dataclass
class LocalVar:
    """局部变量"""
    varname: str
    startpc: int
    endpc: int

@dataclass
class Upvalue:
    """上值"""
    instack: int
    idx: int
    name: str = ""

@dataclass
class Proto:
    """Lua 函数原型"""
    source: str = ""
    line_defined: int = 0
    last_line_defined: int = 0
    num_params: int = 0
    is_vararg: int = 0
    max_stack_size: int = 0
    
    code: List[Instruction] = None
    constants: List = None
    upvalues: List[Upvalue] = None
    protos: List['Proto'] = None
    debug_info: dict = None
    
    def __post_init__(self):
        if self.code is None:
            self.code = []
        if self.constants is None:
            self.constants = []
        if self.upvalues is None:
            self.upvalues = []
        if self.protos is None:
            self.protos = []
        if self.debug_info is None:
            self.debug_info = {
                'lineinfo': [],
                'locvars': [],
                'upvalues': []
            }

class LuacParser:
    """Lua 5.3 字节码解析器"""
    
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.endianness = '<'  # 小端
        self.header_info = {} # 存储头部信息
        
    def read(self, size: int) -> bytes:
        """读取指定字节数"""
        if self.pos + size > len(self.data):
            raise Exception(f"读取越界: pos={self.pos}, size={size}, total={len(self.data)}")
        result = self.data[self.pos:self.pos + size]
        self.pos += size
        return result
    
    def read_byte(self) -> int:
        """读取一个字节"""
        return self.read(1)[0]
    
    def read_int(self) -> int:
        """读取整数"""
        return struct.unpack(self.endianness + 'i', self.read(SIZEOF_INT))[0]
    
    def read_size_t(self) -> int:
        """读取 size_t"""
        return struct.unpack(self.endianness + 'Q', self.read(SIZEOF_SIZET))[0]
    
    def read_lua_integer(self) -> int:
        """读取 Lua 整数"""
        return struct.unpack(self.endianness + 'q', self.read(SIZEOF_LUA_INTEGER))[0]
    
    def read_lua_number(self) -> float:
        """读取 Lua 浮点数"""
        return struct.unpack(self.endianness + 'd', self.read(SIZEOF_LUA_NUMBER))[0]
    
    def read_string(self) -> str:
        """读取字符串"""
        size = self.read_byte()
        if size == 0xFF:  # 长字符串
            size = self.read_size_t()
        if size == 0:
            return ""
        # Lua 5.3 字符串长度包含结尾的 \0
        data = self.read(size - 1)
        return data.decode('utf-8', errors='replace')
    
    def read_instruction(self) -> Instruction:
        """读取指令"""
        raw = struct.unpack(self.endianness + 'I', self.read(SIZEOF_INSTRUCTION))[0]
        
        # 解码指令字段
        opcode = OpCode(raw & 0x3F)
        a = (raw >> 6) & 0xFF
        c = (raw >> 14) & 0x1FF
        b = (raw >> 23) & 0x1FF
        bx = (raw >> 14) & 0x3FFFF
        sbx = bx - 131071  # 2^17-1
        ax = (raw >> 6) & 0x3FFFFFF
        
        return Instruction(opcode, a, b, c, bx, sbx, ax, raw)
    
    def read_constants(self) -> List:
        """读取常量表"""
        n = self.read_int()
        constants = []
        
        for _ in range(n):
            tag = self.read_byte()
            
            if tag == LuaType.TNIL:
                constants.append(None)
            elif tag == LuaType.TBOOLEAN:
                constants.append(bool(self.read_byte()))
            elif tag == LuaType.TNUMFLT:
                constants.append(self.read_lua_number())
            elif tag == LuaType.TNUMINT:
                constants.append(self.read_lua_integer())
            elif tag == LuaType.TSHRSTR or tag == LuaType.TLNGSTR:
                constants.append(self.read_string())
            else:
                raise Exception(f"未知的常量类型: {tag}")
        
        return constants
    
    def read_upvalues(self) -> List[Upvalue]:
        """读取上值信息"""
        n = self.read_int()
        upvalues = []
        
        for _ in range(n):
            instack = self.read_byte()
            idx = self.read_byte()
            upvalues.append(Upvalue(instack, idx))
        
        return upvalues
    
    def read_protos(self) -> List[Proto]:
        """读取子函数原型"""
        n = self.read_int()
        protos = []
        
        for _ in range(n):
            protos.append(self.read_proto())
        
        return protos
    
    def read_debug(self, proto: Proto):
        """读取调试信息"""
        # 行号信息
        n = self.read_int()
        proto.debug_info['lineinfo'] = [self.read_int() for _ in range(n)]
        
        # 局部变量
        n = self.read_int()
        for _ in range(n):
            varname = self.read_string()
            startpc = self.read_int()
            endpc = self.read_int()
            proto.debug_info['locvars'].append(LocalVar(varname, startpc, endpc))
        
        # 上值名称
        n = self.read_int()
        for i in range(n):
            name = self.read_string()
            proto.debug_info['upvalues'].append(name)
            if i < len(proto.upvalues):
                proto.upvalues[i].name = name
    
    def read_proto(self) -> Proto:
        """读取函数原型"""
        proto = Proto()
        
        # 基本信息
        proto.source = self.read_string()
        proto.line_defined = self.read_int()
        proto.last_line_defined = self.read_int()
        proto.num_params = self.read_byte()
        proto.is_vararg = self.read_byte()
        proto.max_stack_size = self.read_byte()
        
        # 指令
        n = self.read_int()
        proto.code = [self.read_instruction() for _ in range(n)]
        
        # 常量
        proto.constants = self.read_constants()
        
        # 上值
        proto.upvalues = self.read_upvalues()
        
        # 子函数
        proto.protos = self.read_protos()
        
        # 调试信息
        self.read_debug(proto)
        
        return proto
    
    def check_header(self):
        """检查文件头并收集头部信息"""
        print("=" * 80)
        print("Lua 5.3 字节码文件头部信息")
        print("=" * 80)
        
        # 签名
        signature = self.read(4)
        print(f"签名 (Signature):        {signature} ({signature.hex()})")
        if signature != LUA_SIGNATURE:
            raise Exception(f"无效的 Lua 签名: {signature}")
        
        # 版本
        version = self.read_byte()
        print(f"版本 (Version):          0x{version:02X} (Lua {version >> 4}.{version & 0xF})")
        if version != LUAC_VERSION:
            raise Exception(f"不支持的 Lua 版本: {version:#x}")
        
        # 格式
        format_val = self.read_byte()
        print(f"格式 (Format):           {format_val} ({'官方格式' if format_val == 0 else '非官方格式'})")
        if format_val != LUAC_FORMAT:
            raise Exception(f"无效的格式: {format_val}")
        
        # 数据校验
        luac_data = self.read(6)
        print(f"数据校验 (LUAC_DATA):    {luac_data.hex()}")
        if luac_data != LUAC_DATA:
            raise Exception(f"损坏的字节码")
        
        # 大小信息
        int_size = self.read_byte()
        sizet_size = self.read_byte()
        instruction_size = self.read_byte()
        lua_integer_size = self.read_byte()
        lua_number_size = self.read_byte()
        
        print(f"int 大小:               {int_size} 字节")
        print(f"size_t 大小:            {sizet_size} 字节")
        print(f"指令大小:               {instruction_size} 字节")
        print(f"Lua 整数大小:           {lua_integer_size} 字节")
        print(f"Lua 浮点数大小:         {lua_number_size} 字节")
        
        # 测试整数和浮点数
        test_int = self.read_lua_integer()
        test_num = self.read_lua_number()
        
        print(f"测试整数:               {test_int} (0x{test_int:X})")
        print(f"测试浮点数:             {test_num}")
        
        if test_int != 0x5678:
            raise Exception("整数格式不匹配")
        if test_num != 370.5:
            raise Exception("浮点数格式不匹配")
        
        # 上值数量
        upvalue_count = self.read_byte()
        print(f"主函数上值数量:         {upvalue_count}")
        
        # 存储头部信息
        self.header_info = {
            'signature': signature,
            'version': version,
            'format': format_val,
            'luac_data': luac_data,
            'int_size': int_size,
            'sizet_size': sizet_size,
            'instruction_size': instruction_size,
            'lua_integer_size': lua_integer_size,
            'lua_number_size': lua_number_size,
            'test_int': test_int,
            'test_num': test_num,
            'upvalue_count': upvalue_count
        }
        
        print("=" * 80)
        print()
    
    def parse(self) -> Proto:
        """解析 luac 文件"""
        self.check_header()
        return self.read_proto()

class LuacDumper:
    """Lua 字节码输出器"""
    
    @staticmethod
    def dump_proto(proto: Proto, indent: int = 0):
        """输出函数原型信息"""
        prefix = "  " * indent
        
        print(f"{prefix}┌─ 函数信息 ─────────────────────────────────────────────")
        print(f"{prefix}│ 源文件:     {proto.source}")
        print(f"{prefix}│ 定义行号:   {proto.line_defined} - {proto.last_line_defined}")
        print(f"{prefix}│ 参数数量:   {proto.num_params}")
        print(f"{prefix}│ 可变参数:   {'是' if proto.is_vararg else '否'}")
        print(f"{prefix}│ 最大栈大小: {proto.max_stack_size}")
        print(f"{prefix}│ 指令数量:   {len(proto.code)}")
        print(f"{prefix}│ 常量数量:   {len(proto.constants)}")
        print(f"{prefix}│ 上值数量:   {len(proto.upvalues)}")
        print(f"{prefix}│ 局部变量:   {len(proto.debug_info['locvars'])}")
        print(f"{prefix}│ 子函数数量: {len(proto.protos)}")
        print(f"{prefix}└─────────────────────────────────────────────────────")
        print()
        
        # 常量表
        if proto.constants:
            print(f"{prefix}┌─ 常量表 ({len(proto.constants)} 个) ─────────────────────────────────")
            for i, const in enumerate(proto.constants):
                if isinstance(const, str):
                    const_repr = f'"{const}"'
                    const_type = "字符串"
                elif isinstance(const, bool):
                    const_repr = str(const).lower()
                    const_type = "布尔值"
                elif isinstance(const, int):
                    const_repr = str(const)
                    const_type = "整数"
                elif isinstance(const, float):
                    const_repr = str(const)
                    const_type = "浮点数"
                elif const is None:
                    const_repr = "nil"
                    const_type = "空值"
                else:
                    const_repr = str(const)
                    const_type = "未知"
                
                print(f"{prefix}│ [{i:3d}] {const_type:<8} {const_repr}")
            print(f"{prefix}└─────────────────────────────────────────────────────")
            print()
        
        # 指令表
        if proto.code:
            print(f"{prefix}┌─ 指令表 ({len(proto.code)} 条指令) ─────────────────────────────")
            for i, inst in enumerate(proto.code):
                line = proto.debug_info['lineinfo'][i] if i < len(proto.debug_info['lineinfo']) else 0
                
                # 格式化指令参数
                if inst.opcode.name in ['LOADK', 'LOADKX']:
                    param_info = f"A={inst.a} Bx={inst.bx}"
                elif inst.opcode.name in ['JMP', 'FORLOOP', 'FORPREP']:
                    param_info = f"A={inst.a} sBx={inst.sbx}"
                elif inst.opcode.name == 'CLOSURE':
                    param_info = f"A={inst.a} Bx={inst.bx}"
                else:
                    param_info = f"A={inst.a} B={inst.b} C={inst.c}"
                
                print(f"{prefix}│ [{i+1:3d}] {inst.opcode.name:<12} {param_info:<20} ; 行号 {line}")
            print(f"{prefix}└─────────────────────────────────────────────────────")
            print()
        
        # 上值信息
        if proto.upvalues:
            print(f"{prefix}┌─ 上值信息 ({len(proto.upvalues)} 个) ─────────────────────────────")
            for i, upval in enumerate(proto.upvalues):
                stack_info = "栈内" if upval.instack else "外部"
                print(f"{prefix}│ [{i:3d}] {upval.name:<15} 索引={upval.idx:3d} 位置={stack_info}")
            print(f"{prefix}└─────────────────────────────────────────────────────")
            print()
        
        # 局部变量
        if proto.debug_info['locvars']:
            print(f"{prefix}┌─ 局部变量 ({len(proto.debug_info['locvars'])} 个) ─────────────────────────")
            for i, var in enumerate(proto.debug_info['locvars']):
                print(f"{prefix}│ [{i:3d}] {var.varname:<15} 作用域=[{var.startpc+1:3d}-{var.endpc+1:3d}]")
            print(f"{prefix}└─────────────────────────────────────────────────────")
            print()
        
        # 子函数
        if proto.protos:
            print(f"{prefix}┌─ 子函数 ({len(proto.protos)} 个) ─────────────────────────────────")
            for i, subproto in enumerate(proto.protos):
                print(f"{prefix}│")
                print(f"{prefix}│ 子函数 #{i+1}:")
                print(f"{prefix}│")
                LuacDumper.dump_proto(subproto, indent + 1)
            print(f"{prefix}└─────────────────────────────────────────────────────")



def main():
    """主函数"""
    if len(sys.argv) < 2:
        print(f"使用方法: {sys.argv[0]} <luac文件>")
        sys.exit(1)
    
    filename = sys.argv[1]
    
    try:
        with open(filename, 'rb') as f:
            data = f.read()
        
        print(f"正在解析 Lua 5.3 字节码文件: {filename}")
        print(f"文件大小: {len(data)} 字节")
        print()
        
        parser = LuacParser(data)
        proto = parser.parse()
        
        print("主函数原型:")
        print("=" * 80)
        LuacDumper.dump_proto(proto)
        
        print("\n解析完成!")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
