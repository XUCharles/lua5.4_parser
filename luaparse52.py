#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lua 5.2 字节码解析器
基于 010 Editor Luac52.bt 模板实现
支持解析和反汇编 Lua 5.2 字节码文件
"""

import struct
import sys
import json
import argparse
from typing import List, Dict, Any, Optional, Union
from enum import IntEnum
from dataclasses import dataclass


# Lua 5.2 常量定义
LUA_SIGNATURE = b'\x1bLua'
LUAC_VERSION = 0x52
LUAC_FORMAT = 0


class LuaType(IntEnum):
    """Lua 数据类型枚举"""
    LUA_TNIL = 0
    LUA_TBOOLEAN = 1
    LUA_TLIGHTUSERDATA = 2
    LUA_TNUMBER = 3
    LUA_TSTRING = 4
    LUA_TTABLE = 5
    LUA_TFUNCTION = 6
    LUA_TUSERDATA = 7
    LUA_TTHREAD = 8
    LUA_NUMTAGS = 9
    
    # Lua 5.2 特定类型
    LUA_TLCL = (LUA_TFUNCTION | (0 << 4))  # Lua closure
    LUA_TLCF = (LUA_TFUNCTION | (1 << 4))  # light C function
    LUA_TCCL = (LUA_TFUNCTION | (2 << 4))  # C closure
    
    LUA_TSHRSTR = (LUA_TSTRING | (0 << 4))  # short strings
    LUA_TLNGSTR = (LUA_TSTRING | (1 << 4))  # long strings
    
    LUA_TNUMFLT = (LUA_TNUMBER | (0 << 4))  # float numbers
    LUA_TNUMINT = (LUA_TNUMBER | (1 << 4))  # integer numbers


class OpCode(IntEnum):
    """Lua 5.2 操作码枚举"""
    OP_MOVE = 0      # A B     R(A) := R(B)
    OP_LOADK = 1     # A Bx    R(A) := Kst(Bx)
    OP_LOADKX = 2    # A       R(A) := Kst(extra arg)
    OP_LOADBOOL = 3  # A B C   R(A) := (Bool)B; if (C) pc++
    OP_LOADNIL = 4   # A B     R(A), R(A+1), ..., R(A+B) := nil
    OP_GETUPVAL = 5  # A B     R(A) := UpValue[B]
    
    OP_GETTABUP = 6  # A B C   R(A) := UpValue[B][RK(C)]
    OP_GETTABLE = 7  # A B C   R(A) := R(B)[RK(C)]
    
    OP_SETTABUP = 8  # A B C   UpValue[A][RK(B)] := RK(C)
    OP_SETUPVAL = 9  # A B     UpValue[B] := R(A)
    OP_SETTABLE = 10 # A B C   R(A)[RK(B)] := RK(C)
    
    OP_NEWTABLE = 11 # A B C   R(A) := {} (size = B,C)
    
    OP_SELF = 12     # A B C   R(A+1) := R(B); R(A) := R(B)[RK(C)]
    
    OP_ADD = 13      # A B C   R(A) := RK(B) + RK(C)
    OP_SUB = 14      # A B C   R(A) := RK(B) - RK(C)
    OP_MUL = 15      # A B C   R(A) := RK(B) * RK(C)
    OP_DIV = 16      # A B C   R(A) := RK(B) / RK(C)
    OP_MOD = 17      # A B C   R(A) := RK(B) % RK(C)
    OP_POW = 18      # A B C   R(A) := RK(B) ^ RK(C)
    OP_UNM = 19      # A B     R(A) := -R(B)
    OP_NOT = 20      # A B     R(A) := not R(B)
    OP_LEN = 21      # A B     R(A) := length of R(B)
    
    OP_CONCAT = 22   # A B C   R(A) := R(B).. ... ..R(C)
    
    OP_JMP = 23      # A sBx   pc+=sBx; if (A) close all upvalues >= R(A - 1)
    OP_EQ = 24       # A B C   if ((RK(B) == RK(C)) ~= A) then pc++
    OP_LT = 25       # A B C   if ((RK(B) <  RK(C)) ~= A) then pc++
    OP_LE = 26       # A B C   if ((RK(B) <= RK(C)) ~= A) then pc++
    
    OP_TEST = 27     # A C     if not (R(A) <=> C) then pc++
    OP_TESTSET = 28  # A B C   if (R(B) <=> C) then R(A) := R(B) else pc++
    
    OP_CALL = 29     # A B C   R(A), ... ,R(A+C-2) := R(A)(R(A+1), ... ,R(A+B-1))
    OP_TAILCALL = 30 # A B C   return R(A)(R(A+1), ... ,R(A+B-1))
    OP_RETURN = 31   # A B     return R(A), ... ,R(A+B-2)
    
    OP_FORLOOP = 32  # A sBx   R(A)+=R(A+2); if R(A) <?= R(A+1) then { pc+=sBx; R(A+3)=R(A) }
    OP_FORPREP = 33  # A sBx   R(A)-=R(A+2); pc+=sBx
    
    OP_TFORCALL = 34 # A C     R(A+3), ... ,R(A+2+C) := R(A)(R(A+1), R(A+2))
    OP_TFORLOOP = 35 # A sBx   if R(A+1) ~= nil then { R(A)=R(A+1); pc += sBx }
    
    OP_SETLIST = 36  # A B C   R(A)[(C-1)*FPF+i] := R(A+i), 1 <= i <= B
    
    OP_CLOSURE = 37  # A Bx    R(A) := closure(KPROTO[Bx])
    
    OP_VARARG = 38   # A B     R(A), R(A+1), ..., R(A+B-2) = vararg
    
    OP_EXTRAARG = 39 # Ax      extra (larger) argument for previous opcode


# 指令格式常量
SIZE_C = 9
SIZE_B = 9
SIZE_Bx = SIZE_C + SIZE_B
SIZE_A = 8
SIZE_Ax = SIZE_C + SIZE_B + SIZE_A
SIZE_OP = 6

POS_OP = 0
POS_A = POS_OP + SIZE_OP
POS_C = POS_A + SIZE_A
POS_B = POS_C + SIZE_C
POS_Bx = POS_C
POS_Ax = POS_A

MAXARG_Bx = (1 << SIZE_Bx) - 1
MAXARG_sBx = MAXARG_Bx >> 1

# RK 常量
BITRK = 1 << (SIZE_B - 1)
MAXINDEXRK = BITRK - 1

# SETLIST 常量
LFIELDS_PER_FLUSH = 50


@dataclass
class Instruction:
    """Lua 5.2 指令类"""
    inst: int
    pc: int
    opcode: OpCode = None
    a: int = 0
    b: int = 0
    c: int = 0
    bx: int = 0
    sbx: int = 0
    ax: int = 0
    
    def __post_init__(self):
        """初始化后处理，计算指令参数"""
        self.opcode = OpCode(self._get_opcode(self.inst))
        self.a = self._get_arg_a(self.inst)
        self.b = self._get_arg_b(self.inst)
        self.c = self._get_arg_c(self.inst)
        self.bx = self._get_arg_bx(self.inst)
        self.sbx = self._get_arg_sbx(self.inst)
        self.ax = self._get_arg_ax(self.inst)
    
    @staticmethod
    def _get_opcode(inst: int) -> int:
        """获取操作码"""
        return (inst >> POS_OP) & ((1 << SIZE_OP) - 1)
    
    @staticmethod
    def _get_arg_a(inst: int) -> int:
        """获取参数A"""
        return (inst >> POS_A) & ((1 << SIZE_A) - 1)
    
    @staticmethod
    def _get_arg_b(inst: int) -> int:
        """获取参数B"""
        return (inst >> POS_B) & ((1 << SIZE_B) - 1)
    
    @staticmethod
    def _get_arg_c(inst: int) -> int:
        """获取参数C"""
        return (inst >> POS_C) & ((1 << SIZE_C) - 1)
    
    @staticmethod
    def _get_arg_bx(inst: int) -> int:
        """获取参数Bx"""
        return (inst >> POS_Bx) & ((1 << SIZE_Bx) - 1)
    
    @staticmethod
    def _get_arg_sbx(inst: int) -> int:
        """获取参数sBx"""
        return Instruction._get_arg_bx(inst) - MAXARG_sBx
    
    @staticmethod
    def _get_arg_ax(inst: int) -> int:
        """获取参数Ax"""
        return (inst >> POS_Ax) & ((1 << SIZE_Ax) - 1)
    
    @staticmethod
    def is_k(x: int) -> bool:
        """测试是否为常量"""
        return (x & BITRK) != 0
    
    @staticmethod
    def index_k(r: int) -> int:
        """获取常量索引"""
        return r & ~BITRK


@dataclass
class LocalVar:
    """局部变量"""
    varname: str
    startpc: int
    endpc: int


@dataclass
class Upvalue:
    """上值描述符"""
    name: str
    instack: int
    idx: int


@dataclass
class Proto:
    """Lua 函数原型"""
    # 头部信息
    linedefined: int = 0
    lastlinedefined: int = 0
    numparams: int = 0
    is_vararg: int = 0
    maxstacksize: int = 0
    
    # 数据列表
    code: List[Instruction] = None
    constants: List[Any] = None
    protos: List['Proto'] = None
    upvalues: List[Upvalue] = None
    source: str = ""
    lineinfo: List[int] = None
    locvars: List[LocalVar] = None
    upvalue_names: List[str] = None
    
    def __post_init__(self):
        """初始化后处理"""
        if self.code is None:
            self.code = []
        if self.constants is None:
            self.constants = []
        if self.protos is None:
            self.protos = []
        if self.upvalues is None:
            self.upvalues = []
        if self.lineinfo is None:
            self.lineinfo = []
        if self.locvars is None:
            self.locvars = []
        if self.upvalue_names is None:
            self.upvalue_names = []


class Lua52Parser:
    """Lua 5.2 字节码解析器"""
    
    def __init__(self, data: bytes):
        """
        初始化解析器
        
        Args:
            data: 字节码数据
        """
        self.data = data
        self.pos = 0
        self.endian = '<'  # 默认小端序
        
        # 头部信息
        self.version = 0
        self.format = 0
        self.size_int = 4
        self.size_size_t = 8
        self.size_instruction = 4
        self.size_lua_number = 8
        self.lua_num_valid = 0
        
        # 主函数原型
        self.main_proto: Optional[Proto] = None
    
    def _read_byte(self) -> int:
        """读取一个字节"""
        if self.pos >= len(self.data):
            raise ValueError("Unexpected end of data")
        value = self.data[self.pos]
        self.pos += 1
        return value
    
    def _read_bytes(self, count: int) -> bytes:
        """读取指定数量的字节"""
        if self.pos + count > len(self.data):
            raise ValueError("Unexpected end of data")
        value = self.data[self.pos:self.pos + count]
        self.pos += count
        return value
    
    def _read_int32(self) -> int:
        """读取32位整数"""
        data = self._read_bytes(4)
        return struct.unpack(f'{self.endian}I', data)[0]
    
    def _read_int64(self) -> int:
        """读取64位整数"""
        data = self._read_bytes(8)
        return struct.unpack(f'{self.endian}Q', data)[0]
    
    def _read_double(self) -> float:
        """读取双精度浮点数"""
        data = self._read_bytes(8)
        return struct.unpack(f'{self.endian}d', data)[0]
    
    def _read_size_t(self) -> int:
        """读取size_t类型"""
        if self.size_size_t == 4:
            return self._read_int32()
        elif self.size_size_t == 8:
            return self._read_int64()
        else:
            raise ValueError(f"Unsupported size_t size: {self.size_size_t}")
    
    def _read_string(self) -> str:
        """读取字符串"""
        size = self._read_size_t()
        if size == 0:
            return ""
        
        # Lua 5.2 字符串包含结尾的 null 字符
        string_data = self._read_bytes(size)
        if string_data[-1] == 0:
            string_data = string_data[:-1]
        
        try:
            return string_data.decode('utf-8')
        except UnicodeDecodeError:
            return string_data.decode('latin-1')
    
    def parse(self) -> Proto:
        """
        解析字节码
        
        Returns:
            主函数原型
        """
        self._parse_header()
        self.main_proto = self._parse_proto()
        return self.main_proto
    
    def _parse_header(self):
        """解析文件头"""
        # 检查签名
        signature = self._read_bytes(4)
        if signature != LUA_SIGNATURE:
            raise ValueError("Invalid Lua bytecode signature")
        
        # 读取版本信息
        self.version = self._read_byte()
        if self.version != LUAC_VERSION:
            raise ValueError(f"Unsupported Lua version: 0x{self.version:02x}")
        
        self.format = self._read_byte()
        
        # 读取字节序
        endian_flag = self._read_byte()
        if endian_flag == 1:
            self.endian = '<'  # 小端序
        elif endian_flag == 0:
            self.endian = '>'  # 大端序
        else:
            raise ValueError(f"Invalid endian flag: {endian_flag}")
        
        # 读取类型大小
        self.size_int = self._read_byte()
        self.size_size_t = self._read_byte()
        self.size_instruction = self._read_byte()
        self.size_lua_number = self._read_byte()
        self.lua_num_valid = self._read_byte()
        
        # Lua 5.2 特有的尾部数据
        luac_tail = self._read_bytes(6)
        expected_tail = b'\x19\x93\r\n\x1a\n'
        if luac_tail != expected_tail:
            raise ValueError("Invalid luac tail data")
    
    def _parse_proto(self) -> Proto:
        """解析函数原型"""
        proto = Proto()
        
        # 解析头部
        proto.linedefined = self._read_int32()
        proto.lastlinedefined = self._read_int32()
        proto.numparams = self._read_byte()
        proto.is_vararg = self._read_byte()
        proto.maxstacksize = self._read_byte()
        
        # 解析指令
        self._parse_code(proto)
        
        # 解析常量
        self._parse_constants(proto)
        
        # 解析子函数
        self._parse_protos(proto)
        
        # 解析上值
        self._parse_upvalues(proto)
        
        # 解析源文件名
        proto.source = self._read_string()
        
        # 解析行号信息
        self._parse_lineinfo(proto)
        
        # 解析局部变量
        self._parse_locvars(proto)
        
        # 解析上值名称
        self._parse_upvalue_names(proto)
        
        return proto
    
    def _parse_code(self, proto: Proto):
        """解析指令代码"""
        sizecode = self._read_int32()
        
        for pc in range(sizecode):
            if self.size_instruction == 4:
                inst_value = self._read_int32()
            else:
                raise ValueError(f"Unsupported instruction size: {self.size_instruction}")
            
            instruction = Instruction(inst_value, pc + 1)
            proto.code.append(instruction)
    
    def _parse_constants(self, proto: Proto):
        """解析常量表"""
        sizek = self._read_int32()
        
        for _ in range(sizek):
            const_type = LuaType(self._read_byte())
            
            if const_type == LuaType.LUA_TNIL:
                value = None
            elif const_type == LuaType.LUA_TBOOLEAN:
                value = bool(self._read_byte())
            elif const_type in (LuaType.LUA_TNUMBER, LuaType.LUA_TNUMFLT):
                value = self._read_double()
            elif const_type == LuaType.LUA_TNUMINT:
                # Lua 5.2 中整数也存储为double
                value = int(self._read_double())
            elif const_type in (LuaType.LUA_TSTRING, LuaType.LUA_TSHRSTR, LuaType.LUA_TLNGSTR):
                value = self._read_string()
            else:
                raise ValueError(f"Unsupported constant type: {const_type}")
            
            proto.constants.append(value)
    
    def _parse_protos(self, proto: Proto):
        """解析子函数"""
        sizep = self._read_int32()
        
        for _ in range(sizep):
            sub_proto = self._parse_proto()
            proto.protos.append(sub_proto)
    
    def _parse_upvalues(self, proto: Proto):
        """解析上值描述符"""
        sizeupvalues = self._read_int32()
        
        for _ in range(sizeupvalues):
            instack = self._read_byte()
            idx = self._read_byte()
            upval = Upvalue("", instack, idx)
            proto.upvalues.append(upval)
    
    def _parse_lineinfo(self, proto: Proto):
        """解析行号信息"""
        sizelineinfo = self._read_int32()
        
        for _ in range(sizelineinfo):
            line = self._read_int32()
            proto.lineinfo.append(line)
    
    def _parse_locvars(self, proto: Proto):
        """解析局部变量"""
        sizelocvars = self._read_int32()
        
        for _ in range(sizelocvars):
            varname = self._read_string()
            startpc = self._read_int32()
            endpc = self._read_int32()
            locvar = LocalVar(varname, startpc, endpc)
            proto.locvars.append(locvar)
    
    def _parse_upvalue_names(self, proto: Proto):
        """解析上值名称"""
        size_upvalue_names = self._read_int32()
        
        for i in range(size_upvalue_names):
            name = self._read_string()
            proto.upvalue_names.append(name)
            # 更新对应的上值名称
            if i < len(proto.upvalues):
                proto.upvalues[i].name = name


class Lua52Dumper:
    """Lua 5.2 字节码输出器"""
    
    @staticmethod
    def dump_header(parser: 'Lua52Parser') -> str:
        """
        输出文件头信息
        
        Args:
            parser: 解析器对象
            
        Returns:
            格式化字符串
        """
        lines = []
        lines.append("HEADER INFORMATION")
        lines.append("-" * 60)
        lines.append(f"Signature: \\x1bLua")
        lines.append(f"Version: 0x{parser.version:02x} (Lua 5.2)")
        lines.append(f"Format: {parser.format}")
        lines.append(f"Endianness: {'little' if parser.endian == '<' else 'big'}")
        lines.append(f"Int size: {parser.size_int} bytes")
        lines.append(f"Size_t size: {parser.size_size_t} bytes")
        lines.append(f"Instruction size: {parser.size_instruction} bytes")
        lines.append(f"Number size: {parser.size_lua_number} bytes")
        lines.append(f"Integral flag: {parser.lua_num_valid}")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def dump_proto(proto: Proto, indent: int = 0) -> str:
        """
        输出函数原型信息
        
        Args:
            proto: 函数原型
            indent: 缩进级别
            
        Returns:
            格式化字符串
        """
        lines = []
        prefix = "  " * indent
        
        # 函数头部信息
        lines.append(f"{prefix}FUNCTION PROTOTYPE")
        lines.append(f"{prefix}{'-' * 60}")
        lines.append(f"{prefix}Source: {proto.source}")
        lines.append(f"{prefix}Lines: {proto.linedefined}-{proto.lastlinedefined}")
        lines.append(f"{prefix}Parameters: {proto.numparams}")
        lines.append(f"{prefix}Vararg: {bool(proto.is_vararg)}")
        lines.append(f"{prefix}Max stack: {proto.maxstacksize}")
        lines.append("")
        
        # 常量表
        if proto.constants:
            lines.append(f"{prefix}CONSTANTS ({len(proto.constants)}):")
            for i, const in enumerate(proto.constants):
                lines.append(f"{prefix}  {i}: {Lua52Dumper._format_constant(const)}")
            lines.append("")
        
        # 局部变量
        if proto.locvars:
            lines.append(f"{prefix}LOCALS ({len(proto.locvars)}):")
            for i, var in enumerate(proto.locvars):
                lines.append(f"{prefix}  {i}: {var.varname} (pc: {var.startpc}-{var.endpc})")
            lines.append("")
        
        # 上值
        if proto.upvalues:
            lines.append(f"{prefix}UPVALUES ({len(proto.upvalues)}):")
            for i, upval in enumerate(proto.upvalues):
                lines.append(f"{prefix}  {i}: {upval.name} (instack: {upval.instack}, idx: {upval.idx})")
            lines.append("")
        
        # 指令
        lines.append(f"{prefix}INSTRUCTIONS ({len(proto.code)}):")
        for i, inst in enumerate(proto.code):
            lines.append(f"{prefix}  {i:4d}: {Lua52Dumper._disassemble_instruction(inst, proto.constants)}")
        lines.append("")
        
        # 子函数
        for i, child in enumerate(proto.protos):
            lines.append(f"{prefix}CHILD FUNCTION {i}:")
            lines.append(Lua52Dumper.dump_proto(child, indent + 1))
        
        return "\n".join(lines)
    
    @staticmethod
    def _format_constant(const: Any) -> str:
        """格式化常量"""
        if const is None:
            return "nil"
        elif isinstance(const, bool):
            return "true" if const else "false"
        elif isinstance(const, (int, float)):
            return f"{const:.14g}"
        elif isinstance(const, str):
            return f'"{const}"'
        else:
            return f"<unknown type: {type(const)}>"
    
    @staticmethod
    def _disassemble_instruction(inst: Instruction, constants: List[Any]) -> str:
        """
        反汇编单条指令
        
        Args:
            inst: 指令对象
            constants: 常量表
            
        Returns:
            反汇编字符串
        """
        opcode = inst.opcode
        a, b, c = inst.a, inst.b, inst.c
        bx, sbx = inst.bx, inst.sbx
        pc = inst.pc
        
        # 获取RK参数的字符串表示
        def get_rk_string(rk: int) -> str:
            if Instruction.is_k(rk):
                idx = Instruction.index_k(rk)
                if idx < len(constants):
                    return f"K({idx})"
                else:
                    return f"K({idx})"
            else:
                return f"R({rk})"
        
        # 指令名称
        opname = opcode.name[3:]  # 去掉 "OP_" 前缀
        
        # 根据操作码生成反汇编字符串
        if opcode == OpCode.OP_MOVE:
            return f"{opname:<12} R({a}) R({b})                ; R({a}) := R({b})"
            
        elif opcode == OpCode.OP_LOADK:
            const_str = Lua52Dumper._format_constant(constants[bx]) if bx < len(constants) else "?"
            return f"{opname:<12} R({a}) K({bx})               ; R({a}) := {const_str}"
            
        elif opcode == OpCode.OP_LOADKX:
            return f"{opname:<12} R({a})                      ; R({a}) := Kst(extra arg)"
            
        elif opcode == OpCode.OP_EXTRAARG:
            return f"{opname:<12} {inst.ax}                        ; extra (larger) argument"
            
        elif opcode == OpCode.OP_LOADBOOL:
            bool_val = "true" if b else "false"
            jump_str = f"; if {c} then pc++" if c else ""
            return f"{opname:<12} R({a}) {b} {c}               ; R({a}) := {bool_val}{jump_str}"
            
        elif opcode == OpCode.OP_LOADNIL:
            return f"{opname:<12} R({a}) {b}                  ; R({a}) to R({a + b}) := nil"
            
        elif opcode == OpCode.OP_GETUPVAL:
            return f"{opname:<12} R({a}) U({b})               ; R({a}) := UpValue[{b}]"
            
        elif opcode == OpCode.OP_GETTABUP:
            rk_c = get_rk_string(c)
            return f"{opname:<12} R({a}) U({b}) {rk_c}         ; R({a}) := UpValue[{b}][{rk_c}]"
            
        elif opcode == OpCode.OP_GETTABLE:
            rk_c = get_rk_string(c)
            return f"{opname:<12} R({a}) R({b}) {rk_c}         ; R({a}) := R({b})[{rk_c}]"
            
        elif opcode == OpCode.OP_SETTABUP:
            rk_b = get_rk_string(b)
            rk_c = get_rk_string(c)
            return f"{opname:<12} U({a}) {rk_b} {rk_c}         ; UpValue[{a}][{rk_b}] := {rk_c}"
            
        elif opcode == OpCode.OP_SETUPVAL:
            return f"{opname:<12} R({a}) U({b})               ; UpValue[{b}] := R({a})"
            
        elif opcode == OpCode.OP_SETTABLE:
            rk_b = get_rk_string(b)
            rk_c = get_rk_string(c)
            return f"{opname:<12} R({a}) {rk_b} {rk_c}         ; R({a})[{rk_b}] := {rk_c}"
            
        elif opcode == OpCode.OP_NEWTABLE:
            return f"{opname:<12} R({a}) {b} {c}               ; R({a}) := {{}} (size = {b},{c})"
            
        elif opcode == OpCode.OP_SELF:
            rk_c = get_rk_string(c)
            return f"{opname:<12} R({a}) R({b}) {rk_c}         ; R({a+1}) := R({b}); R({a}) := R({b})[{rk_c}]"
            
        elif opcode in (OpCode.OP_ADD, OpCode.OP_SUB, OpCode.OP_MUL, OpCode.OP_DIV, OpCode.OP_MOD, OpCode.OP_POW):
            rk_b = get_rk_string(b)
            rk_c = get_rk_string(c)
            ops = {OpCode.OP_ADD: "+", OpCode.OP_SUB: "-", OpCode.OP_MUL: "*", 
                   OpCode.OP_DIV: "/", OpCode.OP_MOD: "%", OpCode.OP_POW: "^"}
            op_str = ops[opcode]
            return f"{opname:<12} R({a}) {rk_b} {rk_c}         ; R({a}) := {rk_b} {op_str} {rk_c}"
            
        elif opcode in (OpCode.OP_UNM, OpCode.OP_NOT, OpCode.OP_LEN):
            ops = {OpCode.OP_UNM: "-", OpCode.OP_NOT: "not ", OpCode.OP_LEN: "#"}
            op_str = ops[opcode]
            return f"{opname:<12} R({a}) R({b})               ; R({a}) := {op_str}R({b})"
            
        elif opcode == OpCode.OP_CONCAT:
            return f"{opname:<12} R({a}) R({b}) R({c})         ; R({a}) := R({b}).. ... ..R({c})"
            
        elif opcode == OpCode.OP_JMP:
            dest = pc + sbx
            close_str = f"; close all upvalues >= R({a-1})" if a > 0 else ""
            return f"{opname:<12} {a} {sbx}                   ; pc+={sbx} (to {dest}){close_str}"
            
        elif opcode in (OpCode.OP_EQ, OpCode.OP_LT, OpCode.OP_LE):
            rk_b = get_rk_string(b)
            rk_c = get_rk_string(c)
            ops = {OpCode.OP_EQ: "==", OpCode.OP_LT: "<", OpCode.OP_LE: "<="}
            op_str = ops[opcode]
            not_str = "not " if a else ""
            return f"{opname:<12} {a} {rk_b} {rk_c}           ; if {not_str}({rk_b} {op_str} {rk_c}) then pc++"
            
        elif opcode == OpCode.OP_TEST:
            not_str = "not " if not c else ""
            return f"{opname:<12} R({a}) {c}                  ; if {not_str}R({a}) then pc++"
            
        elif opcode == OpCode.OP_TESTSET:
            not_str = "" if c else "not "
            return f"{opname:<12} R({a}) R({b}) {c}           ; if {not_str}R({b}) then R({a}) := R({b}) else pc++"
            
        elif opcode == OpCode.OP_CALL:
            return f"{opname:<12} R({a}) {b} {c}               ; R({a}), ... ,R({a+c-2}) := R({a})(R({a+1}), ... ,R({a+b-1}))"
            
        elif opcode == OpCode.OP_TAILCALL:
            return f"{opname:<12} R({a}) {b} {c}               ; return R({a})(R({a+1}), ... ,R({a+b-1}))"
            
        elif opcode == OpCode.OP_RETURN:
            return f"{opname:<12} R({a}) {b}                  ; return R({a}), ... ,R({a+b-2})"
            
        elif opcode == OpCode.OP_FORLOOP:
            dest = pc + sbx
            return f"{opname:<12} R({a}) {sbx}                ; R({a})+=R({a+2}); if R({a}) <?= R({a+1}) then {{ pc+={sbx} (to {dest}); R({a+3})=R({a}) }}"
            
        elif opcode == OpCode.OP_FORPREP:
            dest = pc + sbx
            return f"{opname:<12} R({a}) {sbx}                ; R({a})-=R({a+2}); pc+={sbx} (to {dest})"
            
        elif opcode == OpCode.OP_TFORCALL:
            return f"{opname:<12} R({a}) {c}                  ; R({a+3}), ... ,R({a+2+c}) := R({a})(R({a+1}), R({a+2}))"
            
        elif opcode == OpCode.OP_TFORLOOP:
            dest = pc + sbx
            return f"{opname:<12} R({a}) {sbx}                ; if R({a+1}) ~= nil then {{ R({a})=R({a+1}); pc += {sbx} (to {dest}) }}"
            
        elif opcode == OpCode.OP_SETLIST:
            return f"{opname:<12} R({a}) {b} {c}               ; R({a})[(C-1)*FPF+i] := R({a}+i), 1 <= i <= B"
            
        elif opcode == OpCode.OP_CLOSURE:
            return f"{opname:<12} R({a}) {bx}                 ; R({a}) := closure(KPROTO[{bx}])"
            
        elif opcode == OpCode.OP_VARARG:
            return f"{opname:<12} R({a}) {b}                  ; R({a}), R({a+1}), ..., R({a+b-2}) = vararg"
            
        else:
            return f"{opname:<12} {a} {b} {c}                 ; unknown opcode"


class Lua52Analyzer:
    """Lua 5.2 字节码分析器"""
    
    @staticmethod
    def analyze_globals(proto: Proto, level: int = 0):
        """分析全局变量使用"""
        prefix = "  " * level
        globals_used = set()
        
        # 分析指令中的全局变量访问
        for inst in proto.code:
            if inst.opcode == OpCode.OP_GETTABUP and inst.b == 0:  # _ENV[key]
                if Instruction.is_k(inst.c):
                    idx = Instruction.index_k(inst.c)
                    if idx < len(proto.constants):
                        globals_used.add(proto.constants[idx])
            elif inst.opcode == OpCode.OP_SETTABUP and inst.a == 0:  # _ENV[key] = value
                if Instruction.is_k(inst.b):
                    idx = Instruction.index_k(inst.b)
                    if idx < len(proto.constants):
                        globals_used.add(proto.constants[idx])
        
        if globals_used:
            print(f"{prefix}Global variables used: {', '.join(str(g) for g in sorted(globals_used))}")
        
        # 递归分析子函数
        for i, child in enumerate(proto.protos):
            Lua52Analyzer.analyze_globals(child, level + 1)
    
    @staticmethod
    def analyze_strings(proto: Proto, level: int = 0):
        """分析字符串常量"""
        prefix = "  " * level
        strings = [const for const in proto.constants if isinstance(const, str)]
        
        if strings:
            print(f"{prefix}String constants ({len(strings)}): {', '.join(repr(s) for s in strings)}")
        
        # 递归分析子函数
        for child in proto.protos:
            Lua52Analyzer.analyze_strings(child, level + 1)
    
    @staticmethod
    def analyze_functions(proto: Proto, level: int = 0):
        """分析函数信息"""
        prefix = "  " * level
        
        print(f"{prefix}Function info:")
        print(f"{prefix}  Source: {proto.source}")
        print(f"{prefix}  Lines: {proto.linedefined}-{proto.lastlinedefined}")
        print(f"{prefix}  Parameters: {proto.numparams}")
        print(f"{prefix}  Instructions: {len(proto.code)}")
        print(f"{prefix}  Constants: {len(proto.constants)}")
        print(f"{prefix}  Child functions: {len(proto.protos)}")
        
        # 递归分析子函数
        for i, child in enumerate(proto.protos):
            print(f"{prefix}Child function {i}:")
            Lua52Analyzer.analyze_functions(child, level + 1)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='Lua 5.2 字节码解析器')
    parser.add_argument('input', help='输入的luac文件路径')
    parser.add_argument('--analyze', action='store_true', help='启用分析模式')
    
    args = parser.parse_args()
    
    try:
        # 读取字节码文件
        with open(args.input, 'rb') as f:
            data = f.read()
        
        # 解析字节码
        parser_obj = Lua52Parser(data)
        proto = parser_obj.parse()
        
        # 输出头部信息
        print(Lua52Dumper.dump_header(parser_obj))
        
        if args.analyze:
            # 分析模式
            print("ANALYSIS RESULTS")
            print("-" * 60)
            Lua52Analyzer.analyze_globals(proto)
            Lua52Analyzer.analyze_strings(proto)
            Lua52Analyzer.analyze_functions(proto)
        else:
            # 标准输出模式
            print(Lua52Dumper.dump_proto(proto))
            
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()