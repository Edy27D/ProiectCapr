import re
import json  # Importăm modulul JSON


class AsmParser:
    def __init__(self, filepath):
        self.raw_lines = []
        self.clean_lines = []
        self._load_file(filepath)
        self._clean_code()

    def _load_file(self, filepath):
        with open(filepath, 'r') as file:
            self.raw_lines = file.readlines()

    def _clean_code(self):
        for line in self.raw_lines:
            code_part = line.split(';')[0]
            clean_line = code_part.strip()
            if clean_line:
                self.clean_lines.append(clean_line)

    def parse(self):
        parsed_data = []
        for line in self.clean_lines:
            if line.endswith(':'):
                parsed_data.append({
                    'type': 'label',
                    'name': line[:-1]
                })
            else:
                parts = re.split(r'[\s,]+', line)
                opcode = parts[0].upper()
                operands = parts[1:] if len(parts) > 1 else []

                parsed_data.append({
                    'type': 'instruction',
                    'opcode': opcode,
                    'operands': operands
                })
        return parsed_data

    def save_to_file(self, data, output_filepath):
        with open(output_filepath, 'w') as file:
            # indent=4 face ca textul să fie formatat frumos, pe mai multe linii
            json.dump(data, file, indent=4)
        print(f"-> Succes! Rezultatul a fost salvat în fișierul: {output_filepath}")