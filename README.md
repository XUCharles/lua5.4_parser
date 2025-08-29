# Lua 5.4 Bytecode Parser

A powerful Lua 5.4 bytecode parsing, encryption/decryption, and opcode comparison tool.

## Features

### 🔍 Bytecode Parsing
- Complete parsing of Lua 5.4 bytecode file structure
- Support for Proto, constants, instructions, debug info, and all components
- Detailed instruction disassembly and formatted output
- Recursive parsing of nested functions (sub-Protos)

### 🔐 Encryption/Decryption
- Support for luac file encryption and decryption
- Custom key-based code segment encryption
- Maintains file structure integrity
- Batch processing support

### 📊 OpCode Comparison Analysis
- Compare opcode mappings between two luac files
- Identify VMs with shuffled opcode orders
- Generate detailed mapping tables and statistics
- Recursive analysis of all sub-functions

## Requirements

- Python 3.7+
- No additional dependencies

## Usage

### Basic Parsing
```bash
# Parse luac file
python luaparse.py gametest.luac
```

### Encryption
```bash
# Encrypt luac file
python luaparse.py -e input.luac -k "your_encryption_key" -o encrypted.luac
```

### Decryption
```bash
# Decrypt luac file
python luaparse.py -d encrypted.luac -k "your_encryption_key" -o decrypted.luac
```

### OpCode Comparison
```bash
# Compare opcode mappings between two luac files
python luaparse.py -c standard.luac shuffled.luac -o mapping.txt
```

## Command Line Arguments

| Argument | Description |
|----------|-------------|
| `input_file` | Input luac file path |
| `-d, --decrypt` | Decryption mode |
| `-e, --encrypt` | Encryption mode |
| `-k, --key` | Encryption/decryption key |
| `-o, --output` | Output file path |
| `-c, --compare` | Compare opcode mappings between two luac files |

## Output Examples

### Parsing Output
```
============================================================
Lua 5.4 Bytecode File Analysis Results
============================================================

📁 File Information:
   Path: gametest.luac
   Size: 1234 bytes
   Signature: ✓ Valid (ESC Lua)
   Version: ✓ 5.4 (0x54)
   Format: ✓ Official (0x00)

🎯 Main Function Proto:
┌──────────────────────────────────────────────────────┐
│ 📋 Basic Information                                 │
├──────────────────────────────────────────────────────┤
│ Source: @gametest.lua                                │
│ Lines: 0-0                                           │
│ Params: 0, Vararg: 1, MaxStack: 2                   │
└──────────────────────────────────────────────────────┘
```

### OpCode Comparison Output
```
============================================================
OPCODE COMPARISON ANALYSIS
============================================================

Parsing standard file: standard.luac
Parsing shuffled file: shuffled.luac

Standard file instruction count: 156
Shuffled file instruction count: 156

------------------------------------------------------------
OPCODE MAPPING RELATIONSHIPS
------------------------------------------------------------
Standard OpCode  Shuffled OpCode  Standard Name   Mapped Name
------------------------------------------------------------
0               42              MOVE            MOVE
1               15              LOADI           LOADI
3               28              LOADK           LOADK
...
```

## Technical Features

### Supported Lua 5.4 Features
- ✅ New instruction format (7-bit opcode)
- ✅ Variable-length integer encoding
- ✅ New constant type tags
- ✅ Absolute line number information
- ✅ To-be-closed variables

### Instruction Parsing
- Support for all 83 Lua 5.4 instructions
- Complete parameter parsing (A, B, C, Bx, sBx, Ax, sJ)
- Instruction mode recognition (iABC, iABx, iAsBx, iAx, isJ)

### Encryption Algorithm
- XOR encryption algorithm
- Support for custom key lengths
- Cyclic key usage
- Maintains instruction boundary integrity

## Project Structure

```
luaParser/
├── luaparse.py          # Main program file
├── README.md            # Project documentation (Chinese)
├── README_EN.md         # Project documentation (English)
├── Luac54.bt           # 010 Editor template file
├── gametest.luac       # Test file
└── *.luac              # Other test files
```

## Core Classes and Methods

### LuacParser Class
- `parse()`: Parse luac file
- `decrypt_luac_file()`: Decrypt luac file
- `encrypt_luac_file()`: Encrypt luac file
- `compare_opcodes()`: Compare opcode mappings
- `decode_instruction()`: Instruction decoding

### Data Structures
- `Proto`: Function prototype
- `Upvalue`: Upvalue information
- `LocVar`: Local variable
- `AbsLineInfo`: Absolute line number information

## Development Guide

### Adding New Features
1. Add new methods to the `LuacParser` class
2. Add command line arguments in the `main()` function
3. Update documentation

### Debugging Tips
- Use `-v` parameter for verbose output
- Check raw byte data in the `ori` dictionary
- Compare with 010 Editor template parsing results

## License

MIT License

## Contributing

Issues and Pull Requests are welcome!

## Changelog

### v1.0.0
- Initial release
- Basic luac parsing functionality
- Added encryption/decryption features
- Implemented opcode comparison analysis

---

**Note**: This tool is for educational and research purposes only. Please comply with relevant laws and regulations.