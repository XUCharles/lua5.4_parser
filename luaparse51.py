#!/usr/bin/env python3
"""
Lua 5.1 Bytecode Parser
解析 luac 5.1 版本的字节码文件
"""

import struct
import sys
from enum import IntEnum
from dataclasses import dataclass
from typing import List, Optional, Union, BinaryIO

# Lua 5.1 常量
LUA_SIGNATURE = b"\x1bLua"
LUAC_VERSION = 0x51
LUAC_FORMAT = 0
LUAC_HEADERSIZE = 12

# Lua 5.1 数据类型
class LuaType(IntEnum):
    LUA_TNIL = 0
    LUA_TBOOLEAN = 1
    LUA_TLIGHTUSERDATA = 2
    LUA_TNUMBER = 3
    LUA_TSTRING = 4
    LUA_TTABLE = 5
    LUA_TFUNCTION = 6
    LUA_TUSERDATA = 7
    LUA_TTHREAD = 8

# Lua 5.1 操作码
class OpCode(IntEnum):
    OP_MOVE = 0
    OP_LOADK = 1
    OP_LOADBOOL = 2
    OP_LOADNIL = 3
    OP_GETUPVAL = 4
    OP_GETGLOBAL = 5
    OP_GETTABLE = 6
    OP_SETGLOBAL = 7
    OP_SETUPVAL = 8
    OP_SETTABLE = 9
    OP_NEWTABLE = 10
    OP_SELF = 11
    OP_ADD = 12
    OP_SUB = 13
    OP_MUL = 14
    OP_DIV = 15
    OP_MOD = 16
    OP_POW = 17
    OP_UNM = 18
    OP_NOT = 19
    OP_LEN = 20
    OP_CONCAT = 21
    OP_JMP = 22
    OP_EQ = 23
    OP_LT = 24
    OP_LE = 25
    OP_TEST = 26
    OP_TESTSET = 27
    OP_CALL = 28
    OP_TAILCALL = 29
    OP_RETURN = 30
    OP_FORLOOP = 31
    OP_FORPREP = 32
    OP_TFORLOOP = 33
    OP_SETLIST = 34
    OP_CLOSE = 35
    OP_CLOSURE = 36
    OP_VARARG = 37

@dataclass
class Instruction:
    """Lua 5.1 指令"""
    opcode: OpCode
    a: int
    b: int
    c: int
    bx: int
    sbx: int
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
    """上值 (Lua 5.1 中只有名称)"""
    name: str

@dataclass
class Proto:
    """Lua 5.1 函数原型"""
    source: str = ""
    line_defined: int = 0
    last_line_defined: int = 0
    nups: int = 0  # number of upvalues
    num_params: int = 0
    is_vararg: int = 0
    max_stack_size: int = 0
    
    code: List[Instruction] = None
    constants: List = None
    protos: List['Proto'] = None
    debug_info: dict = None
    
    def __post_init__(self):
        if self.code is None:
            self.code = []
        if self.constants is None:
            self.constants = []
        if self.protos is None:
            self.protos = []
        if self.debug_info is None:
            self.debug_info = {
                'lineinfo': [],
                'locvars': [],
                'upvalues': []
            }

