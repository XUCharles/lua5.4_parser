#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LuaJIT 字节码解析器 - 完整版本
支持 LuaJIT 2.0/2.1 字节码格式解析
基于 010 Editor LuaJIT.bt 模板实现

版本: 2.0
"""

import struct
import sys
import argparse
import json
from dataclasses import dataclass, field, asdict
from typing import List, Tuple, Dict, Any, Union

# LuaJIT 文件头常量
LUAJIT_SIGNATURE = b'\x1bLJ'
LUAJIT_VERSION = 1

# 字节码格式常量
BCDUMP_F_BE = 0x01  # 大端序
BCDUMP_F_STRIP = 0x02  # 去除调试信息
BCDUMP_F_FFI = 0x04  # 包含 FFI

# 原型标志
BCDUMP_F_CHILD = 0x01  # 有子原型
BCDUMP_F_VARARG = 0x02  # 可变参数
BCDUMP_F_FFI_PROTO = 0x04  # FFI 原型
BCDUMP_F_NOJIT = 0x08  # 禁用 JIT
BCDUMP_F_ILOOP = 0x10  # 有内部循环

# 常量类型标记
BCDUMP_KGC_CHILD = 0
BCDUMP_KGC_TAB = 1
BCDUMP_KGC_I64 = 2
BCDUMP_KGC_U64 = 3
BCDUMP_KGC_COMPLEX = 4
BCDUMP_KGC_STR = 5

# 表常量类型
BCDUMP_KTAB_NIL = 0
BCDUMP_KTAB_FALSE = 1
BCDUMP_KTAB_TRUE = 2
BCDUMP_KTAB_INT = 3
BCDUMP_KTAB_NUM = 4
BCDUMP_KTAB_STR = 5

# 变量名类型
VARNAME_END = 0
VARNAME_FOR_IDX = 1
VARNAME_FOR_STOP = 2
VARNAME_FOR_STEP = 3
VARNAME_FOR_GEN = 4
VARNAME_FOR_STATE = 5
VARNAME_FOR_CTL = 6
VARNAME_MAX = 7


# LuaJIT 操作码枚举
class BCOp:
    """LuaJIT 字节码操作码定义"""
    ISLT = 0;
    ISGE = 1;
    ISLE = 2;
    ISGT = 3
    ISEQV = 4;
    ISNEV = 5;
    ISEQS = 6;
    ISNES = 7
    ISEQN = 8;
    ISNEN = 9;
    ISEQP = 10;
    ISNEP = 11
    ISTC = 12;
    ISFC = 13;
    IST = 14;
    ISF = 15
    MOV = 16;
    NOT = 17;
    UNM = 18;
    LEN = 19
    ADDVN = 20;
    SUBVN = 21;
    MULVN = 22;
    DIVVN = 23;
    MODVN = 24
    ADDNV = 25;
    SUBNV = 26;
    MULNV = 27;
    DIVNV = 28;
    MODNV = 29
    ADDVV = 30;
    SUBVV = 31;
    MULVV = 32;
    DIVVV = 33;
    MODVV = 34
    POW = 35;
    CAT = 36;
    KSTR = 37;
    KCDATA = 38;
    KSHORT = 39
    KNUM = 40;
    KPRI = 41;
    KNIL = 42;
    UGET = 43;
    USETV = 44
    USETS = 45;
    USETN = 46;
    USETP = 47;
    UCLO = 48;
    FNEW = 49
    TNEW = 50;
    TDUP = 51;
    GGET = 52;
    GSET = 53;
    TGETV = 54
    TGETS = 55;
    TGETB = 56;
    TSETV = 57;
    TSETS = 58;
    TSETB = 59
    TSETM = 60;
    CALLM = 61;
    CALL = 62;
    CALLMT = 63;
    CALLT = 64
    ITERC = 65;
    ITERN = 66;
    VARG = 67;
    ISNEXT = 68;
    RETM = 69
    RET = 70;
    RET0 = 71;
    RET1 = 72;
    FORI = 73;
    JFORI = 74
    FORL = 75;
    IFORL = 76;
    JFORL = 77;
    ITERL = 78;
    IITERL = 79
    JITERL = 80;
    LOOP = 81;
    ILOOP = 82;
    JLOOP = 83;
    JMP = 84
    FUNCF = 85;
    IFUNCF = 86;
    JFUNCF = 87;
    FUNCV = 88;
    IFUNCV = 89
    JFUNCV = 90;
    FUNCC = 91;
    FUNCCW = 92

    # 操作码名称映射
    NAMES = [
        'ISLT', 'ISGE', 'ISLE', 'ISGT', 'ISEQV', 'ISNEV', 'ISEQS', 'ISNES',
        'ISEQN', 'ISNEN', 'ISEQP', 'ISNEP', 'ISTC', 'ISFC', 'IST', 'ISF',
        'MOV', 'NOT', 'UNM', 'LEN', 'ADDVN', 'SUBVN', 'MULVN', 'DIVVN', 'MODVN',
        'ADDNV', 'SUBNV', 'MULNV', 'DIVNV', 'MODNV', 'ADDVV', 'SUBVV', 'MULVV',
        'DIVVV', 'MODVV', 'POW', 'CAT', 'KSTR', 'KCDATA', 'KSHORT', 'KNUM',
        'KPRI', 'KNIL', 'UGET', 'USETV', 'USETS', 'USETN', 'USETP', 'UCLO',
        'FNEW', 'TNEW', 'TDUP', 'GGET', 'GSET', 'TGETV', 'TGETS', 'TGETB',
        'TSETV', 'TSETS', 'TSETB', 'TSETM', 'CALLM', 'CALL', 'CALLMT', 'CALLT',
        'ITERC', 'ITERN', 'VARG', 'ISNEXT', 'RETM', 'RET', 'RET0', 'RET1',
        'FORI', 'JFORI', 'FORL', 'IFORL', 'JFORL', 'ITERL', 'IITERL', 'JITERL',
        'LOOP', 'ILOOP', 'JLOOP', 'JMP', 'FUNCF', 'IFUNCF', 'JFUNCF', 'FUNCV',
        'IFUNCV', 'JFUNCV', 'FUNCC', 'FUNCCW'
    ]


@dataclass
class Proto:
    """LuaJIT 函数原型数据结构"""
    # 原型头信息
    size: int = 0
    flags: int = 0
    numparams: int = 0
    framesize: int = 0
    numuv: int = 0
    numkgc: int = 0
    numkn: int = 0
    numbc: int = 0

    # 调试信息
    debuginfo_size: int = 0
    firstline: int = 0
    numline: int = 0

    # 字节码和数据
    bytecode: List[int] = field(default_factory=list)
    uv_data: List[int] = field(default_factory=list)
    constants_gc: List[Tuple[str, Any]] = field(default_factory=list)
    constants_num: List[Union[int, float]] = field(default_factory=list)

    # 调试信息
    lineinfo: List[int] = field(default_factory=list)
    uvnames: List[str] = field(default_factory=list)
    varnames: List[str] = field(default_factory=list)


class LuaJITParser:
    """LuaJIT 字节码解析器"""

    def __init__(self, data: bytes):
        """
        初始化解析器

        Args:
            data: 字节码文件数据
        """
        self.data = data
        self.pos = 0
        self.size = len(data)
        self.flags = 0
        self.header_info = {}

    def read_byte(self) -> int:
        """读取单个字节"""
        if self.pos >= self.size:
            raise Exception("文件读取超出边界")
        val = self.data[self.pos]
        self.pos += 1
        return val

    def read_uint16(self) -> int:
        """读取 16 位无符号整数"""
        if self.pos + 2 > self.size:
            raise Exception("文件读取超出边界")
        val = struct.unpack('<H', self.data[self.pos:self.pos + 2])[0]
        self.pos += 2
        return val

    def read_uint32(self) -> int:
        """读取 32 位无符号整数"""
        if self.pos + 4 > self.size:
            raise Exception("文件读取超出边界")
        val = struct.unpack('<I', self.data[self.pos:self.pos + 4])[0]
        self.pos += 4
        return val

    def read_uleb128(self) -> int:
        """
        读取 ULEB128 编码的整数

        Returns:
            解码后的整数值
        """
        result = 0
        shift = 0
        while True:
            if self.pos >= self.size:
                raise Exception("ULEB128 读取超出边界")
            byte = self.data[self.pos]
            self.pos += 1
            result |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                break
            shift += 7
            if shift >= 35:  # 防止无限循环
                raise Exception("ULEB128 编码过长")
        return result

    def read_uleb128_33(self) -> Tuple[Tuple[int, int], bool]:
        """
        读取 33 位 ULEB128 编码的数值常量

        Returns:
            ((lo, hi), is_num): 低位、高位和是否为数字类型的元组
        """
        if self.pos >= self.size:
            raise Exception("ULEB128_33 读取超出边界")

        first_byte = self.data[self.pos]
        is_num = (first_byte & 0x01) != 0

        # 读取低位部分
        lo = (first_byte >> 1) & 0x3F
        self.pos += 1

        if (first_byte >> 1) > 0x3F:
            # 需要读取更多字节
            shift = 6
            while True:
                if self.pos >= self.size:
                    raise Exception("ULEB128_33 读取超出边界")
                byte = self.data[self.pos]
                self.pos += 1
                lo |= (byte & 0x7F) << shift
                if (byte & 0x80) == 0:
                    break
                shift += 7
                if shift >= 32:
                    break

        hi = 0
        if is_num:
            # 如果是数字类型，读取高位
            hi = self.read_uleb128()

        return (lo, hi), is_num

    def read_string(self, length: int) -> str:
        """
        读取指定长度的字符串

        Args:
            length: 字符串长度

        Returns:
            解码后的字符串
        """
        if self.pos + length > self.size:
            raise Exception("字符串读取超出边界")
        data = self.data[self.pos:self.pos + length]
        self.pos += length
        try:
            return data.decode('utf-8')
        except UnicodeDecodeError:
            return data.decode('latin-1')

    def read_header(self) -> Dict[str, Any]:
        """
        读取 LuaJIT 文件头

        Returns:
            包含头部信息的字典
        """
        # 检查签名
        if self.pos + 3 > self.size:
            raise Exception("文件太小，无法读取签名")

        signature = self.data[self.pos:self.pos + 3]
        if signature != LUAJIT_SIGNATURE:
            raise Exception(f"无效的 LuaJIT 签名: {signature}")
        self.pos += 3

        # 读取版本
        version = self.read_byte()
        if version != LUAJIT_VERSION:
            print(f"警告: 版本不匹配，期望 {LUAJIT_VERSION}，实际 {version}")

        # 读取标志
        self.flags = self.read_uleb128()

        # 解析标志
        is_big_endian = bool(self.flags & BCDUMP_F_BE)
        is_stripped = bool(self.flags & BCDUMP_F_STRIP)
        has_ffi = bool(self.flags & BCDUMP_F_FFI)

        # 读取源文件名（如果未去除调试信息）
        source_name = ""
        if not is_stripped:
            name_len = self.read_uleb128()
            if name_len > 0:
                source_name = self.read_string(name_len)

        # 存储头部信息
        self.header_info = {
            'signature': signature.hex(),
            'version': version,
            'flags': self.flags,
            'is_big_endian': is_big_endian,
            'is_stripped': is_stripped,
            'has_ffi': has_ffi,
            'source_name': source_name
        }

        return self.header_info

    def read_table(self) -> Dict[str, Any]:
        """
        读取表常量

        Returns:
            表数据字典
        """
        array_count = self.read_uleb128()
        hash_count = self.read_uleb128()

        table_data = {
            'array_items': [],
            'hash_items': []
        }

        # 读取数组部分
        for i in range(array_count):
            item = self.read_table_item()
            table_data['array_items'].append(item)

        # 读取哈希部分
        for i in range(hash_count):
            key = self.read_table_item()
            value = self.read_table_item()
            table_data['hash_items'].append((key, value))

        return table_data

    def read_table_item(self) -> Any:
        """
        读取表项

        Returns:
            表项值
        """
        item_type = self.read_uleb128()

        if item_type >= BCDUMP_KTAB_STR:
            # 字符串
            str_len = item_type - BCDUMP_KTAB_STR
            return self.read_string(str_len)
        elif item_type == BCDUMP_KTAB_INT:
            # 整数
            return self.read_uleb128()
        elif item_type == BCDUMP_KTAB_NUM:
            # 数字
            lo = self.read_uleb128()
            hi = self.read_uleb128()
            # 组合成 double
            num_bits = lo | (hi << 32)
            return struct.unpack('<d', struct.pack('<Q', num_bits))[0]
        elif item_type == BCDUMP_KTAB_TRUE:
            return True
        elif item_type == BCDUMP_KTAB_FALSE:
            return False
        elif item_type == BCDUMP_KTAB_NIL:
            return None
        else:
            raise Exception(f"未知的表项类型: {item_type}")

    def read_proto(self) -> Proto:
        """
        读取函数原型

        Returns:
            Proto 对象
        """
        proto = Proto()

        # 读取原型大小
        proto.size = self.read_uleb128()

        if proto.size == 0:
            return proto

        # 记录开始位置
        start_pos = self.pos

        # 原型头
        proto.flags = self.read_byte()
        proto.numparams = self.read_byte()
        proto.framesize = self.read_byte()
        proto.numuv = self.read_byte()
        proto.numkgc = self.read_uleb128()
        proto.numkn = self.read_uleb128()
        proto.numbc = self.read_uleb128()

        # 调试信息（如果有）
        if not (self.flags & BCDUMP_F_STRIP):
            proto.debuginfo_size = self.read_uleb128()
            proto.firstline = self.read_uleb128()
            proto.numline = self.read_uleb128()

        # 按照 010 Editor 模板的顺序读取数据

        # 1. 字节码指令
        proto.bytecode = []
        for i in range(proto.numbc):
            inst = self.read_uint32()
            proto.bytecode.append(inst)

        # 2. Upvalue 数据
        proto.uv_data = []
        for i in range(proto.numuv):
            uv = self.read_uint16()
            proto.uv_data.append(uv)

        # 3. GC 常量（复杂常量）
        proto.constants_gc = []
        for i in range(proto.numkgc):
            const_type = self.read_uleb128()

            if const_type >= BCDUMP_KGC_STR:
                # 字符串
                str_len = const_type - BCDUMP_KGC_STR
                str_data = self.read_string(str_len)
                proto.constants_gc.append(('string', str_data))
            elif const_type == BCDUMP_KGC_TAB:
                # 表
                tab = self.read_table()
                proto.constants_gc.append(('table', tab))
            elif const_type == BCDUMP_KGC_CHILD:
                # 子原型引用 - 根据 010 Editor 模板，这里不读取额外数据
                # 只是一个引用标记，实际的子原型在别处定义
                proto.constants_gc.append(('child_ref', None))
            elif const_type == BCDUMP_KGC_I64:
                # int64
                lo = self.read_uleb128()
                hi = self.read_uleb128()
                val = lo | (hi << 32)
                if val >= (1 << 63):
                    val -= (1 << 64)  # 转换为有符号
                proto.constants_gc.append(('i64', val))
            elif const_type == BCDUMP_KGC_U64:
                # uint64
                lo = self.read_uleb128()
                hi = self.read_uleb128()
                val = lo | (hi << 32)
                proto.constants_gc.append(('u64', val))
            elif const_type == BCDUMP_KGC_COMPLEX:
                # 复数
                real_lo = self.read_uleb128()
                real_hi = self.read_uleb128()
                imag_lo = self.read_uleb128()
                imag_hi = self.read_uleb128()
                real_bits = real_lo | (real_hi << 32)
                imag_bits = imag_lo | (imag_hi << 32)
                real = struct.unpack('<d', struct.pack('<Q', real_bits))[0]
                imag = struct.unpack('<d', struct.pack('<Q', imag_bits))[0]
                proto.constants_gc.append(('complex', (real, imag)))
            else:
                raise Exception(f"未知的 GC 常量类型: {const_type}")

        # 4. 数值常量
        proto.constants_num = []
        for i in range(proto.numkn):
            (lo, hi), is_num = self.read_uleb128_33()

            if is_num:
                # 浮点数
                num_bits = lo | (hi << 32)
                num = struct.unpack('<d', struct.pack('<Q', num_bits))[0]
                proto.constants_num.append(num)
            else:
                # 整数
                if lo >= (1 << 31):
                    lo -= (1 << 32)  # 转换为有符号
                proto.constants_num.append(lo)

        # 调试信息
        if not (self.flags & BCDUMP_F_STRIP) and proto.debuginfo_size > 0:
            # 行号信息
            if proto.numline > 0:
                proto.lineinfo = []
                if proto.numline >= 65536:
                    # 32 位行号
                    for i in range(proto.numbc):
                        line = self.read_uint32()
                        proto.lineinfo.append(line)
                elif proto.numline >= 256:
                    # 16 位行号
                    for i in range(proto.numbc):
                        line = self.read_uint16()
                        proto.lineinfo.append(line)
                else:
                    # 8 位行号
                    for i in range(proto.numbc):
                        line = self.read_byte()
                        proto.lineinfo.append(line)

            # Upvalue 名称
            for i in range(proto.numuv):
                name_len = self.read_uleb128()
                if name_len > 0:
                    name = self.read_string(name_len)
                    proto.uvnames.append(name)
                else:
                    proto.uvnames.append("")

            # 变量名
            while self.pos < self.size:
                var_type = self.read_byte()
                if var_type == VARNAME_END:
                    break

                if var_type >= VARNAME_MAX:
                    # 变量名字符串
                    name_len = var_type - VARNAME_MAX
                    if name_len > 0:
                        name = self.read_string(name_len)
                        proto.varnames.append(name)
                else:
                    # 特殊变量类型
                    proto.varnames.append(f"<type_{var_type}>")

                # 读取作用域信息
                start_addr = self.read_uleb128()
                end_addr = self.read_uleb128()

        return proto

    def parse(self) -> Tuple[Dict[str, Any], List[Proto]]:
        """
        解析 LuaJIT 字节码文件

        Returns:
            (header_info, protos): 头部信息和所有函数原型列表
        """
        header = self.read_header()
        protos = []

        # 继续读取直到文件结束，每个 Proto 都有自己的大小字段
        while self.pos < self.size:
            try:
                proto = self.read_proto()
                if proto.size == 0:
                    # 遇到空 Proto，可能是文件结束标记
                    break
                protos.append(proto)
            except Exception as e:
                # 如果读取失败，可能已经到达文件末尾
                print(f"警告: 读取 Proto 时出错: {e}")
                break

        return header, protos


class LuaJITDumper:
    """LuaJIT 字节码输出器"""

    @staticmethod
    def dump_header(header_info: Dict[str, Any]) -> None:
        """
        输出头部信息

        Args:
            header_info: 头部信息字典
        """
        print("=" * 60)
        print("LuaJIT 字节码文件头部信息")
        print("=" * 60)
        print(f"签名 (signature):       {header_info['signature']}")
        print(f"版本 (version):         {header_info['version']}")
        print(f"标志 (flags):           0x{header_info['flags']:02x}")
        print(f"大端序 (is_big_endian): {'是' if header_info['is_big_endian'] else '否'}")
        print(f"去除调试 (is_stripped): {'是' if header_info['is_stripped'] else '否'}")
        print(f"包含FFI (has_ffi):      {'是' if header_info['has_ffi'] else '否'}")
        if header_info['source_name']:
            print(f"源文件 (source_name):   {header_info['source_name']}")
        print()

    @staticmethod
    def decode_instruction(inst: int, pc: int) -> str:
        """
        解码字节码指令

        Args:
            inst: 32位指令
            pc: 程序计数器

        Returns:
            格式化的指令字符串
        """
        opcode = inst & 0xFF
        a = (inst >> 8) & 0xFF
        c = (inst >> 16) & 0xFF
        b = (inst >> 24) & 0xFF
        d = (inst >> 16) & 0xFFFF

        if opcode < len(BCOp.NAMES):
            op_name = BCOp.NAMES[opcode]
        else:
            op_name = f"UNK_{opcode}"

        # 根据操作码类型格式化参数
        if opcode in [BCOp.JMP, BCOp.FORI, BCOp.FORL, BCOp.ITERL, BCOp.LOOP]:
            # 跳转指令使用 D 参数
            return f"{op_name:8} {a:3} {d:5}"
        elif opcode in [BCOp.KSTR, BCOp.KNUM, BCOp.KPRI, BCOp.KNIL]:
            # 常量指令
            return f"{op_name:8} {a:3} {d:5}"
        else:
            # 三参数指令
            return f"{op_name:8} {a:3} {b:3} {c:3}"

    @staticmethod
    def dump_proto(proto: Proto, level: int = 0) -> None:
        """
        输出函数原型信息

        Args:
            proto: 函数原型对象
            level: 嵌套层级
        """
        indent = "  " * level

        if proto.size == 0:
            print(f"{indent}空原型")
            return

        print(f"{indent}{'=' * 50}")
        print(f"{indent}函数原型 (Proto) - 层级 {level}")
        print(f"{indent}{'=' * 50}")
        print(f"{indent}大小 (size):         {proto.size}")
        print(f"{indent}标志 (flags):        0x{proto.flags:02x}")
        print(f"{indent}参数数量 (numparams): {proto.numparams}")
        print(f"{indent}栈帧大小 (framesize): {proto.framesize}")
        print(f"{indent}上值数量 (numuv):     {proto.numuv}")
        print(f"{indent}GC常量数 (numkgc):    {proto.numkgc}")
        print(f"{indent}数值常量数 (numkn):   {proto.numkn}")
        print(f"{indent}字节码数 (numbc):     {proto.numbc}")

        if not (proto.flags & BCDUMP_F_STRIP):
            print(f"{indent}首行号 (firstline):   {proto.firstline}")
            print(f"{indent}行数 (numline):       {proto.numline}")

        # 输出字节码指令
        if proto.bytecode:
            print(f"\n{indent}字节码指令 (bytecode):")
            print(f"{indent}{'PC':>4} {'指令':>8} {'A':>3} {'B':>3} {'C':>3} {'原始':>10} {'说明'}")
            print(f"{indent}{'-' * 60}")

            for i, inst in enumerate(proto.bytecode):
                pc = i + 1
                decoded = LuaJITDumper.decode_instruction(inst, pc)
                line_info = ""
                if i < len(proto.lineinfo):
                    line_info = f"行:{proto.lineinfo[i]}"

                print(f"{indent}{pc:4} {decoded} 0x{inst:08x} {line_info}")

        # 输出 GC 常量
        if proto.constants_gc:
            print(f"\n{indent}GC 常量 (constants_gc):")
            for i, (const_type, value) in enumerate(proto.constants_gc):
                if const_type == 'string':
                    print(f"{indent}  [{i}] 字符串 (string): \"{value}\"")
                elif const_type == 'table':
                    print(
                        f"{indent}  [{i}] 表 (table): {len(value['array_items'])} 数组项, {len(value['hash_items'])} 哈希项")
                elif const_type == 'child_ref':
                    print(f"{indent}  [{i}] 子原型引用 (child_ref)")
                elif const_type in ['i64', 'u64']:
                    print(f"{indent}  [{i}] {const_type.upper()}: {value}")
                elif const_type == 'complex':
                    real, imag = value
                    print(f"{indent}  [{i}] 复数 (complex): {real} + {imag}i")
                else:
                    print(f"{indent}  [{i}] {const_type}: {value}")

        # 输出数值常量
        if proto.constants_num:
            print(f"\n{indent}数值常量 (constants_num):")
            for i, num in enumerate(proto.constants_num):
                if isinstance(num, float):
                    print(f"{indent}  [{i}] 浮点数 (float): {num}")
                else:
                    print(f"{indent}  [{i}] 整数 (int): {num}")

        # 输出 Upvalue 信息
        if proto.uv_data:
            print(f"\n{indent}Upvalue 数据 (uv_data):")
            for i, uv in enumerate(proto.uv_data):
                name = proto.uvnames[i] if i < len(proto.uvnames) else f"uv_{i}"
                print(f"{indent}  [{i}] {name}: 0x{uv:04x}")

        # 输出变量名
        if proto.varnames:
            print(f"\n{indent}局部变量 (varnames):")
            for i, name in enumerate(proto.varnames):
                print(f"{indent}  [{i}] {name}")

        print()

    @staticmethod
    def dump_all_protos(protos: List[Proto]) -> None:
        """
        输出所有函数原型信息

        Args:
            protos: 函数原型列表
        """
        print(f"总共找到 {len(protos)} 个函数原型 (protos):")
        print()

        for i, proto in enumerate(protos):
            print(f"原型 (Proto) #{i + 1}:")
            LuaJITDumper.dump_proto(proto, level=0)

    @staticmethod
    def export_json(header_info: Dict[str, Any], protos: List[Proto]) -> str:
        """
        导出为 JSON 格式

        Args:
            header_info: 头部信息
            protos: 函数原型列表

        Returns:
            JSON 字符串
        """
        data = {
            'header': header_info,
            'protos': [asdict(proto) for proto in protos]
        }
        return json.dumps(data, indent=2, ensure_ascii=False)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='LuaJIT 字节码解析器')
    parser.add_argument('input', help='输入的 LuaJIT 字节码文件')
    parser.add_argument('-j', '--json', action='store_true', help='输出 JSON 格式')
    parser.add_argument('-o', '--output', help='输出文件路径')
    parser.add_argument('-v', '--verbose', action='store_true', help='详细输出')

    args = parser.parse_args()

    try:
        # 读取文件
        with open(args.input, 'rb') as f:
            data = f.read()

        # 解析字节码
        luajit_parser = LuaJITParser(data)
        header_info, protos = luajit_parser.parse()

        # 输出结果
        if args.json:
            # JSON 格式输出
            json_output = LuaJITDumper.export_json(header_info, protos)
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(json_output)
                print(f"JSON 输出已保存到: {args.output}")
            else:
                print(json_output)
        else:
            # 标准格式输出
            if args.output:
                import sys
                original_stdout = sys.stdout
                with open(args.output, 'w', encoding='utf-8') as f:
                    sys.stdout = f
                    LuaJITDumper.dump_header(header_info)
                    LuaJITDumper.dump_all_protos(protos)
                sys.stdout = original_stdout
                print(f"输出已保存到: {args.output}")
            else:
                LuaJITDumper.dump_header(header_info)
                LuaJITDumper.dump_all_protos(protos)

        print(f"\n解析完成! 文件大小: {len(data)} 字节, 找到 {len(protos)} 个函数原型 (protos)")

    except Exception as e:
        print(f"错误: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()