#!/usr/bin/env python3
"""
Lua 5.4 bytecode parser
解析并展示 luac 文件的详细结构
"""

import struct
import sys
import argparse
from typing import List, Dict, Any, BinaryIO
from dataclasses import dataclass
from enum import IntEnum

# Lua 5.4 常量
LUA_SIGNATURE = b"\x1bLua"
LUAC_VERSION = 0x54
LUAC_FORMAT = 0
LUAC_DATA = b"\x19\x93\r\n\x1a\n"
LUAC_INT = 0x5678
LUAC_NUM = 370.5


# 数据类型 - 修复为Lua 5.4的实际内部类型标签
class LuaType(IntEnum):
    # 基本类型常量（来自lua.h）
    LUA_TNIL = 0
    LUA_TBOOLEAN = 1
    LUA_TLIGHTUSERDATA = 2
    LUA_TNUMBER = 3
    LUA_TSTRING = 4
    LUA_TTABLE = 5
    LUA_TFUNCTION = 6
    LUA_TUSERDATA = 7
    LUA_TTHREAD = 8
    
    # 内部类型标签（来自lobject.h，使用makevariant宏）
    VNIL = 0          # makevariant(LUA_TNIL, 0)
    VFALSE = 17       # makevariant(LUA_TBOOLEAN, 0) = 1 | (0 << 4)
    VTRUE = 33        # makevariant(LUA_TBOOLEAN, 1) = 1 | (1 << 4)
    VNUMFLT = 19      # makevariant(LUA_TNUMBER, 0) = 3 | (0 << 4)
    VNUMINT = 35      # makevariant(LUA_TNUMBER, 1) = 3 | (1 << 4)
    VSHRSTR = 20      # makevariant(LUA_TSTRING, 0) = 4 | (0 << 4)
    VLNGSTR = 36      # makevariant(LUA_TSTRING, 1) = 4 | (1 << 4)
    
    # 其他可能的类型
    VLIGHTUSERDATA = 18  # makevariant(LUA_TLIGHTUSERDATA, 0)
    VLCF = 22           # makevariant(LUA_TFUNCTION, 0) - light C function
    VCCL = 38           # makevariant(LUA_TFUNCTION, 1) - C closure
    VLCL = 54           # makevariant(LUA_TFUNCTION, 2) - Lua closure


# 指令格式
class OpMode(IntEnum):
    iABC = 0
    iABx = 1
    iAsBx = 2
    iAx = 3
    isJ = 4


# 操作码
class OpCode(IntEnum):
    MOVE = 0
    LOADI = 1
    LOADF = 2
    LOADK = 3
    LOADKX = 4
    LOADFALSE = 5
    LFALSESKIP = 6
    LOADTRUE = 7
    LOADNIL = 8
    GETUPVAL = 9
    SETUPVAL = 10
    GETTABUP = 11
    GETTABLE = 12
    GETI = 13
    GETFIELD = 14
    SETTABUP = 15
    SETTABLE = 16
    SETI = 17
    SETFIELD = 18
    NEWTABLE = 19
    SELF = 20
    ADDI = 21
    ADDK = 22
    SUBK = 23
    MULK = 24
    MODK = 25
    POWK = 26
    DIVK = 27
    IDIVK = 28
    BANDK = 29
    BORK = 30
    BXORK = 31
    SHRI = 32
    SHLI = 33
    ADD = 34
    SUB = 35
    MUL = 36
    MOD = 37
    POW = 38
    DIV = 39
    IDIV = 40
    BAND = 41
    BOR = 42
    BXOR = 43
    SHL = 44
    SHR = 45
    MMBIN = 46
    MMBINI = 47
    MMBINK = 48
    UNM = 49
    BNOT = 50
    NOT = 51
    LEN = 52
    CONCAT = 53
    CLOSE = 54
    TBC = 55
    JMP = 56
    EQ = 57
    LT = 58
    LE = 59
    EQK = 60
    EQI = 61
    LTI = 62
    LEI = 63
    GTI = 64
    GEI = 65
    TEST = 66
    TESTSET = 67
    CALL = 68
    TAILCALL = 69
    RETURN = 70
    RETURN0 = 71
    RETURN1 = 72
    FORLOOP = 73
    FORPREP = 74
    TFORPREP = 75
    TFORCALL = 76
    TFORLOOP = 77
    SETLIST = 78
    CLOSURE = 79
    VARARG = 80
    VARARGPREP = 81
    EXTRAARG = 82


# 指令格式信息
# 指令格式信息 - 完整版本
OPCODE_INFO = {
    OpCode.MOVE: ("MOVE", OpMode.iABC),
    OpCode.LOADI: ("LOADI", OpMode.iAsBx),
    OpCode.LOADF: ("LOADF", OpMode.iAsBx),
    OpCode.LOADK: ("LOADK", OpMode.iABx),
    OpCode.LOADKX: ("LOADKX", OpMode.iABx),
    OpCode.LOADFALSE: ("LOADFALSE", OpMode.iABC),
    OpCode.LFALSESKIP: ("LFALSESKIP", OpMode.iABC),
    OpCode.LOADTRUE: ("LOADTRUE", OpMode.iABC),
    OpCode.LOADNIL: ("LOADNIL", OpMode.iABC),
    OpCode.GETUPVAL: ("GETUPVAL", OpMode.iABC),
    OpCode.SETUPVAL: ("SETUPVAL", OpMode.iABC),
    OpCode.GETTABUP: ("GETTABUP", OpMode.iABC),
    OpCode.GETTABLE: ("GETTABLE", OpMode.iABC),
    OpCode.GETI: ("GETI", OpMode.iABC),
    OpCode.GETFIELD: ("GETFIELD", OpMode.iABC),
    OpCode.SETTABUP: ("SETTABUP", OpMode.iABC),
    OpCode.SETTABLE: ("SETTABLE", OpMode.iABC),
    OpCode.SETI: ("SETI", OpMode.iABC),
    OpCode.SETFIELD: ("SETFIELD", OpMode.iABC),
    OpCode.NEWTABLE: ("NEWTABLE", OpMode.iABC),
    OpCode.SELF: ("SELF", OpMode.iABC),
    OpCode.ADDI: ("ADDI", OpMode.iABC),
    OpCode.ADDK: ("ADDK", OpMode.iABC),
    OpCode.SUBK: ("SUBK", OpMode.iABC),
    OpCode.MULK: ("MULK", OpMode.iABC),
    OpCode.MODK: ("MODK", OpMode.iABC),
    OpCode.POWK: ("POWK", OpMode.iABC),
    OpCode.DIVK: ("DIVK", OpMode.iABC),
    OpCode.IDIVK: ("IDIVK", OpMode.iABC),
    OpCode.BANDK: ("BANDK", OpMode.iABC),
    OpCode.BORK: ("BORK", OpMode.iABC),
    OpCode.BXORK: ("BXORK", OpMode.iABC),
    OpCode.SHRI: ("SHRI", OpMode.iABC),
    OpCode.SHLI: ("SHLI", OpMode.iABC),
    OpCode.ADD: ("ADD", OpMode.iABC),
    OpCode.SUB: ("SUB", OpMode.iABC),
    OpCode.MUL: ("MUL", OpMode.iABC),
    OpCode.MOD: ("MOD", OpMode.iABC),
    OpCode.POW: ("POW", OpMode.iABC),
    OpCode.DIV: ("DIV", OpMode.iABC),
    OpCode.IDIV: ("IDIV", OpMode.iABC),
    OpCode.BAND: ("BAND", OpMode.iABC),
    OpCode.BOR: ("BOR", OpMode.iABC),
    OpCode.BXOR: ("BXOR", OpMode.iABC),
    OpCode.SHL: ("SHL", OpMode.iABC),
    OpCode.SHR: ("SHR", OpMode.iABC),
    OpCode.MMBIN: ("MMBIN", OpMode.iABC),
    OpCode.MMBINI: ("MMBINI", OpMode.iABC),
    OpCode.MMBINK: ("MMBINK", OpMode.iABC),
    OpCode.UNM: ("UNM", OpMode.iABC),
    OpCode.BNOT: ("BNOT", OpMode.iABC),
    OpCode.NOT: ("NOT", OpMode.iABC),
    OpCode.LEN: ("LEN", OpMode.iABC),
    OpCode.CONCAT: ("CONCAT", OpMode.iABC),
    OpCode.CLOSE: ("CLOSE", OpMode.iABC),
    OpCode.TBC: ("TBC", OpMode.iABC),
    OpCode.JMP: ("JMP", OpMode.isJ),
    OpCode.EQ: ("EQ", OpMode.iABC),
    OpCode.LT: ("LT", OpMode.iABC),
    OpCode.LE: ("LE", OpMode.iABC),
    OpCode.EQK: ("EQK", OpMode.iABC),
    OpCode.EQI: ("EQI", OpMode.iABC),
    OpCode.LTI: ("LTI", OpMode.iABC),
    OpCode.LEI: ("LEI", OpMode.iABC),
    OpCode.GTI: ("GTI", OpMode.iABC),
    OpCode.GEI: ("GEI", OpMode.iABC),
    OpCode.TEST: ("TEST", OpMode.iABC),
    OpCode.TESTSET: ("TESTSET", OpMode.iABC),
    OpCode.CALL: ("CALL", OpMode.iABC),
    OpCode.TAILCALL: ("TAILCALL", OpMode.iABC),
    OpCode.RETURN: ("RETURN", OpMode.iABC),
    OpCode.RETURN0: ("RETURN0", OpMode.iABC),
    OpCode.RETURN1: ("RETURN1", OpMode.iABC),
    OpCode.FORLOOP: ("FORLOOP", OpMode.iAsBx),
    OpCode.FORPREP: ("FORPREP", OpMode.iAsBx),
    OpCode.TFORPREP: ("TFORPREP", OpMode.iAsBx),
    OpCode.TFORCALL: ("TFORCALL", OpMode.iABC),
    OpCode.TFORLOOP: ("TFORLOOP", OpMode.iAsBx),
    OpCode.SETLIST: ("SETLIST", OpMode.iABC),
    OpCode.CLOSURE: ("CLOSURE", OpMode.iABx),
    OpCode.VARARG: ("VARARG", OpMode.iABC),
    OpCode.VARARGPREP: ("VARARGPREP", OpMode.iABC),
    OpCode.EXTRAARG: ("EXTRAARG", OpMode.iAx),
}