class Lua51Parser:
    """Lua 5.1 字节码解析器"""
    
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0
        self.endianness = '<'  # 小端
        self.int_size = 4
        self.sizet_size = 4
        self.instruction_size = 4
        self.number_size = 8
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
        return struct.unpack(self.endianness + 'i', self.read(self.int_size))[0]
    
    def read_size_t(self) -> int:
        """读取 size_t"""
        if self.sizet_size == 4:
            return struct.unpack(self.endianness + 'I', self.read(4))[0]
        else:
            return struct.unpack(self.endianness + 'Q', self.read(8))[0]
    
    def read_number(self) -> float:
        """读取 Lua number"""
        return struct.unpack(self.endianness + 'd', self.read(self.number_size))[0]
    
    def read_string(self) -> str:
        """读取字符串 (Lua 5.1 格式)"""
        # Lua 5.1 使用 size_t 存储字符串长度
        size = self.read_size_t()
        if size == 0:
            return ""
        # Lua 5.1 字符串包含结尾的 \0
        data = self.read(size)
        return data[:-1].decode('utf-8', errors='replace')
    
    def read_instruction(self) -> Instruction:
        """读取指令"""
        raw = struct.unpack(self.endianness + 'I', self.read(self.instruction_size))[0]
        
        # 解码指令字段 (Lua 5.1 格式)
        opcode = OpCode(raw & 0x3F)
        a = (raw >> 6) & 0xFF
        c = (raw >> 14) & 0x1FF
        b = (raw >> 23) & 0x1FF
        bx = (raw >> 14) & 0x3FFFF
        sbx = bx - 131071  # 2^17-1
        
        return Instruction(opcode, a, b, c, bx, sbx, raw)
    
    def read_constants(self) -> List:
        """读取常量表"""
        n = self.read_int()
        constants = []
        
        for _ in range(n):
            t = self.read_byte()
            
            if t == LuaType.LUA_TNIL:
                constants.append(None)
            elif t == LuaType.LUA_TBOOLEAN:
                constants.append(bool(self.read_byte()))
            elif t == LuaType.LUA_TNUMBER:
                constants.append(self.read_number())
            elif t == LuaType.LUA_TSTRING:
                constants.append(self.read_string())
            else:
                raise Exception(f"未知的常量类型: {t}")
        
        return constants
    
    def read_code(self) -> List[Instruction]:
        """读取指令列表"""
        n = self.read_int()
        return [self.read_instruction() for _ in range(n)]
    
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
        for _ in range(n):
            name = self.read_string()
            proto.debug_info['upvalues'].append(Upvalue(name))
    
    def read_proto(self) -> Proto:
        """读取函数原型"""
        proto = Proto()
        
        # 函数头信息
        proto.source = self.read_string()
        proto.line_defined = self.read_int()
        proto.last_line_defined = self.read_int()
        proto.nups = self.read_byte()
        proto.num_params = self.read_byte()
        proto.is_vararg = self.read_byte()
        proto.max_stack_size = self.read_byte()
        
        # 指令
        proto.code = self.read_code()
        
        # 常量
        proto.constants = self.read_constants()
        
        # 子函数
        proto.protos = self.read_protos()
        
        # 调试信息
        self.read_debug(proto)
        
        return proto
    
    def check_header(self):
        """检查文件头"""
        # 签名
        signature = self.read(4)
        if signature != LUA_SIGNATURE:
            raise Exception(f"无效的 Lua 签名: {signature}")
        
        # 版本
        version = self.read_byte()
        if version != LUAC_VERSION:
            raise Exception(f"不支持的 Lua 版本: {version:#x} (需要 5.1)")
        
        # 格式
        format = self.read_byte()
        if format != LUAC_FORMAT:
            raise Exception(f"无效的格式: {format}")
        
        # 大小端标记
        endian = self.read_byte()
        if endian == 1:
            self.endianness = '<'  # 小端
        else:
            self.endianness = '>'  # 大端
        
        # 各种大小
        self.int_size = self.read_byte()
        self.sizet_size = self.read_byte()
        self.instruction_size = self.read_byte()
        self.number_size = self.read_byte()
        
        # 整数格式 (0 = 浮点数, 1 = 整数)
        integral = self.read_byte()
        
        # 保存头部信息
        self.header_info = {
            'signature': signature,
            'version': version,
            'format': format,
            'endianness': endian,
            'size_int': self.int_size,
            'size_size_t': self.sizet_size,
            'size_instruction': self.instruction_size,
            'size_number': self.number_size,
            'integral_flag': integral
        }
    
    def parse(self) -> Proto:
        """解析 luac 文件"""
        self.check_header()
        return self.read_proto()

