import Parser
import Asembler
from Seqv import Secventiator

parser = Parser.AsmParser("test.asm")
rezultat_parser = parser.parse()
parser.save_to_file(rezultat_parser, "temp_parsed.json")

assembler = Asembler.Assembler16Bit("temp_parsed.json")
assembler.assemble("program.bin")

cpu = Secventiator()

cpu.incarca_program_binar("program.bin")

cpu.ruleaza()