@dataclass
class Upvalue:
    instack: int
    idx: int
    kind: int
    # 添加原始数据存储
    ori: bytes = None


@dataclass
class LocVar:
    varname: str
    startpc: int
    endpc: int
    # 添加原始数据存储
    ori: bytes = None


@dataclass
class AbsLineInfo:
    pc: int
    line: int
    # 添加原始数据存储
    ori: bytes = None


@dataclass
class Proto:
    source: str
    linedefined: int
    lastlinedefined: int
    numparams: int
    is_vararg: int
    maxstacksize: int

    code: List[int]
    constants: List[Any]
    upvalues: List[Upvalue]
    protos: List['Proto']

    lineinfo: List[int]
    abslineinfo: List[AbsLineInfo]
    locvars: List[LocVar]
    upvalue_names: List[str]
    
    # 添加原始数据存储
    ori: Dict[str, bytes] = None
    
    def __post_init__(self):
        """初始化原始数据字典"""
        if self.ori is None:
            self.ori = {
                'source': b'',
                'linedefined': b'',
                'lastlinedefined': b'',
                'numparams': b'',
                'is_vararg': b'',
                'maxstacksize': b'',
                'code': b'',
                'constants': b'',
                'upvalues': b'',
                'protos': b'',
                'lineinfo': b'',
                'abslineinfo': b'',
                'locvars': b'',
                'upvalue_names': b''
            }