class Lua51Dumper:
    """Lua 5.1 字节码输出器"""
    
    OPCODE_INFO = {
        # 操作码: (格式, 描述)
        OpCode.OP_MOVE: ('iABC', 'R(A) := R(B)'),
        OpCode.OP_LOADK: ('iABx', 'R(A) := Kst(Bx)'),
        OpCode.OP_LOADBOOL: ('iABC', 'R(A) := (Bool)B; if (C) pc++'),
        OpCode.OP_LOADNIL: ('iABC', 'R(A) := ... := R(B) := nil'),
        OpCode.OP_GETUPVAL: ('iABC', 'R(A) := UpValue[B]'),
        OpCode.OP_GETGLOBAL: ('iABx', 'R(A) := Gbl[Kst(Bx)]'),
        OpCode.OP_GETTABLE: ('iABC', 'R(A) := R(B)[RK(C)]'),
        OpCode.OP_SETGLOBAL: ('iABx', 'Gbl[Kst(Bx)] := R(A)'),
        OpCode.OP_SETUPVAL: ('iABC', 'UpValue[B] := R(A)'),
        OpCode.OP_SETTABLE: ('iABC', 'R(A)[RK(B)] := RK(C)'),
        OpCode.OP_NEWTABLE: ('iABC', 'R(A) := {} (size = B,C)'),
        OpCode.OP_SELF: ('iABC', 'R(A+1) := R(B); R(A) := R(B)[RK(C)]'),
        OpCode.OP_ADD: ('iABC', 'R(A) := RK(B) + RK(C)'),
        OpCode.OP_SUB: ('iABC', 'R(A) := RK(B) - RK(C)'),
        OpCode.OP_MUL: ('iABC', 'R(A) := RK(B) * RK(C)'),
        OpCode.OP_DIV: ('iABC', 'R(A) := RK(B) / RK(C)'),
        OpCode.OP_MOD: ('iABC', 'R(A) := RK(B) % RK(C)'),
        OpCode.OP_POW: ('iABC', 'R(A) := RK(B) ^ RK(C)'),
        OpCode.OP_UNM: ('iABC', 'R(A) := -R(B)'),
        OpCode.OP_NOT: ('iABC', 'R(A) := not R(B)'),
        OpCode.OP_LEN: ('iABC', 'R(A) := length of R(B)'),
        OpCode.OP_CONCAT: ('iABC', 'R(A) := R(B).. ... ..R(C)'),
        OpCode.OP_JMP: ('iAsBx', 'pc+=sBx'),
        OpCode.OP_EQ: ('iABC', 'if ((RK(B) == RK(C)) ~= A) then pc++'),
        OpCode.OP_LT: ('iABC', 'if ((RK(B) <  RK(C)) ~= A) then pc++'),
        OpCode.OP_LE: ('iABC', 'if ((RK(B) <= RK(C)) ~= A) then pc++'),
        OpCode.OP_TEST: ('iABC', 'if not (R(A) <=> C) then pc++'),
        OpCode.OP_TESTSET: ('iABC', 'if (R(B) <=> C) then R(A) := R(B) else pc++'),
        OpCode.OP_CALL: ('iABC', 'R(A), ... ,R(A+C-2) := R(A)(R(A+1), ... ,R(A+B-1))'),
        OpCode.OP_TAILCALL: ('iABC', 'return R(A)(R(A+1), ... ,R(A+B-1))'),
        OpCode.OP_RETURN: ('iABC', 'return R(A), ... ,R(A+B-2)'),
        OpCode.OP_FORLOOP: ('iAsBx', 'R(A)+=R(A+2); if R(A) <?= R(A+1) then { pc+=sBx; R(A+3)=R(A) }'),
        OpCode.OP_FORPREP: ('iAsBx', 'R(A)-=R(A+2); pc+=sBx'),
        OpCode.OP_TFORLOOP: ('iAC', 'R(A+3), ... ,R(A+2+C) := R(A)(R(A+1), R(A+2))'),
        OpCode.OP_SETLIST: ('iABC', 'R(A)[(C-1)*FPF+i] := R(A+i), 1 <= i <= B'),
        OpCode.OP_CLOSE: ('iABC', 'close all variables in the stack up to (>=) R(A)'),
        OpCode.OP_CLOSURE: ('iABx', 'R(A) := closure(KPROTO[Bx], R(A), ... ,R(A+n))'),
        OpCode.OP_VARARG: ('iABC', 'R(A), R(A+1), ..., R(A+B-1) = vararg'),
    }
    
    @staticmethod
    def dump_header(header_info: dict):
        """输出头部信息"""
        print("=" * 80)
        print("HEADER INFORMATION")
        print("=" * 80)
        print(f"Signature:        {header_info['signature']}")
        print(f"Version:          0x{header_info['version']:02X} (Lua 5.1)")
        print(f"Format:           {header_info['format']}")
        print(f"Endianness:       {'Little' if header_info['endianness'] == 1 else 'Big'}")
        print(f"Size of int:      {header_info['size_int']} bytes")
        print(f"Size of size_t:   {header_info['size_size_t']} bytes")
        print(f"Size of Instruction: {header_info['size_instruction']} bytes")
        print(f"Size of lua_Number: {header_info['size_number']} bytes")
        print(f"Number type:      {'Integer' if header_info['integral_flag'] else 'Floating-point'}")
        print()
    
    @staticmethod
    def dump_proto(proto: Proto, indent: int = 0):
        """输出函数原型信息"""
        prefix = "  " * indent
        
        # 函数头部信息
        print(f"{prefix}{'=' * 60}")
        print(f"{prefix}FUNCTION: {proto.source}:{proto.line_defined}-{proto.last_line_defined}")
        print(f"{prefix}{'=' * 60}")
        print(f"{prefix}Parameters:       {proto.num_params}")
        print(f"{prefix}Is Vararg:        {'Yes' if proto.is_vararg else 'No'}")
        print(f"{prefix}Max Stack Size:   {proto.max_stack_size}")
        print(f"{prefix}Upvalues:         {proto.nups}")
        print(f"{prefix}Instructions:     {len(proto.code)}")
        print(f"{prefix}Constants:        {len(proto.constants)}")
        print(f"{prefix}Local Variables:  {len(proto.debug_info['locvars'])}")
        print(f"{prefix}Sub-functions:    {len(proto.protos)}")
        print()
        
        # 指令表
        if proto.code:
            print(f"{prefix}INSTRUCTIONS ({len(proto.code)}):")
            print(f"{prefix}{'-' * 60}")
            print(f"{prefix}{'PC':<4} {'Line':<6} {'OpCode':<12} {'A':<3} {'B':<3} {'C':<3} {'Bx':<6} {'sBx':<6} {'Description'}")
            print(f"{prefix}{'-' * 60}")
            
            for i, inst in enumerate(proto.code):
                line = proto.debug_info['lineinfo'][i] if i < len(proto.debug_info['lineinfo']) else 0
                
                # 获取指令信息
                info = Lua51Dumper.OPCODE_INFO.get(inst.opcode, ('iABC', ''))
                fmt, desc = info
                
                # 格式化操作码名称
                opcode_name = inst.opcode.name
                
                # 根据指令格式显示参数
                if fmt == 'iABC':
                    params = f"{inst.a:<3} {inst.b:<3} {inst.c:<3} {'':>6} {'':>6}"
                elif fmt == 'iABx':
                    params = f"{inst.a:<3} {'':>3} {'':>3} {inst.bx:<6} {'':>6}"
                elif fmt == 'iAsBx':
                    params = f"{inst.a:<3} {'':>3} {'':>3} {'':>6} {inst.sbx:<6}"
                else:
                    params = f"{inst.a:<3} {inst.b:<3} {inst.c:<3} {inst.bx:<6} {inst.sbx:<6}"
                
                # 特殊处理某些指令的额外信息
                extra_info = ""
                if inst.opcode == OpCode.OP_LOADK and inst.bx < len(proto.constants):
                    const = proto.constants[inst.bx]
                    if isinstance(const, str):
                        extra_info = f' ; K[{inst.bx}] = "{const}"'
                    else:
                        extra_info = f' ; K[{inst.bx}] = {const}'
                elif inst.opcode in (OpCode.OP_GETGLOBAL, OpCode.OP_SETGLOBAL):
                    if inst.bx < len(proto.constants):
                        extra_info = f' ; K[{inst.bx}] = "{proto.constants[inst.bx]}"'
                elif inst.opcode == OpCode.OP_JMP:
                    target = i + 1 + inst.sbx
                    extra_info = f' ; to PC {target}'
                
                print(f"{prefix}{i+1:<4} {line:<6} {opcode_name:<12} {params} {desc}{extra_info}")
            print()
        
        # 常量表
        if proto.constants:
            print(f"{prefix}CONSTANTS ({len(proto.constants)}):")
            print(f"{prefix}{'-' * 40}")
            print(f"{prefix}{'Index':<6} {'Type':<10} {'Value'}")
            print(f"{prefix}{'-' * 40}")
            
            for i, const in enumerate(proto.constants):
                if const is None:
                    const_type = "nil"
                    const_repr = "nil"
                elif isinstance(const, bool):
                    const_type = "boolean"
                    const_repr = str(const).lower()
                elif isinstance(const, (int, float)):
                    const_type = "number"
                    const_repr = str(const)
                elif isinstance(const, str):
                    const_type = "string"
                    const_repr = f'"{const}"'
                else:
                    const_type = type(const).__name__
                    const_repr = str(const)
                
                print(f"{prefix}{i:<6} {const_type:<10} {const_repr}")
            print()
        
        # 局部变量
        if proto.debug_info['locvars']:
            print(f"{prefix}LOCAL VARIABLES ({len(proto.debug_info['locvars'])}):")
            print(f"{prefix}{'-' * 40}")
            print(f"{prefix}{'Index':<6} {'Name':<15} {'Start PC':<9} {'End PC'}")
            print(f"{prefix}{'-' * 40}")
            
            for i, var in enumerate(proto.debug_info['locvars']):
                print(f"{prefix}{i:<6} {var.varname:<15} {var.startpc+1:<9} {var.endpc+1}")
            print()
        
        # 上值
        if proto.debug_info['upvalues']:
            print(f"{prefix}UPVALUES ({len(proto.debug_info['upvalues'])}):")
            print(f"{prefix}{'-' * 30}")
            print(f"{prefix}{'Index':<6} {'Name'}")
            print(f"{prefix}{'-' * 30}")
            
            for i, upval in enumerate(proto.debug_info['upvalues']):
                print(f"{prefix}{i:<6} {upval.name}")
            print()
        
        # 子函数
        if proto.protos:
            print(f"{prefix}SUB-FUNCTIONS ({len(proto.protos)}):")
            print(f"{prefix}{'-' * 60}")
            
            for i, subproto in enumerate(proto.protos):
                print(f"\n{prefix}Function #{i}:")
                Lua51Dumper.dump_proto(subproto, indent + 1)

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <luac_file> [--analyze]")
        sys.exit(1)
    
    filename = sys.argv[1]
    analyze = '--analyze' in sys.argv
    
    try:
        with open(filename, 'rb') as f:
            data = f.read()
        
        parser = Lua51Parser(data)
        proto = parser.parse()
        
        print(f"Lua 5.1 Bytecode Analysis: {filename}")
        print("=" * 80)
        
        # 打印头部信息
        Lua51Dumper.dump_header(parser.header_info)
        
        if analyze:
            # 分析模式
            print("ANALYSIS RESULTS")
            print("=" * 80)
            
            # 全局变量
            globals_used = Lua51Analyzer.analyze_globals(proto)
            print(f"\nGLOBAL VARIABLES USED ({len(globals_used)}):")
            print("-" * 40)
            for g in sorted(globals_used):
                print(f"  - {g}")
            
            # 字符串常量
            strings = Lua51Analyzer.analyze_strings(proto)
            print(f"\nSTRING CONSTANTS ({len(strings)}):")
            print("-" * 40)
            for s in strings[:10]:  # 只显示前10个
                print(f"  - \"{s}\"")
            if len(strings) > 10:
                print(f"  ... and {len(strings) - 10} more")
            
            # 函数列表
            functions = Lua51Analyzer.analyze_functions(proto)
            print(f"\nFUNCTIONS ({len(functions)}):")
            print("-" * 40)
            for func in functions:
                print(f"  - {func['path']} @ {func['source']}:{func['lines']}")
                print(f"    Params: {func['params']}, Vararg: {func['vararg']}, Stack: {func['stack']}")
                print(f"    Instructions: {func['instructions']}, Constants: {func['constants']}, Upvalues: {func['upvalues']}")
        else:
            # 标准输出模式
            print("BYTECODE DISASSEMBLY")
            print("=" * 80)
            Lua51Dumper.dump_proto(proto)
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

