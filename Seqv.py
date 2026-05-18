import struct


class Secventiator:
    def __init__(self):
        # --- Memoriile ---
        self.MPM = [0] * 65536  # Memoria Principală
        self.Micro_ROM = {}  # ROM de Control

        # --- Regiștrii Hardware ---
        self.R = [0] * 16  # R0 - R15
        self.PC = 0
        self.MAR = 0
        self.MDR = 0
        self.IR = 0
        self.SP = 65535  # Stack Pointer
        self.FLAG = 0  # Registrul de status
        self.Z_flag = 0  # Flag-ul de Zero pentru salturi conditionate

        # Regiștri ascunși pt procesor
        self.T = 0
        self.ADR = 0
        self.IVR = 0

        # --- Linii de control curente ---
        self.MPC = 0x00  # Micro-Program Counter
        self.MIR = {}  # Micro-Instruction Register

        # --- Magistrale ---
        self.S_Bus = 0
        self.D_Bus = 0
        self.R_Bus = 0

        self.halted = False

        self._incarca_micro_rom()

    def _incarca_micro_rom(self):
        #microprogram#
        self.Micro_ROM = {
            # --- CICLUL DE FETCH (Extragerea instrucțiunii din memorie) ---
            0x00: {'LABEL': 'IFCH', 'SBUS': 'PdPCs', 'RBUS': 'PmADR', 'MEM': 'READ', 'ALTE': '+2PC', 'SUCC': 'STEP',
                   'SALT': '0x01'},
            0x01: {'LABEL': 'IFCH_1', 'SBUS': 'PdMDRs', 'RBUS': 'PmIR', 'SUCC': 'JUMPI', 'SALT': 'ILLEGAL'},
            # ILLEGAL forțează decodificarea IR

            # --- RUTINE DE EXECUȚIE (Micro-operațiile pentru fiecare instrucțiune) ---
            0x1D: {'LABEL': 'MOV_IMM', 'SBUS': 'PdIMM', 'ALU': 'PASS_S', 'RBUS': 'PmRG', 'SUCC': 'JUMPI',
                   'SALT': 'IFCH'},
            0x1E: {'LABEL': 'MOV_REG', 'SBUS': 'PdRGs', 'ALU': 'PASS_S', 'RBUS': 'PmRG', 'SUCC': 'JUMPI',
                   'SALT': 'IFCH'},
            0x1A: {'LABEL': 'ADD_IMM', 'SBUS': 'PdIMM', 'DBUS': 'PdRGd', 'ALU': 'SUM', 'RBUS': 'PmRG', 'SUCC': 'JUMPI',
                   'SALT': 'IFCH'},
            0x1F: {'LABEL': 'ADD_REG', 'SBUS': 'PdRGs', 'DBUS': 'PdRGd', 'ALU': 'SUM', 'RBUS': 'PmRG', 'SUCC': 'JUMPI',
                   'SALT': 'IFCH'},
            0x20: {'LABEL': 'SUB', 'SBUS': 'PdRGsNeg', 'DBUS': 'PdRGd', 'ALU': 'SUM', 'RBUS': 'PmRG',
                   'ALTE': 'Cin,PdCONDaritm', 'SUCC': 'JUMPI', 'SALT': 'IFCH'},
            0x27: {'LABEL': 'INC', 'SBUS': 'Pd0s', 'DBUS': 'PdRGd', 'ALU': 'SUM', 'RBUS': 'PmRG',
                   'ALTE': 'Cin,PdCONDaritm', 'SUCC': 'JUMPI', 'SALT': 'IFCH'},
            0x28: {'LABEL': 'DEC', 'SBUS': 'Pd-1s', 'DBUS': 'PdRGd', 'ALU': 'SUM', 'RBUS': 'PmRG',
                   'ALTE': 'PdCONDaritm', 'SUCC': 'JUMPI', 'SALT': 'IFCH'},

            # --- SALTURI CONDIȚIONATE ---
            0x3A: {'LABEL': 'BNE', 'SUCC': 'BRANCH_BNE'},  # O comandă specială de decizie

            # --- OPERAȚII DIVERSE (Clasa 4) ---
            0x5E: {'LABEL': 'NOP', 'SUCC': 'JUMPI', 'SALT': 'IFCH'},
            0x60: {'LABEL': 'HALT', 'ALTE': 'A(0)BPO', 'SUCC': 'STEP', 'SALT': '0x61'},
            0x61: {'LABEL': 'HALT_2', 'SUCC': 'STEP', 'SALT': '0x61'},  # Oprește procesorul aici
        }

    def incarca_program_binar(self, filepath):
        """Încarcă .bin în Memoria Principală."""
        try:
            with open(filepath, 'rb') as f:
                continut = f.read()
            adresa = 0
            for i in range(0, len(continut), 2):
                chunk = continut[i:i + 2]
                if len(chunk) == 2:
                    self.MPM[adresa] = struct.unpack('>H', chunk)[0]
                    adresa += 1
            print(f"-> Program binar încărcat cu succes în MPM. ({adresa} instrucțiuni)")
        except FileNotFoundError:
            print("Eroare: Fișierul binar nu a fost găsit.")

    def _citeste_sbus(self):
        sursa = self.MIR.get('SBUS', 'NONE')
        if sursa == 'PdPCs':
            self.S_Bus = self.PC
        elif sursa == 'PdMDRs':
            self.S_Bus = self.MDR
        elif sursa == 'PdSPs':
            self.S_Bus = self.SP
        elif sursa == 'PdTs':
            self.S_Bus = self.T
        elif sursa == 'Pd0s':
            self.S_Bus = 0
        elif sursa == 'Pd-1s':
            self.S_Bus = 0xFFFF  # -1 în complement față de 2
        elif sursa == 'PdFLAGs':
            self.S_Bus = self.FLAG

        # --- Extragem valoarea din Registrul Sursă (Biții 6-9 din IR) ---
        elif sursa == 'PdRGs':
            reg_index = (self.IR >> 6) & 0xF
            self.S_Bus = self.R[reg_index]
        # --- LOGICA NOUĂ PENTRU SCĂDERE ---
        elif sursa == 'PdRGsNeg':
            reg_index = (self.IR >> 6) & 0xF
            # Inversăm biții cu '~' și aplicăm masca & 0xFFFF pentru a rămâne pe 16 biți
            self.S_Bus = (~self.R[reg_index]) & 0xFFFF

        # --- Extragem Valoarea Imediată (Biții 6-9 din IR) ---
        elif sursa == 'PdIMM':
            val_imediata = (self.IR >> 6) & 0xF
            self.S_Bus = val_imediata

        else:
            self.S_Bus = 0

    def _citeste_dbus(self):
        dest = self.MIR.get('DBUS', 'NONE')
        if dest == 'PdMDRd':
            self.D_Bus = self.MDR
        elif dest == 'PdPCd':
            self.D_Bus = self.PC
        elif dest == 'Pd0d':
            self.D_Bus = 0

        # --- Extragem valoarea din Registrul Destinație (Biții 0-3 din IR) ---
        elif dest == 'PdRGd':
            reg_index = self.IR & 0xF
            self.D_Bus = self.R[reg_index]

        else:
            self.D_Bus = 0

    def _executa_alu(self):
        op = self.MIR.get('ALU', 'NONE')
        if op == 'NONE' or op == 'PASS_S':
            self.R_Bus = self.S_Bus
        elif op == 'SUM':
            alte_ops = self.MIR.get('ALTE', '')
            cin = 1 if 'Cin' in alte_ops else 0
            self.R_Bus = (self.S_Bus + self.D_Bus + cin) & 0xFFFF
        elif op == 'AND':
            self.R_Bus = self.S_Bus & self.D_Bus
        elif op == 'OR':
            self.R_Bus = self.S_Bus | self.D_Bus
        elif op == 'XOR':
            self.R_Bus = self.S_Bus ^ self.D_Bus

        alte_ops = self.MIR.get('ALTE', '')
        if 'PdCONDaritm' in alte_ops or 'PdCONDlog' in alte_ops:
            self.Z_flag = 1 if self.R_Bus == 0 else 0

    def _scrie_rbus(self):
        dest = self.MIR.get('RBUS', 'NONE')
        if dest == 'PmADR':
            self.MAR = self.R_Bus
        elif dest == 'PmPC':
            self.PC = self.R_Bus
        elif dest == 'PmMDR':
            self.MDR = self.R_Bus
        elif dest == 'PmT':
            self.T = self.R_Bus
        elif dest == 'PmFLAG':
            self.FLAG = self.R_Bus
        elif dest == 'PmIR':
            self.IR = self.R_Bus  # Salvează instrucțiunea în IR

        # --- Scriem rezultatul în Registrul Destinație (Biții 0-3 din IR) ---
        elif dest == 'PmRG':
            reg_index = self.IR & 0xF
            self.R[reg_index] = self.R_Bus

    def _operatii_diverse(self):
        alte = self.MIR.get('ALTE', 'NONE')
        if '+2PC' in alte:
            self.PC = (self.PC + 1) & 0xFFFF
        if '-2SP' in alte:
            self.SP = (self.SP - 1) & 0xFFFF
        if '+2SP' in alte:
            self.SP = (self.SP + 1) & 0xFFFF

    def _operatii_memorie(self):
        mem_op = self.MIR.get('MEM', 'NONE')
        if mem_op == 'READ':
            self.MDR = self.MPM[self.MAR]
        elif mem_op == 'WRITE':
            self.MPM[self.MAR] = self.MDR

    def _calculeaza_urmatorul_mpc(self):
        succ = self.MIR.get('SUCC', 'STEP')
        salt = self.MIR.get('SALT', '0x00')

        if succ == 'STEP':
            if salt.startswith('0x'):
                self.MPC = int(salt, 16)
            else:
                self.MPC += 1

        elif succ == 'BRANCH_BNE':
            # Dacă rezultatul NU a fost zero (Z_flag == 0), facem saltul!
            if self.Z_flag == 0:
                offset = self.IR & 0xFF  # Luăm ultimii 8 biți
                if offset > 127: offset -= 256  # Transformăm în număr negativ dacă e cazul
                self.PC = (self.PC + offset) & 0xFFFF
            self.MPC = 0x00  # Ne întoarcem la Fetch indiferent dacă am sărit sau nu

        elif succ == 'JUMPI':
            # --- MAPPER-UL (DECODIFICATORUL HARDWARE) ---
            if salt == 'ILLEGAL':
                opcode_c1 = (self.IR >> 12) & 0xF
                opcode_c2 = (self.IR >> 6) & 0x3FF
                opcode_c3 = (self.IR >> 8) & 0xFF  # <-- ADAUGAT pentru Clasa 3
                opcode_c4 = self.IR

                mas = (self.IR >> 10) & 0x3  # Extragem Modul de Adresare Sursă

                # Rutare către microadresele din ROM
                if opcode_c1 == 0b0000:  # MOV
                    if mas == 0b00:
                        self.MPC = 0x1D  # MOV_IMM
                    else:
                        self.MPC = 0x1E  # MOV_REG
                elif opcode_c1 == 0b0001:
                    self.MPC = 0x1F  # ADD
                    if mas == 0b00:
                        self.MPC = 0x1A  # ADD_IMM (foloseste valoarea 8)
                    else:
                        self.MPC = 0x1F  # ADD_REG (foloseste registrul R8)
                elif opcode_c1 == 0b0010:
                    self.MPC = 0x20  # SUB
                elif opcode_c2 == 0b1000000010:
                    self.MPC = 0x27  # INC
                elif opcode_c2 == 0b1000000011:
                    self.MPC = 0x28  # DEC
                elif opcode_c3 == 0b11000001:
                    self.MPC = 0x3A  # BNE <-- ADAUGAT rutarea pentru BNE
                elif opcode_c4 == 0b1110000000001101:
                    self.MPC = 0x5E  # NOP
                elif opcode_c4 == 0b1110000000010000:
                    self.MPC = 0x60  # HALT
                else:
                    print(f"Eroare: OPCODE necunoscut în IR: 0x{self.IR:04X}")
                    self.halted = True

            else:
                # Căutare adresă după Label (ex: salt înapoi la IFCH)
                adresa_gasita = next((addr for addr, instr in self.Micro_ROM.items() if instr.get('LABEL') == salt),
                                     None)
                self.MPC = adresa_gasita if adresa_gasita is not None else 0x00

    def ruleaza(self):
        print("\n=== START SIMULARE HARDWARE ===")
        ciclu = 0
        self.MPC = 0x00

        while not self.halted and ciclu < 1000:  # Am marit putin limita pt bucle
            if self.MPC == 0x60 or self.MPC == 0x61:
                self.halted = True
                print("-> Semnal HALT întâlnit.")
                break

            if self.MPC not in self.Micro_ROM:
                print(f"Eroare: Adresa MPC 0x{self.MPC:02X} nu există! Oprire.")
                break

            self.MIR = self.Micro_ROM[self.MPC]

            self._citeste_sbus()
            self._citeste_dbus()
            self._executa_alu()
            self._scrie_rbus()
            self._operatii_memorie()
            self._operatii_diverse()

            self._calculeaza_urmatorul_mpc()

            ciclu += 1

        print(f"=== SIMULARE ÎNCHEIATĂ ({ciclu} cicli de ceas executati) ===\n")
        self.afiseaza_stare()

    def afiseaza_stare(self):
        print("--- STAREA PROCESORULUI (HEXA) ---")
        print(f"PC:   0x{self.PC:04X} | IR:   0x{self.IR:04X}")
        print(f"MAR:  0x{self.MAR:04X} | MDR:  0x{self.MDR:04X}")
        print(
            f"SP:   0x{self.SP:04X} | FLAG: 0x{self.FLAG:04X} | Z_flag: {self.Z_flag}")  # Am adaugat afisarea lui Z pt debugging
        print(f"T:    0x{self.T:04X} | ADR:  0x{self.ADR:04X}")
        print("-" * 34)
        for i in range(0, 16, 2):
            r1 = f"R{i}: 0x{self.R[i]:04X}"
            r2 = f"R{i + 1}: 0x{self.R[i + 1]:04X}"
            print(f"{r1:<16} {r2}")
        print("-" * 34)