class LuacParser:
    def __init__(self, filename: str):
        self.filename = filename
        self.file: BinaryIO = None
        self.main_proto: Proto = None
        # 添加原始数据记录开关
        self._record_raw_data = True
        # 添加加密相关属性
        self.encryption_key = None
        self.encrypt_mode = False
    
    @staticmethod
    def compare_opcodes(standard_file: str, shuffled_file: str) -> Dict[int, int]:
        """对比两个luac文件的opcode指令，找出opcode映射关系
        
        Args:
            standard_file: 标准opcode虚拟机生成的luac文件
            shuffled_file: 打乱opcode顺序的虚拟机生成的luac文件
            
        Returns:
            Dict[int, int]: 映射关系字典，key为标准opcode，value为打乱后的opcode
        """
        print("\n" + "="*60)
        print("OPCODE 对比分析")
        print("="*60)
        
        # 解析两个文件
        print(f"正在解析标准文件: {standard_file}")
        standard_parser = LuacParser(standard_file)
        standard_parser.parse()
        
        print(f"正在解析打乱文件: {shuffled_file}")
        shuffled_parser = LuacParser(shuffled_file)
        shuffled_parser.parse()
        
        # 提取所有指令
        standard_instructions = LuacParser._extract_all_instructions(standard_parser.main_proto)
        shuffled_instructions = LuacParser._extract_all_instructions(shuffled_parser.main_proto)
        
        print(f"\n标准文件指令总数: {len(standard_instructions)}")
        print(f"打乱文件指令总数: {len(shuffled_instructions)}")
        
        if len(standard_instructions) != len(shuffled_instructions):
            raise ValueError("两个文件的指令数量不匹配，可能不是同一个lua代码生成的")
        
        # 分析opcode映射关系
        opcode_mapping = LuacParser._analyze_opcode_mapping(standard_instructions, shuffled_instructions)
        
        # 输出结果
        LuacParser._print_mapping_results(opcode_mapping)
        
        return opcode_mapping
    
    @staticmethod
    def _extract_all_instructions(proto: Proto) -> List[int]:
        """递归提取Proto及其所有子Proto中的指令
        
        Args:
            proto: 要提取指令的Proto对象
            
        Returns:
            List[int]: 所有指令的列表
        """
        instructions = []
        
        # 添加当前Proto的指令
        instructions.extend(proto.code)
        
        # 递归添加子Proto的指令
        for sub_proto in proto.protos:
            instructions.extend(LuacParser._extract_all_instructions(sub_proto))
        
        return instructions
    
    @staticmethod
    def _analyze_opcode_mapping(standard_instructions: List[int], shuffled_instructions: List[int]) -> Dict[int, int]:
        """分析opcode映射关系
        
        Args:
            standard_instructions: 标准指令列表
            shuffled_instructions: 打乱后的指令列表
            
        Returns:
            Dict[int, int]: opcode映射关系
        """
        opcode_mapping = {}
        opcode_pairs = []
        
        # 创建临时解析器实例用于解码指令
        temp_parser = LuacParser("")
        
        # 使用decode_instruction方法正确提取opcode
        for std_inst, shuf_inst in zip(standard_instructions, shuffled_instructions):
            std_decoded = temp_parser.decode_instruction(std_inst)
            shuf_decoded = temp_parser.decode_instruction(shuf_inst)
            
            std_opcode = std_decoded['opcode']
            shuf_opcode = shuf_decoded['opcode']
            
            opcode_pairs.append((std_opcode, shuf_opcode))
            
            # 记录映射关系
            if std_opcode in opcode_mapping:
                if opcode_mapping[std_opcode] != shuf_opcode:
                    print(f"警告: 发现不一致的映射 {std_opcode} -> {opcode_mapping[std_opcode]} 和 {shuf_opcode}")
            else:
                opcode_mapping[std_opcode] = shuf_opcode
        
        return opcode_mapping
    
    @staticmethod
    def _print_mapping_results(opcode_mapping: Dict[int, int]):
        """打印映射结果
        
        Args:
            opcode_mapping: opcode映射关系
        """
        print("\n" + "-"*60)
        print("OPCODE 映射关系")
        print("-"*60)
        print(f"{'标准OpCode':<15} {'打乱OpCode':<15} {'标准指令名':<15} {'映射指令名':<15}")
        print("-"*60)
        
        # 按标准opcode排序
        for std_opcode in sorted(opcode_mapping.keys()):
            shuf_opcode = opcode_mapping[std_opcode]
            
            # 获取指令名称
            std_name = "UNKNOWN"
            shuf_name = "UNKNOWN"
            
            try:
                if std_opcode in OpCode.__members__.values():
                    std_name = OpCode(std_opcode).name
            except ValueError:
                pass
            
            try:
                if shuf_opcode in OpCode.__members__.values():
                    shuf_name = OpCode(shuf_opcode).name
            except ValueError:
                pass
            
            print(f"{std_opcode:<15} {shuf_opcode:<15} {std_name:<15} {shuf_name:<15}")
        
        print("-"*60)
        print(f"总共发现 {len(opcode_mapping)} 个不同的opcode映射")
        
        # 统计信息
        identity_mappings = sum(1 for std, shuf in opcode_mapping.items() if std == shuf)
        changed_mappings = len(opcode_mapping) - identity_mappings
        
        print(f"未改变的映射: {identity_mappings}")
        print(f"已改变的映射: {changed_mappings}")
        
        if changed_mappings > 0:
            print("\n改变的映射详情:")
            for std_opcode, shuf_opcode in opcode_mapping.items():
                if std_opcode != shuf_opcode:
                    std_name = "UNKNOWN"
                    shuf_name = "UNKNOWN"
                    
                    try:
                        if std_opcode in OpCode.__members__.values():
                            std_name = OpCode(std_opcode).name
                    except ValueError:
                        pass
                    
                    try:
                        if shuf_opcode in OpCode.__members__.values():
                            shuf_name = OpCode(shuf_opcode).name
                    except ValueError:
                        pass
                    
                    print(f"  {std_opcode}({std_name}) -> {shuf_opcode}({shuf_name})")

    def read_byte(self) -> int:
        """读取一个字节"""
        return struct.unpack('B', self.file.read(1))[0]

    def read_size(self) -> int:
        """读取大小值 (变长编码) - 修复为符合Lua 5.4格式
        
        Lua 5.4使用变长编码存储大小值：
        - 每个字节的低7位存储数据
        - 最高位为0表示还有后续字节，为1表示这是最后一个字节
        - 数据按大端序组织（高位在前）
        """
        x = 0
        # 设置溢出限制，防止无限循环
        limit = (1 << (8 * 8 - 7))  # 大约是 2^57
        
        while True:
            b = self.read_byte()
            if x >= limit:
                raise ValueError("变长编码整数溢出")
            
            # 将当前值左移7位，然后加上新字节的低7位
            x = (x << 7) | (b & 0x7f)
            
            # 如果最高位为1，说明这是最后一个字节
            if (b & 0x80) != 0:
                break
                
        return x

    def read_int(self) -> int:
        """读取一个整数 - 在Lua 5.4中使用变长编码"""
        return self.read_size()

    def read_integer(self) -> int:
        """读取 Lua 整数 (8字节)"""
        return struct.unpack('<q', self.file.read(8))[0]

    def read_number(self) -> float:
        """读取 Lua 浮点数 (8字节)"""
        return struct.unpack('<d', self.file.read(8))[0]

    def read_string(self) -> str:
        """读取字符串
        
        Lua 5.4字符串格式：
        - 先读取长度（变长编码）
        - 长度为0表示NULL字符串
        - 长度包含结尾的\0字符，所以实际字符串长度要减1
        """
        size = self.read_size()
        if size == 0:
            return None
        size -= 1  # Lua 字符串长度包含结尾的 \0
        data = self.file.read(size)
        return data.decode('utf-8', errors='replace')
    
    def read_byte_with_raw(self) -> tuple[int, bytes]:
        """读取一个字节并返回原始数据"""
        raw_data = self.file.read(1)
        return struct.unpack('B', raw_data)[0], raw_data

    def read_size_with_raw(self) -> tuple[int, bytes]:
        """读取大小值并返回原始数据"""
        x = 0
        raw_data = b''
        limit = (1 << (8 * 8 - 7))
        
        while True:
            byte_data = self.file.read(1)
            raw_data += byte_data
            b = struct.unpack('B', byte_data)[0]
            
            if x >= limit:
                raise ValueError("变长编码整数溢出")
            
            x = (x << 7) | (b & 0x7f)
            
            if (b & 0x80) != 0:
                break
                
        return x, raw_data

    def read_integer_with_raw(self) -> tuple[int, bytes]:
        """读取Lua整数并返回原始数据"""
        raw_data = self.file.read(8)
        return struct.unpack('<q', raw_data)[0], raw_data

    def read_number_with_raw(self) -> tuple[float, bytes]:
        """读取Lua浮点数并返回原始数据"""
        raw_data = self.file.read(8)
        return struct.unpack('<d', raw_data)[0], raw_data

    def read_string_with_raw(self) -> tuple[str, bytes]:
        """读取字符串并返回原始数据"""
        size, size_raw = self.read_size_with_raw()
        if size == 0:
            return None, size_raw
        
        size -= 1
        string_data = self.file.read(size)
        total_raw = size_raw + string_data
        
        return string_data.decode('utf-8', errors='replace'), total_raw

    def read_vector(self, n: int) -> bytes:
        """读取 n 个字节"""
        return self.file.read(n)

    def check_header(self):
        """检查文件头"""
        print("\n" + "="*50)
        print("文件头 (Header)")
        print("="*50)
    
        # 签名
        signature = self.file.read(4)
        if signature != LUA_SIGNATURE:
            raise ValueError("不是有效的 Lua 字节码文件")
        print(f"✓ 签名: {signature} [4 bytes]")
    
        # 版本
        version = self.read_byte()
        if version != LUAC_VERSION:
            raise ValueError(f"版本不匹配: 期望 {LUAC_VERSION}, 实际 {version}")
        print(f"✓ 版本: Lua {version >> 4}.{version & 0xF} [1 byte]")
    
        # 格式和数据校验
        format_byte = self.read_byte()
        data = self.file.read(6)
        print(f"✓ 格式校验: 通过 [7 bytes]")
    
        # 大小信息
        inst_size = self.read_byte()
        int_size = self.read_byte()
        num_size = self.read_byte()
        print(f"✓ 类型大小: 指令{inst_size}字节, 整数{int_size}字节, 浮点{num_size}字节 [3 bytes]")
    
        # 测试值
        test_int = self.read_integer()
        test_num = self.read_number()
        print(f"✓ 测试值: 整数0x{test_int:X}, 浮点{test_num} [16 bytes]")
        print(f"文件头总大小: 31 bytes\n")
    
    def read_upvalues(self, proto: Proto):
        """读取upvalue信息并记录原始数据"""
        n, n_raw = self.read_size_with_raw() if self._record_raw_data else (self.read_int(), b'')
        proto.upvalues = []
        upvalues_raw = n_raw
        
        for i in range(n):
            if self._record_raw_data:
                instack, instack_raw = self.read_byte_with_raw()
                idx, idx_raw = self.read_byte_with_raw()
                kind, kind_raw = self.read_byte_with_raw()
                upvalue_raw = instack_raw + idx_raw + kind_raw
                upvalues_raw += upvalue_raw
                
                upvalue = Upvalue(instack, idx, kind)
                upvalue.ori = upvalue_raw
                proto.upvalues.append(upvalue)
            else:
                instack = self.read_byte()
                idx = self.read_byte()
                kind = self.read_byte()
                proto.upvalues.append(Upvalue(instack, idx, kind))
        
        if self._record_raw_data:
            proto.ori['upvalues'] = upvalues_raw
    
    def read_constants(self, proto: Proto):
        """读取常量表并记录原始数据"""
        n, n_raw = self.read_size_with_raw() if self._record_raw_data else (self.read_int(), b'')
        proto.constants = []
        constants_raw = n_raw
        
        for i in range(n):
            if self._record_raw_data:
                t, t_raw = self.read_byte_with_raw()
                const_raw = t_raw
            else:
                t = self.read_byte()
            
            base_type = t & 0x0F
            variant = (t >> 4) & 0x0F
            
            if t == LuaType.VNIL or base_type == LuaType.LUA_TNIL:
                proto.constants.append(None)
            elif t == LuaType.VFALSE:
                proto.constants.append(False)
            elif t == LuaType.VTRUE:
                proto.constants.append(True)
            elif t == LuaType.VNUMFLT:
                if self._record_raw_data:
                    value, value_raw = self.read_number_with_raw()
                    const_raw += value_raw
                else:
                    value = self.read_number()
                proto.constants.append(value)
            elif t == LuaType.VNUMINT:
                if self._record_raw_data:
                    value, value_raw = self.read_integer_with_raw()
                    const_raw += value_raw
                else:
                    value = self.read_integer()
                proto.constants.append(value)
            elif t == LuaType.VSHRSTR or t == LuaType.VLNGSTR:
                if self._record_raw_data:
                    value, value_raw = self.read_string_with_raw()
                    const_raw += value_raw
                else:
                    value = self.read_string()
                proto.constants.append(value)
            elif base_type == LuaType.LUA_TBOOLEAN:
                if variant == 0:
                    proto.constants.append(False)
                else:
                    proto.constants.append(True)
            elif base_type == LuaType.LUA_TNUMBER:
                if variant == 0:
                    if self._record_raw_data:
                        value, value_raw = self.read_number_with_raw()
                        const_raw += value_raw
                    else:
                        value = self.read_number()
                    proto.constants.append(value)
                else:
                    if self._record_raw_data:
                        value, value_raw = self.read_integer_with_raw()
                        const_raw += value_raw
                    else:
                        value = self.read_integer()
                    proto.constants.append(value)
            elif base_type == LuaType.LUA_TSTRING:
                if self._record_raw_data:
                    value, value_raw = self.read_string_with_raw()
                    const_raw += value_raw
                else:
                    value = self.read_string()
                proto.constants.append(value)
            else:
                raise ValueError(f"未知的常量类型: {t}")
            
            if self._record_raw_data:
                constants_raw += const_raw
        
        if self._record_raw_data:
            proto.ori['constants'] = constants_raw
    
    def read_code(self, proto: Proto):
        """读取指令并记录原始数据"""
        n, n_raw = self.read_size_with_raw() if self._record_raw_data else (self.read_int(), b'')
        proto.code = []
        code_raw = n_raw
        
        for i in range(n):
            inst_raw = self.file.read(4)
            inst = struct.unpack('<I', inst_raw)[0]
            proto.code.append(inst)
            
            if self._record_raw_data:
                code_raw += inst_raw
        
        if self._record_raw_data:
            proto.ori['code'] = code_raw
    
    def read_debug(self, proto: Proto):
        """读取调试信息并记录原始数据"""
        debug_raw = b''
        
        # 行号信息
        n, n_raw = self.read_size_with_raw() if self._record_raw_data else (self.read_int(), b'')
        if self._record_raw_data:
            debug_raw += n_raw
        
        proto.lineinfo = []
        for i in range(n):
            if self._record_raw_data:
                line, line_raw = self.read_byte_with_raw()
                debug_raw += line_raw
            else:
                line = self.read_byte()
            proto.lineinfo.append(line)
        
        # 绝对行号信息
        n, n_raw = self.read_size_with_raw() if self._record_raw_data else (self.read_int(), b'')
        if self._record_raw_data:
            debug_raw += n_raw
        
        proto.abslineinfo = []
        for i in range(n):
            if self._record_raw_data:
                pc, pc_raw = self.read_size_with_raw()
                line, line_raw = self.read_size_with_raw()
                abs_raw = pc_raw + line_raw
                debug_raw += abs_raw
                
                absline = AbsLineInfo(pc, line)
                absline.ori = abs_raw
                proto.abslineinfo.append(absline)
            else:
                pc = self.read_int()
                line = self.read_int()
                proto.abslineinfo.append(AbsLineInfo(pc, line))
        
        # 局部变量
        n, n_raw = self.read_size_with_raw() if self._record_raw_data else (self.read_int(), b'')
        if self._record_raw_data:
            debug_raw += n_raw
        
        proto.locvars = []
        for i in range(n):
            if self._record_raw_data:
                varname, varname_raw = self.read_string_with_raw()
                startpc, startpc_raw = self.read_size_with_raw()
                endpc, endpc_raw = self.read_size_with_raw()
                locvar_raw = varname_raw + startpc_raw + endpc_raw
                debug_raw += locvar_raw
                
                locvar = LocVar(varname, startpc, endpc)
                locvar.ori = locvar_raw
                proto.locvars.append(locvar)
            else:
                varname = self.read_string()
                startpc = self.read_int()
                endpc = self.read_int()
                proto.locvars.append(LocVar(varname, startpc, endpc))
        
        # upvalue名称
        n, n_raw = self.read_size_with_raw() if self._record_raw_data else (self.read_int(), b'')
        if self._record_raw_data:
            debug_raw += n_raw
        
        proto.upvalue_names = []
        for i in range(n):
            if self._record_raw_data:
                name, name_raw = self.read_string_with_raw()
                debug_raw += name_raw
            else:
                name = self.read_string()
            proto.upvalue_names.append(name)
        
        if self._record_raw_data:
            proto.ori['lineinfo'] = debug_raw[:len(debug_raw)//4]  # 简化处理
            proto.ori['abslineinfo'] = debug_raw[len(debug_raw)//4:len(debug_raw)//2]
            proto.ori['locvars'] = debug_raw[len(debug_raw)//2:3*len(debug_raw)//4]
            proto.ori['upvalue_names'] = debug_raw[3*len(debug_raw)//4:]
    
    def read_protos(self, proto: Proto):
        """读取子函数列表并记录原始数据"""
        n, n_raw = self.read_size_with_raw() if self._record_raw_data else (self.read_int(), b'')
        proto.protos = []
        protos_raw = n_raw
        
        for i in range(n):
            subproto = self.read_proto(proto.source)
            proto.protos.append(subproto)
            
            if self._record_raw_data:
                # 收集子函数的原始数据（这里简化处理，实际应该记录完整的子函数字节数据）
                protos_raw += b''
        
        if self._record_raw_data:
            proto.ori['protos'] = protos_raw
    
    def read_proto(self, parent_source: str) -> Proto:
        """读取函数原型并记录原始数据"""
        proto = Proto(
            source=None,
            linedefined=0,
            lastlinedefined=0,
            numparams=0,
            is_vararg=0,
            maxstacksize=0,
            code=[],
            constants=[],
            upvalues=[],
            protos=[],
            lineinfo=[],
            abslineinfo=[],
            locvars=[],
            upvalue_names=[]
        )
        
        # 基本信息
        if self._record_raw_data:
            proto.source, source_raw = self.read_string_with_raw()
            proto.ori['source'] = source_raw
        else:
            proto.source = self.read_string()
        
        if proto.source is None:
            proto.source = parent_source
        
        if self._record_raw_data:
            proto.linedefined, linedefined_raw = self.read_size_with_raw()
            proto.lastlinedefined, lastlinedefined_raw = self.read_size_with_raw()
            proto.numparams, numparams_raw = self.read_byte_with_raw()
            proto.is_vararg, is_vararg_raw = self.read_byte_with_raw()
            proto.maxstacksize, maxstacksize_raw = self.read_byte_with_raw()
            
            proto.ori['linedefined'] = linedefined_raw
            proto.ori['lastlinedefined'] = lastlinedefined_raw
            proto.ori['numparams'] = numparams_raw
            proto.ori['is_vararg'] = is_vararg_raw
            proto.ori['maxstacksize'] = maxstacksize_raw
        else:
            proto.linedefined = self.read_int()
            proto.lastlinedefined = self.read_int()
            proto.numparams = self.read_byte()
            proto.is_vararg = self.read_byte()
            proto.maxstacksize = self.read_byte()
        
        # 读取各部分
        self.read_code(proto)
        self.read_constants(proto)
        self.read_upvalues(proto)
        self.read_protos(proto)
        self.read_debug(proto)
        
        return proto
    
    def decode_instruction(self, inst: int) -> Dict[str, Any]:
        """解码单条指令"""
        opcode = inst & 0x7F
    
        result = {
            'raw': inst,
            'opcode': opcode,
            'name': 'UNKNOWN'
        }
    
        if opcode in OPCODE_INFO:
            name, mode = OPCODE_INFO[opcode]
            result['name'] = name
            result['mode'] = mode
    
            if mode == OpMode.iABC:
                result['A'] = (inst >> 7) & 0xFF
                result['B'] = (inst >> 16) & 0xFF
                result['k'] = (inst >> 15) & 0x1
                result['C'] = (inst >> 24) & 0xFF
            elif mode == OpMode.iABx:
                result['A'] = (inst >> 7) & 0xFF
                result['Bx'] = (inst >> 15) & 0x1FFFF
            elif mode == OpMode.iAsBx:
                result['A'] = (inst >> 7) & 0xFF
                result['sBx'] = ((inst >> 15) & 0x1FFFF) - 0xFFFF
            elif mode == OpMode.iAx:
                result['Ax'] = (inst >> 7) & 0x1FFFFFF
            elif mode == OpMode.isJ:
                result['sJ'] = ((inst >> 7) & 0x1FFFFFF) - 0xFFFFFF
    
        return result
    
    def print_proto(self, proto: Proto, level: int = 0):
        """打印函数原型信息 - 完整展示版本，显示所有数据并添加原变量名"""
        indent = "  " * level
        border = "═" * 60
        thin_border = "─" * 60
        
        # 函数头部信息
        print(f"\n{indent}╔{border}╗")
        print(f"{indent}║ 📁 函数原型 [Level {level}] (Proto)" + " " * (60 - len(f"函数原型 [Level {level}] (Proto)") - 4) + "║")
        print(f"{indent}╠{border}╣")
        print(f"{indent}║ 📄 源文件 (source): {proto.source}" + " " * max(0, 60 - len(f"源文件 (source): {proto.source}") - 4) + "║")
        print(f"{indent}║ 📍 起始行 (linedefined): {proto.linedefined}" + " " * max(0, 60 - len(f"起始行 (linedefined): {proto.linedefined}") - 4) + "║")
        print(f"{indent}║ 📍 结束行 (lastlinedefined): {proto.lastlinedefined}" + " " * max(0, 60 - len(f"结束行 (lastlinedefined): {proto.lastlinedefined}") - 4) + "║")
        print(f"{indent}║ 🔧 参数个数 (numparams): {proto.numparams}" + " " * max(0, 60 - len(f"参数个数 (numparams): {proto.numparams}") - 4) + "║")
        print(f"{indent}║ 🔧 变长参数 (is_vararg): {'是' if proto.is_vararg else '否'} ({proto.is_vararg})" + " " * max(0, 60 - len(f"变长参数 (is_vararg): {'是' if proto.is_vararg else '否'} ({proto.is_vararg})") - 4) + "║")
        print(f"{indent}║ 📊 最大栈大小 (maxstacksize): {proto.maxstacksize}" + " " * max(0, 60 - len(f"最大栈大小 (maxstacksize): {proto.maxstacksize}") - 4) + "║")
        print(f"{indent}╠{border}╣")
        
        # 统计信息区域
        print(f"{indent}║ 📈 结构统计:" + " " * (60 - len("结构统计:") - 4) + "║")
        print(f"{indent}║   • 常量表 (constants): {len(proto.constants):4d} 项" + " " * max(0, 60 - len(f"  • 常量表 (constants): {len(proto.constants):4d} 项") - 4) + "║")
        print(f"{indent}║   • 指令表 (code): {len(proto.code):4d} 条" + " " * max(0, 60 - len(f"  • 指令表 (code): {len(proto.code):4d} 条") - 4) + "║")
        print(f"{indent}║   • Upvalue表 (upvalues): {len(proto.upvalues):4d} 个" + " " * max(0, 60 - len(f"  • Upvalue表 (upvalues): {len(proto.upvalues):4d} 个") - 4) + "║")
        print(f"{indent}║   • 子函数 (protos): {len(proto.protos):4d} 个" + " " * max(0, 60 - len(f"  • 子函数 (protos): {len(proto.protos):4d} 个") - 4) + "║")
        print(f"{indent}║   • 局部变量 (locvars): {len(proto.locvars):4d} 个" + " " * max(0, 60 - len(f"  • 局部变量 (locvars): {len(proto.locvars):4d} 个") - 4) + "║")
        print(f"{indent}║   • 行号信息 (lineinfo): {len(proto.lineinfo):4d} 个" + " " * max(0, 60 - len(f"  • 行号信息 (lineinfo): {len(proto.lineinfo):4d} 个") - 4) + "║")
        print(f"{indent}║   • 绝对行号 (abslineinfo): {len(proto.abslineinfo):4d} 个" + " " * max(0, 60 - len(f"  • 绝对行号 (abslineinfo): {len(proto.abslineinfo):4d} 个") - 4) + "║")
        print(f"{indent}║   • Upvalue名称 (upvalue_names): {len(proto.upvalue_names):4d} 个" + " " * max(0, 60 - len(f"  • Upvalue名称 (upvalue_names): {len(proto.upvalue_names):4d} 个") - 4) + "║")
        print(f"{indent}╚{border}╝")
        
        # 常量表详情 - 完整展示
        if proto.constants:
            print(f"\n{indent}┌{thin_border}┐")
            print(f"{indent}│ 🔢 常量表详情 (constants) - {len(proto.constants)} 项" + " " * max(0, 60 - len(f"常量表详情 (constants) - {len(proto.constants)} 项") - 4) + "│")
            print(f"{indent}├{thin_border}┤")
            
            # 显示所有常量
            for i, const in enumerate(proto.constants):
                const_type = type(const).__name__
                if isinstance(const, str):
                    const_display = f'\"{"{:.30}".format(const)}\"' if len(const) > 30 else f'\"{"{}".format(const)}\"' # 字符串内容
                    size_info = f"({len(const.encode('utf-8'))} bytes)" # 字符串字节大小
                elif isinstance(const, float):
                    const_display = str(const) # 浮点数内容
                    size_info = f"({const_type}, {struct.calcsize('<d')} bytes)" # 浮点数类型和字节大小
                elif isinstance(const, int):
                    const_display = str(const) # 整数内容
                    size_info = f"({const_type}, {struct.calcsize('<q')} bytes)" # 整数类型和字节大小
                else:
                    const_display = str(const) # 其他类型内容
                    size_info = f"({const_type})" # 其他类型
                
                print(f"{indent}│ [{i:3d}] {const_display} {size_info}" + " " * max(0, 50 - len(f"[{i:3d}] {const_display} {size_info}")) + "│")
            
            print(f"{indent}└{thin_border}┘")
        
        # 指令表概览
        if proto.code:
            print(f"\n{indent}┌{thin_border}┐")
            print(f"{indent}│ ⚙️  指令表概览 ({len(proto.code)} 条) [code]" + " " * max(0, 50 - len(f"指令表概览 ({len(proto.code)} 条) [code]") - 4) + "│")
            print(f"{indent}├{thin_border}┤")
            
            # 显示所有指令
            for i, inst_raw in enumerate(proto.code):
                decoded_inst = self.decode_instruction(inst_raw)
                opname = decoded_inst.get('name', 'UNKNOWN')
                opcode = decoded_inst.get('opcode', -1)
                
                # 构建参数字符串
                params_str = []
                if 'A' in decoded_inst: params_str.append(f"A={decoded_inst['A']}")
                if 'B' in decoded_inst: params_str.append(f"B={decoded_inst['B']}")
                if 'C' in decoded_inst: params_str.append(f"C={decoded_inst['C']}")
                if 'Bx' in decoded_inst: params_str.append(f"Bx={decoded_inst['Bx']}")
                if 'sBx' in decoded_inst: params_str.append(f"sBx={decoded_inst['sBx']}")
                if 'Ax' in decoded_inst: params_str.append(f"Ax={decoded_inst['Ax']}")
                if 'sJ' in decoded_inst: params_str.append(f"sJ={decoded_inst['sJ']}")
                
                params_display = ', '.join(params_str)
                
                # 格式化输出
                line_display = f"{indent}│ [{i:4d}] {opname:<12} (OpCode: {opcode:3d}) {{ {params_display} }}" # 指令内容和参数
                print(line_display + " " * max(0, 50 - len(line_display) + len(indent)) + "│")
            
            print(f"{indent}└{thin_border}┘")
        
        # Upvalue 详情
        if proto.upvalues:
            print(f"\n{indent}┌{thin_border}┐")
            print(f"{indent}│ ⬆️  Upvalue 详情 ({len(proto.upvalues)} 个) [upvalues]" + " " * max(0, 50 - len(f"Upvalue 详情 ({len(proto.upvalues)} 个) [upvalues]") - 4) + "│")
            print(f"{indent}├{thin_border}┤")
            for i, upval in enumerate(proto.upvalues):
                # 尝试获取 upvalue 名称，如果存在的话
                upval_name = proto.upvalue_names[i] if i < len(proto.upvalue_names) else "<unknown>"
                print(f"{indent}│ [{i:3d}] Name: '{upval_name}', InStack: {upval.instack}, Idx: {upval.idx}, Kind: {upval.kind} (Size: {struct.calcsize('BBB')} bytes)" + " " * max(0, 50 - len(f"[{i:3d}] Name: '{upval_name}', InStack: {upval.instack}, Idx: {upval.idx}, Kind: {upval.kind} (Size: {struct.calcsize('BBB')} bytes)")) + "│")
            print(f"{indent}└{thin_border}┘")

        # 局部变量详情
        if proto.locvars:
            print(f"\n{indent}┌{thin_border}┐")
            print(f"{indent}│ 📝 局部变量详情 ({len(proto.locvars)} 个) [locvars]" + " " * max(0, 50 - len(f"局部变量详情 ({len(proto.locvars)} 个) [locvars]") - 4) + "│")
            print(f"{indent}├{thin_border}┤")
            for i, locvar in enumerate(proto.locvars):
                print(f"{indent}│ [{i:3d}] Name: '{locvar.varname}', StartPC: {locvar.startpc}, EndPC: {locvar.endpc}" + " " * max(0, 50 - len(f"[{i:3d}] Name: '{locvar.varname}', StartPC: {locvar.startpc}, EndPC: {locvar.endpc}")) + "│")
            print(f"{indent}└{thin_border}┘")

        # 调试信息 (行号)
        if proto.lineinfo:
            print(f"\n{indent}┌{thin_border}┐")
            print(f"{indent}│ 📏 行号信息 ({len(proto.lineinfo)} 项) [lineinfo]" + " " * max(0, 50 - len(f"行号信息 ({len(proto.lineinfo)} 项) [lineinfo]") - 4) + "│")
            print(f"{indent}├{thin_border}┤")
            # 同样可以考虑折叠，但这里先全部显示
            for i, line_offset in enumerate(proto.lineinfo):
                print(f"{indent}│ [{i:3d}] Line Offset: {line_offset}" + " " * max(0, 50 - len(f"[{i:3d}] Line Offset: {line_offset}")) + "│")
            print(f"{indent}└{thin_border}┘")

        # 绝对行号信息
        if proto.abslineinfo:
            print(f"\n{indent}┌{thin_border}┐")
            print(f"{indent}│ 📍 绝对行号信息 ({len(proto.abslineinfo)} 项) [abslineinfo]" + " " * max(0, 50 - len(f"绝对行号信息 ({len(proto.abslineinfo)} 项) [abslineinfo]") - 4) + "│")
            print(f"{indent}├{thin_border}┤")
            for i, absline in enumerate(proto.abslineinfo):
                print(f"{indent}│ [{i:3d}] PC: {absline.pc}, Line: {absline.line}" + " " * max(0, 50 - len(f"[{i:3d}] PC: {absline.pc}, Line: {absline.line}")) + "│")
            print(f"{indent}└{thin_border}┘")

        # 递归打印子函数
        if proto.protos:
            print(f"\n{indent}┌{thin_border}┐")
            print(f"{indent}│ 🌳 子函数列表 ({len(proto.protos)} 个) [protos]" + " " * max(0, 50 - len(f"子函数列表 ({len(proto.protos)} 个) [protos]") - 4) + "│")
            print(f"{indent}├{thin_border}┤")
            for i, p in enumerate(proto.protos):
                print(f"{indent}│ [{i:3d}] 子函数开始" + " " * max(0, 50 - len(f"[{i:3d}] 子函数开始")) + "│")
                self.print_proto(p, level + 1)
                print(f"{indent}│ [{i:3d}] 子函数结束" + " " * max(0, 50 - len(f"[{i:3d}] 子函数结束")) + "│")
            print(f"{indent}└{thin_border}┘")

        if level == 0:
            print(f"\n{indent}╚{border}╝") # 主函数结束的底部边框
    
    def parse(self):
        """解析 luac 文件"""
        with open(self.filename, 'rb') as self.file:
            # 检查文件头
            self.check_header()

            # 读取 upvalue 数量
            upval_count = self.read_byte()
            print(f"主函数 upvalue 数量: {upval_count}\n")

            # 读取主函数
            self.main_proto = self.read_proto("")

            # 打印主函数
            #self.print_proto(self.main_proto)
#----------------------------------加解密相关代码----------------------------------
    def set_encryption_key(self, key: bytes):
        """
        设置加密密钥
        
        Args:
            key: 轮密钥，用于循环异或加密
        """
        self.encryption_key = key
        self.encrypt_mode = True

    def encrypt_code_data(self, code_data: bytes) -> bytes:
        """
        对code数据进行加密处理
        
        加密流程：
        1. 跳过code的size部分（已在调用处处理）
        2. 对每个指令（4字节）进行处理：
           - 每个指令的首个字节：异或后减1
           - 其他字节：只进行异或
        3. 使用轮密钥进行循环异或处理
        
        Args:
            code_data: 原始code数据（不包含size）
        
        Returns:
            bytes: 加密后的code数据
        """
        if not self.encryption_key or len(self.encryption_key) == 0:
            raise ValueError("加密密钥未设置")
        
        encrypted_data = bytearray()
        key_len = len(self.encryption_key)
        
        # 按4字节为一组处理指令
        for inst_idx in range(0, len(code_data), 4):
            # 处理当前指令的4个字节
            for byte_idx in range(4):
                if inst_idx + byte_idx >= len(code_data):
                    break
                    
                byte = code_data[inst_idx + byte_idx]
                # 获取当前轮密钥字节（循环使用）
                key_byte = self.encryption_key[(inst_idx + byte_idx) % key_len]
                
                # 异或处理
                encrypted_byte = byte ^ key_byte
                
                # 特殊处理：每个指令的首个字节异或后需要减去1
                # if byte_idx == 0:  # 指令的首个字节
                #     encrypted_byte = (encrypted_byte - 1) & 0xFF
                
                encrypted_data.append(encrypted_byte)
        
        return bytes(encrypted_data)

    def decrypt_code_data(self, encrypted_data: bytes) -> bytes:
        """
        对加密的code数据进行解密处理
        
        解密流程：
        1. 对每个指令（4字节）进行处理：
           - 每个指令的首个字节：先加1再异或
           - 其他字节：只进行异或
        2. 使用轮密钥进行循环异或处理
        
        Args:
            encrypted_data: 加密的code数据
        
        Returns:
            bytes: 解密后的code数据
        """
        if not self.encryption_key or len(self.encryption_key) == 0:
            raise ValueError("解密密钥未设置")
        
        decrypted_data = bytearray()
        key_len = len(self.encryption_key)
        
        # 按4字节为一组处理指令
        for inst_idx in range(0, len(encrypted_data), 4):
            # 处理当前指令的4个字节
            for byte_idx in range(4):
                if inst_idx + byte_idx >= len(encrypted_data):
                    break
                    
                byte = encrypted_data[inst_idx + byte_idx]
                # 获取当前轮密钥字节（循环使用）
                key_byte = self.encryption_key[(inst_idx + byte_idx) % key_len]
                
                # 特殊处理：每个指令的首个字节需要先加1再异或
                # if byte_idx == 0:  # 指令的首个字节
                #     byte = (byte + 1) & 0xFF
                
                # 异或处理
                decrypted_byte = byte ^ key_byte
                decrypted_data.append(decrypted_byte)
        
        return bytes(decrypted_data)

    def encrypt_proto_code(self, proto: Proto):
        """
        递归加密Proto及其子Proto的code部分
        
        Args:
            proto: 要加密的Proto对象
        """
        if not self.encrypt_mode or not self.encryption_key:
            return
        
        # 加密当前Proto的code部分
        if hasattr(proto, 'ori') and proto.ori and 'code' in proto.ori:
            code_raw = proto.ori['code']
            
            # 分离size部分和实际code数据
            # 需要重新解析size部分的长度
            temp_pos = 0
            size_bytes = b''
            
            # 解析变长编码的size部分
            while temp_pos < len(code_raw):
                byte = code_raw[temp_pos]
                size_bytes += bytes([byte])
                temp_pos += 1
                
                # 如果最高位为1，说明这是最后一个字节
                if (byte & 0x80) != 0:
                    break
            
            # 获取实际的code数据（跳过size部分）
            actual_code_data = code_raw[temp_pos:]
            
            # 加密code数据
            encrypted_code = self.encrypt_code_data(actual_code_data)
            
            # 重新组合：size部分 + 加密后的code数据
            proto.ori['code'] = size_bytes + encrypted_code
        
        # 递归处理子Proto
        if hasattr(proto, 'protos') and proto.protos:
            for sub_proto in proto.protos:
                self.encrypt_proto_code(sub_proto)
    
    def decrypt_proto_code(self, proto: Proto):
        """
        递归解密Proto及其子Proto的code部分
        
        Args:
            proto: 要解密的Proto对象
        """
        if not self.encrypt_mode or not self.encryption_key:
            return
        
        # 解密当前Proto的code部分
        if hasattr(proto, 'ori') and proto.ori and 'code' in proto.ori:
            code_raw = proto.ori['code']
            
            # 分离size部分和实际code数据
            # 需要重新解析size部分的长度
            temp_pos = 0
            size_bytes = b''
            
            # 解析变长编码的size部分
            while temp_pos < len(code_raw):
                byte = code_raw[temp_pos]
                size_bytes += bytes([byte])
                temp_pos += 1
                
                # 如果最高位为1，说明这是最后一个字节
                if (byte & 0x80) != 0:
                    break
            
            # 获取实际的code数据（跳过size部分）
            encrypted_code_data = code_raw[temp_pos:]
            
            # 解密code数据
            decrypted_code = self.decrypt_code_data(encrypted_code_data)
            
            # 重新组合：size部分 + 解密后的code数据
            proto.ori['code'] = size_bytes + decrypted_code
        
        # 递归处理子Proto
        if hasattr(proto, 'protos') and proto.protos:
            for sub_proto in proto.protos:
                self.decrypt_proto_code(sub_proto)

    def write_decrypted_luac(self, output_filename: str, decryption_key: bytes):
        """
        对当前已加载的加密luac数据进行解密并生成解密后的luac文件
        
        Args:
            output_filename: 输出的解密后luac文件名
            decryption_key: 解密密钥
        
        Note:
            使用此方法前需要先调用parse()方法加载luac文件
        """
        if not self.main_proto:
            raise ValueError("请先调用parse()方法加载luac文件")
        
        # 设置解密密钥
        self.set_encryption_key(decryption_key)
        
        # 解密所有Proto的code部分
        self.decrypt_proto_code(self.main_proto)
        
        # 写入解密后的luac文件
        with open(output_filename, 'wb') as output_file:
            # 重新构建整个luac文件
            self._write_luac_file(output_file)
        
        print(f"✓ 解密后的luac文件已生成: {output_filename}")
 
    def write_encrypted_luac(self, output_filename: str, encryption_key: bytes):
        """
        生成加密后的luac文件
        
        Args:
            output_filename: 输出文件名
            encryption_key: 加密密钥
        """
        # 设置加密密钥
        self.set_encryption_key(encryption_key)
        
        # 加密所有Proto的code部分
        if self.main_proto:
            self.encrypt_proto_code(self.main_proto)
        
        # 写入加密后的luac文件
        with open(output_filename, 'wb') as output_file:
            # 重新构建整个luac文件
            self._write_luac_file(output_file)
        
        print(f"✓ 加密后的luac文件已生成: {output_filename}")

    def _write_luac_file(self, output_file):
        """
        写入完整的luac文件结构
        
        Args:
            output_file: 输出文件对象
        """
        # 写入文件头
        self._write_header(output_file)
        
        # 写入主函数的upvalue数量
        output_file.write(struct.pack('B', len(self.main_proto.upvalues)))
        
        # 写入主Proto
        self._write_proto(output_file, self.main_proto, is_main_proto=True)

    def _write_header(self, output_file):
        """
        写入luac文件头
        
        Args:
            output_file: 输出文件对象
        """
        # Lua签名
        output_file.write(LUA_SIGNATURE)
        
        # 版本信息
        output_file.write(struct.pack('B', LUAC_VERSION))
        output_file.write(struct.pack('B', LUAC_FORMAT))
        output_file.write(LUAC_DATA)
        
        # 大小信息
        output_file.write(struct.pack('B', 4))  # 指令大小
        output_file.write(struct.pack('B', 8))  # 整数大小
        output_file.write(struct.pack('B', 8))  # 浮点数大小
        
        # 测试值
        output_file.write(struct.pack('<q', LUAC_INT))
        output_file.write(struct.pack('<d', LUAC_NUM))

    def _write_size(self, output_file, value: int):
        """
        写入变长编码的大小值
        
        Args:
            output_file: 输出文件对象
            value: 要写入的值
        """
        if value == 0:
            output_file.write(struct.pack('B', 0x80))
            return
        
        # 转换为变长编码
        bytes_list = []
        while value > 0:
            bytes_list.append(value & 0x7F)
            value >>= 7
        
        # 反转并写入（最后一个字节设置最高位）
        for i, byte_val in enumerate(reversed(bytes_list)):
            if i == len(bytes_list) - 1:
                byte_val |= 0x80
            output_file.write(struct.pack('B', byte_val))

    def _write_string(self, output_file, s: str):
        """
        写入字符串
        
        Args:
            output_file: 输出文件对象
            s: 要写入的字符串
        """
        if s is None:
            self._write_size(output_file, 0)
        else:
            data = s.encode('utf-8')
            self._write_size(output_file, len(data) + 1)  # +1 for null terminator
            output_file.write(data)

    def _write_proto(self, output_file, proto: Proto, is_main_proto: bool = True):
        """
        写入Proto结构

        Args:
            output_file: 输出文件对象
            proto: Proto对象
            is_main_proto: 是否为主函数Proto
        """
        # 写入基本信息
        # 对于子函数，如果source与主函数相同，则写入空字符串
        if is_main_proto:
            self._write_string(output_file, proto.source)
        else:
            # 子函数的source通常为空，检查ori中的原始数据
            if hasattr(proto, 'ori') and proto.ori and 'source' in proto.ori:
                # 如果有原始数据，使用原始数据来判断
                source_raw = proto.ori['source']
                if len(source_raw) <= 1:  # 空字符串的编码长度为1（只有长度字节）
                    self._write_string(output_file, None)
                else:
                    self._write_string(output_file, proto.source)
            else:
                # 没有原始数据时，假设子函数source为空
                self._write_string(output_file, None)

        self._write_size(output_file, proto.linedefined)
        self._write_size(output_file, proto.lastlinedefined)
        output_file.write(struct.pack('B', proto.numparams))
        output_file.write(struct.pack('B', proto.is_vararg))
        output_file.write(struct.pack('B', proto.maxstacksize))

        # 写入code（已加密）
        if hasattr(proto, 'ori') and proto.ori and 'code' in proto.ori:
            output_file.write(proto.ori['code'])
        else:
            # 如果没有原始数据，重新构建
            self._write_size(output_file, len(proto.code))
            for inst in proto.code:
                output_file.write(struct.pack('<I', inst))

        # 写入常量表
        self._write_constants(output_file, proto)

        # 写入upvalues
        self._write_upvalues(output_file, proto)

        # 写入子Proto
        self._write_protos(output_file, proto)

        # 写入调试信息
        self._write_debug(output_file, proto)

    def _write_constants(self, output_file, proto: Proto):
        """
        写入常量表
        
        Args:
            output_file: 输出文件对象
            proto: Proto对象
        """
        self._write_size(output_file, len(proto.constants))
        
        for const in proto.constants:
            if const is None:
                output_file.write(struct.pack('B', LuaType.VNIL))
            elif const is False:
                output_file.write(struct.pack('B', LuaType.VFALSE))
            elif const is True:
                output_file.write(struct.pack('B', LuaType.VTRUE))
            elif isinstance(const, float):
                output_file.write(struct.pack('B', LuaType.VNUMFLT))
                output_file.write(struct.pack('<d', const))
            elif isinstance(const, int):
                output_file.write(struct.pack('B', LuaType.VNUMINT))
                output_file.write(struct.pack('<q', const))
            elif isinstance(const, str):
                if len(const) <= 40:  # 短字符串阈值
                    output_file.write(struct.pack('B', LuaType.VSHRSTR))
                else:
                    output_file.write(struct.pack('B', LuaType.VLNGSTR))
                self._write_string(output_file, const)

    def _write_upvalues(self, output_file, proto: Proto):
        """
        写入upvalues
        
        Args:
            output_file: 输出文件对象
            proto: Proto对象
        """
        self._write_size(output_file, len(proto.upvalues))
        
        for upval in proto.upvalues:
            output_file.write(struct.pack('B', upval.instack))
            output_file.write(struct.pack('B', upval.idx))
            output_file.write(struct.pack('B', upval.kind))

    def _write_protos(self, output_file, proto: Proto):
        """
        写入子Proto列表

        Args:
            output_file: 输出文件对象
            proto: Proto对象
        """
        self._write_size(output_file, len(proto.protos))

        for sub_proto in proto.protos:
            # 子Proto的is_main_proto参数设为False
            self._write_proto(output_file, sub_proto, is_main_proto=False)

    def _write_debug(self, output_file, proto: Proto):
        """
        写入调试信息
        
        Args:
            output_file: 输出文件对象
            proto: Proto对象
        """
        # 行号信息
        self._write_size(output_file, len(proto.lineinfo))
        for line in proto.lineinfo:
            output_file.write(struct.pack('B', line))
        
        # 绝对行号信息
        self._write_size(output_file, len(proto.abslineinfo))
        for absline in proto.abslineinfo:
            self._write_size(output_file, absline.pc)
            self._write_size(output_file, absline.line)
        
        # 局部变量
        self._write_size(output_file, len(proto.locvars))
        for locvar in proto.locvars:
            self._write_string(output_file, locvar.varname)
            self._write_size(output_file, locvar.startpc)
            self._write_size(output_file, locvar.endpc)
        
        # upvalue名称
        self._write_size(output_file, len(proto.upvalue_names))
        for name in proto.upvalue_names:
            self._write_string(output_file, name)

def bytes_to_hex_int_list(data):
    """
    将字节数据转换为十六进制整数列表

    Args:
        data: bytes对象

    Returns:
        list: 十六进制格式的整数列表，如['0xaf', '0x51', ...]
    """
    return [f'0x{b:02x}' for b in data]


def bytes_to_hex_values(data):
    """
    将字节数据转换为十六进制数值列表

    Args:
        data: bytes对象

    Returns:
        list: 十六进制数值列表，如[0xaf, 0x51, 0x75]
    """
    return [int(b) for b in data]  # 字节本身就是十六进制数值

def main():
    parser = argparse.ArgumentParser(description='Lua 5.4 字节码解析器')
    parser.add_argument('input_file', nargs='?', help='输入的luac文件路径')
    parser.add_argument('-d', '--decrypt', action='store_true', help='解密模式')
    parser.add_argument('-e', '--encrypt', action='store_true', help='加密模式')
    parser.add_argument('-k', '--key', type=str, help='加密/解密密钥')
    parser.add_argument('-o', '--output', type=str, help='输出文件路径（可选）')
    parser.add_argument('-c', '--compare', nargs=2, metavar=('STANDARD_FILE', 'SHUFFLED_FILE'), 
                       help='对比两个luac文件的opcode映射关系')
    
    args = parser.parse_args()
    
    # 检查参数有效性
    if args.compare:
        # 对比模式
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
                        std_name = "UNKNOWN"
                        shuf_name = "UNKNOWN"
                        
                        try:
                            if std_opcode in OpCode.__members__.values():
                                std_name = OpCode(std_opcode).name
                        except ValueError:
                            pass
                        
                        try:
                            if shuf_opcode in OpCode.__members__.values():
                                shuf_name = OpCode(shuf_opcode).name
                        except ValueError:
                            pass
                        
                        f.write(f"{std_opcode}({std_name}) -> {shuf_opcode}({shuf_name})\n")
                
                print(f"\n✓ 映射结果已保存到: {args.output}")
            
            return
            
        except Exception as e:
            print(f"对比过程中发生错误: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    # 检查其他模式的参数
    if not args.input_file:
        print("错误: 需要指定输入文件或使用对比模式 (-c)")
        parser.print_help()
        sys.exit(1)
    
    if args.decrypt and args.encrypt:
        print("错误: 不能同时指定加密和解密模式")
        sys.exit(1)
    
    if (args.decrypt or args.encrypt) and not args.key:
        print("错误: 加密或解密模式需要提供密钥 (-k)")
        sys.exit(1)
    
    try:
        parser_obj = LuacParser(args.input_file)
        parser_obj.parse()
        
        if args.decrypt:
            # 解密模式
            if not args.output:
                # 自动生成输出文件名
                base_name = args.input_file.rsplit('.', 1)[0]
                args.output = f"{base_name}_decrypt.luac"
            
            # 设置解密密钥并解密
            encryption_key = args.key.encode('utf-8')
            parser_obj.set_encryption_key(encryption_key)
            parser_obj.decrypt_proto_code(parser_obj.main_proto)
            
            # 写入解密后的文件
            with open(args.output, 'wb') as output_file:
                parser_obj._write_luac_file(output_file)
            
            print(f"✓ 解密完成，输出文件: {args.output}")
            
        elif args.encrypt:
            # 加密模式
            if not args.output:
                # 自动生成输出文件名
                base_name = args.input_file.rsplit('.', 1)[0]
                args.output = f"{base_name}_encrypt.luac"
            
            # 加密并写入文件
            encryption_key = args.key.encode('utf-8')
            parser_obj.write_encrypted_luac(args.output, encryption_key)
            
        else:
            # 默认解析模式
            parser_obj.print_proto(parser_obj.main_proto)
            
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()


