import json
import struct


class Assembler16Bit:
    def __init__(self, json_filepath):
        with open(json_filepath, 'r') as f:
            self.data = json.load(f)

        self.machine_code = bytearray()
        self.symbol_table = {}

        self.modes = {'AM': 0b00, 'AD': 0b01, 'AI': 0b10, 'AX': 0b11}

        # --- Clasa 1 (4 biți) ---
        self.opcodes_cls1 = {
            'MOV': 0b0000, 'ADD': 0b0001, 'SUB': 0b0010, 'CMP': 0b0011,
            'AND': 0b0100, 'OR': 0b0101, 'XOR': 0b0110
        }

        # --- Clasa 2 (10 biți) ---
        self.opcodes_cls2 = {
            'CLR': 0b1000000000, 'NEG': 0b1000000001, 'INC': 0b1000000010,
            'DEC': 0b1000000011, 'ASL': 0b1000000100, 'ASR': 0b1000000101,
            'LSR': 0b1000000110, 'ROL': 0b1000000111, 'ROR': 0b1000001000,
            'RLC': 0b1000001001, 'RRC': 0b1000001010, 'JMP': 0b1000001011,
            'CALL': 0b1000001100, 'PUSH': 0b1000001101, 'POP': 0b1000001110
        }

        # --- Clasa 3 (8 biți) ---
        self.opcodes_cls3 = {
            'BR': 0b11000000, 'BNE': 0b11000001, 'BEQ': 0b11000010,
            'BPL': 0b11000011, 'BMI': 0b11000100, 'BCS': 0b11000101,
            'BCC': 0b11000110, 'BVS': 0b11000111, 'BVC': 0b11001000
        }

        # --- Clasa 4 (16 biți) ---
        self.opcodes_cls4 = {
            'CLC': 0b1110000000000000,
            'CLV': 0b1110000000000001,
            'CLZ': 0b1110000000000010,
            'CLS': 0b1110000000000011,
            'CCC': 0b1110000000000111,
            'SEC': 0b1110000000001000,
            'SEV': 0b1110000000001001,
            'SEZ': 0b1110000000001010,
            'SES': 0b1110000000001011,  # Corectat din SEZ
            'SCC': 0b1110000000001100,
            'NOP': 0b1110000000001101,
            'RET': 0b1110000000001110,
            'RETI': 0b1110000000001111,
            'HALT': 0b1110000000010000,
            'WAIT': 0b1110000000010001,
            'PUSH PC': 0b1110000000010010,
            'POP PC': 0b1110000000010011,
            'PUSH FLAG': 0b1110000000010100,
            'POP FLAG': 0b1110000000010101
        }

    def _decode_operand(self, op_str):
        op_str = op_str.strip().upper()

        def valideaza_limita(numar):
            if not (0 <= numar <= 15):
                raise ValueError(f"Eroare: Valoarea {numar} depășește limita de 4 biți!")
            return numar

        if op_str.startswith('#') or op_str.isdigit():
            val = int(op_str.replace('#', '').replace('H', ''), 16) if 'H' in op_str else int(op_str.replace('#', ''))
            return self.modes['AM'], valideaza_limita(val)
        elif op_str.startswith('(') and op_str.endswith(')'):
            reg_num = int(op_str[1:-1].strip().replace('R', ''))
            return self.modes['AI'], valideaza_limita(reg_num)
        elif '(' in op_str and op_str.endswith(')'):
            reg_num = int(op_str.split('(')[1][:-1].strip().replace('R', ''))
            return self.modes['AX'], valideaza_limita(reg_num)
        elif op_str.startswith('R'):
            reg_num = int(op_str.replace('R', ''))
            return self.modes['AD'], valideaza_limita(reg_num)
        else:
            raise ValueError(f"Operand invalid -> {op_str}")

    def first_pass(self):
        instr_count = 0
        for item in self.data:
            if item['type'] == 'label':
                self.symbol_table[item['name']] = instr_count
            elif item['type'] == 'instruction':
                instr_count += 1

    def _translate_class_1(self, instr):
        opcode_val = self.opcodes_cls1[instr['opcode']]
        mad, rd = self._decode_operand(instr['operands'][0])
        mas, rs = self._decode_operand(instr['operands'][1])
        return (opcode_val << 12) | (mas << 10) | (rs << 6) | (mad << 4) | rd

    def _translate_class_2(self, instr):
        opcode_val = self.opcodes_cls2[instr['opcode']]
        mad, rd = self._decode_operand(instr['operands'][0])
        return (opcode_val << 6) | (mad << 4) | rd

    def _translate_class_3(self, instr, current_index):
        opcode_val = self.opcodes_cls3[instr['opcode']]
        label_name = instr['operands'][0]
        if label_name not in self.symbol_table:
            raise ValueError(f"Eroare: Eticheta '{label_name}' nu a fost definită!")

        target_index = self.symbol_table[label_name]
        offset = target_index - (current_index + 1)

        if not (-128 <= offset <= 127):
            raise ValueError(f"Eroare: Salt prea lung către '{label_name}'. Offset={offset}.")
        return (opcode_val << 8) | (offset & 0xFF)

    def assemble(self, output_filepath):
        self.first_pass()
        current_instr_index = 0

        for item in self.data:
            if item['type'] == 'instruction':
                op_name = item['opcode']
                operands = item['operands']

                # Construim numele complet pentru cazuri speciale (ex: "PUSH" și "PC" devin "PUSH PC")
                full_op_name = op_name
                if operands and operands[0] in ['PC', 'FLAG']:
                    full_op_name = f"{op_name} {operands[0]}"

                # Rutăm către clasa corectă
                if full_op_name in self.opcodes_cls4:
                    # Clasa 4 nu are nevoie de decodare de operanzi
                    binary_instr = self.opcodes_cls4[full_op_name]
                elif op_name in self.opcodes_cls1:
                    binary_instr = self._translate_class_1(item)
                elif op_name in self.opcodes_cls2:
                    binary_instr = self._translate_class_2(item)
                elif op_name in self.opcodes_cls3:
                    binary_instr = self._translate_class_3(item, current_instr_index)
                else:
                    raise ValueError(f"Eroare: Instrucțiune necunoscută: {full_op_name}")

                self.machine_code.extend(struct.pack('>H', binary_instr))
                current_instr_index += 1

        with open(output_filepath, 'wb') as f:
            f.write(self.machine_code)
        print(f"-> Succes absolut! Binarul complet a fost generat în: {output_filepath}")