class Lua51Analyzer:
    """Lua 5.1 字节码分析器"""
    
    @staticmethod
    def analyze_globals(proto: Proto) -> set:
        """分析全局变量使用"""
        globals_used = set()
        
        for inst in proto.code:
            if inst.opcode in [OpCode.OP_GETGLOBAL, OpCode.OP_SETGLOBAL]:
                if inst.bx < len(proto.constants):
                    globals_used.add(proto.constants[inst.bx])
        
        # 递归分析子函数
        for subproto in proto.protos:
            globals_used.update(Lua51Analyzer.analyze_globals(subproto))
        
        return globals_used
    
    @staticmethod
    def analyze_strings(proto: Proto) -> List[str]:
        """提取所有字符串常量"""
        strings = []
        
        for const in proto.constants:
            if isinstance(const, str):
                strings.append(const)
        
        # 递归分析子函数
        for subproto in proto.protos:
            strings.extend(Lua51Analyzer.analyze_strings(subproto))
        
        return strings
    
    @staticmethod
    def analyze_functions(proto: Proto, path: str = "main") -> List[dict]:
        """分析函数信息"""
        functions = [{
            'path': path,
            'source': proto.source,
            'lines': f"{proto.line_defined}-{proto.last_line_defined}",
            'params': proto.num_params,
            'vararg': bool(proto.is_vararg),
            'stack': proto.max_stack_size,
            'instructions': len(proto.code),
            'constants': len(proto.constants),
            'upvalues': proto.nups
        }]
        
        # 递归分析子函数
        for i, subproto in enumerate(proto.protos):
            subpath = f"{path}.func{i}"
            functions.extend(Lua51Analyzer.analyze_functions(subproto, subpath))
        
        return functions

if __name__ == "__main__":
    main()
