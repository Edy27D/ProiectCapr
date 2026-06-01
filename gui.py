import flet as ft
import flet.canvas as cv
import traceback
from Parser import AsmParser
from Asembler import Assembler16Bit
from Seqv import Secventiator

def main(page: ft.Page):
    page.title = "Microarch Simulator 16-Bit - Ultimate Animated Datapath"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.window_width = 1500
    page.window_height = 900
    page.bgcolor = "#F8FAFC"

    cpu = Secventiator()
    all_hw_blocks = []

    # --- HELPER COMPONENTE ---
    def create_hw_block(name, top, left, width=130, height=55, default_val="0x0000", custom_content=None):
        val_text = ft.Text(default_val, font_family="Consolas", color=ft.Colors.BLUE_900, weight="bold", size=14)
        content = custom_content if custom_content else ft.Column([
            ft.Text(name, weight="w800", color=ft.Colors.BLUE_GREY_800, size=11),
            val_text
        ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2)

        container = ft.Container(
            content=content, top=top, left=left, width=width, height=height,
            bgcolor=ft.Colors.WHITE, border_radius=8,
            animate=ft.Animation(300, ft.AnimationCurve.EASE_OUT),
            animate_scale=ft.Animation(300, ft.AnimationCurve.BOUNCE_OUT),
            shadow=ft.BoxShadow(spread_radius=1, blur_radius=4, color=ft.Colors.BLACK12, offset=ft.Offset(0, 2)),
            border=ft.Border(
                top=ft.BorderSide(1, ft.Colors.BLUE_GREY_200), bottom=ft.BorderSide(1, ft.Colors.BLUE_GREY_200),
                left=ft.BorderSide(1, ft.Colors.BLUE_GREY_200), right=ft.BorderSide(1, ft.Colors.BLUE_GREY_200)
            )
        )
        all_hw_blocks.append(container)
        return container, val_text

    # --- DEFINIRE COORDONATE COMPONENTE ---
    center_x = 550
    ui_alu_box, ui_alu_val = create_hw_block("ALU", top=80, left=center_x, width=160, height=65, default_val="OP: NONE")
    ui_flag_box, ui_flag_val = create_hw_block("FLAG", top=170, left=center_x, width=160)
    ui_ivr_box, ui_ivr_val = create_hw_block("IVR", top=240, left=center_x, width=160)
    ui_pc_box, ui_pc_val = create_hw_block("PC", top=310, left=center_x, width=160)
    ui_sp_box, ui_sp_val = create_hw_block("SP", top=380, left=center_x, width=160)
    ui_t_box, ui_t_val = create_hw_block("T", top=450, left=center_x, width=160)

    ui_adr_box, ui_adr_val = create_hw_block("ADR", top=550, left=center_x+50)
    ui_mdr_box, ui_mdr_val = create_hw_block("MDR", top=620, left=center_x+50)
    
    left_x = 250
    ui_mar_box, ui_mar_val = create_hw_block("MAR", top=110, left=left_x+25)
    ui_ir_box, ui_ir_val = create_hw_block("IR", top=550, left=left_x, width=180)

    # Register Group
    rg_x = 850
    rg_texts = []
    rg_rows = []
    for i in range(16):
        t = ft.Text(f"R{i:<2}: 0x0000", font_family="Consolas", size=12, color=ft.Colors.BLUE_GREY_900)
        rg_texts.append(t)
        rg_rows.append(t)
    
    rg_content = ft.Column([
        ft.Text("Register Group", weight="bold", size=12, color=ft.Colors.BLUE_GREY_500),
        ft.Column(rg_rows, spacing=1)
    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
    
    ui_rg_box, _ = create_hw_block("RG", top=170, left=rg_x, width=130, height=360, custom_content=rg_content)

    # --- CANVAS PENTRU MAGISTRALE ---
    bus_canvas = cv.Canvas(shapes=[], expand=True)

    datapath_board = ft.Stack([
        bus_canvas,
        ui_mar_box, ui_ir_box, ui_alu_box, ui_flag_box, ui_ivr_box, ui_pc_box, ui_sp_box, ui_t_box,
        ui_adr_box, ui_mdr_box, ui_rg_box
    ], expand=True)

    # --- FUNCȚII ANIMAȚIE ȘI DESENARE MAGISTRALE ---
    def reset_all_blocks():
        for box in all_hw_blocks:
            box.bgcolor = ft.Colors.WHITE
            box.scale = 1.0
            box.shadow = ft.BoxShadow(spread_radius=1, blur_radius=4, color=ft.Colors.BLACK12, offset=ft.Offset(0, 2))
            box.border = ft.Border(
                top=ft.BorderSide(1, ft.Colors.BLUE_GREY_200), bottom=ft.BorderSide(1, ft.Colors.BLUE_GREY_200),
                left=ft.BorderSide(1, ft.Colors.BLUE_GREY_200), right=ft.BorderSide(1, ft.Colors.BLUE_GREY_200)
            )

    def highlight_block(box, role="source"):
        box.scale = 1.1 
        box.shadow = ft.BoxShadow(spread_radius=2, blur_radius=10, color=ft.Colors.BLACK38, offset=ft.Offset(0, 5))
        if role == "source_s":
            box.bgcolor = ft.Colors.ORANGE_50; color = ft.Colors.ORANGE
        elif role == "source_d":
            box.bgcolor = ft.Colors.BLUE_50; color = ft.Colors.BLUE
        elif role == "dest":
            box.bgcolor = ft.Colors.GREEN_50; color = ft.Colors.GREEN
        elif role == "alu":
            box.bgcolor = ft.Colors.PURPLE_50; color = ft.Colors.PURPLE

        box.border = ft.Border(
            top=ft.BorderSide(3, color), bottom=ft.BorderSide(3, color),
            left=ft.BorderSide(3, color), right=ft.BorderSide(3, color)
        )

    def draw_line(x1, y1, x2, y2, color, thickness=2, is_dashed=False):
        paint = ft.Paint(stroke_width=thickness, color=color, style=ft.PaintingStyle.STROKE)
        # Am simplificat desenul pentru compatibilitate cu Flet
        bus_canvas.shapes.append(cv.Path([cv.Path.MoveTo(x1, y1), cv.Path.LineTo(x2, y2)], paint=paint))

    def update_buses(step_info):
        bus_canvas.shapes.clear()
        
        # Coordonate fixe magistrale (X)
        X_SBUS = 480; X_DBUS = 510; X_RBUS = 800
        
        # Culori implicite (Inactive)
        c_idle = ft.Colors.BLUE_GREY_100
        c_sbus = ft.Colors.ORANGE_500
        c_dbus = ft.Colors.BLUE_500
        c_rbus = ft.Colors.GREEN_500

        # --- 1. DESENĂM FIRELE DE BAZĂ INACTIVE (GRI) ---
        draw_line(X_SBUS, 50, X_SBUS, 700, c_idle, 4) # SBUS vertical
        draw_line(X_DBUS, 50, X_DBUS, 700, c_idle, 4) # DBUS vertical
        draw_line(X_RBUS, 50, X_RBUS, 700, c_idle, 4) # RBUS vertical

        # Textele pentru magistrale
        bus_canvas.shapes.append(cv.Text(X_SBUS-15, 40, "SBUS", ft.TextStyle(color=c_idle, weight="bold", size=12)))
        bus_canvas.shapes.append(cv.Text(X_DBUS-15, 40, "DBUS", ft.TextStyle(color=c_idle, weight="bold", size=12)))
        bus_canvas.shapes.append(cv.Text(X_RBUS-15, 40, "RBUS", ft.TextStyle(color=c_idle, weight="bold", size=12)))

        # Fire Gri Către ALU
        draw_line(X_SBUS, 100, 550, 100, c_idle)
        draw_line(X_DBUS, 120, 550, 120, c_idle)
        draw_line(710, 110, X_RBUS, 110, c_idle)

        # Fire Gri de la/către Componente Centrale
        y_coords = {"FLAG": 195, "PC": 335, "SP": 405, "T": 475}
        for comp, y in y_coords.items():
            draw_line(X_SBUS, y, 550, y, c_idle) # Către SBUS
            draw_line(X_DBUS, y+10, 550, y+10, c_idle) # Către DBUS
            draw_line(710, y, X_RBUS, y, c_idle) # De la RBUS
            
        # Fire Gri Speciale (MDR, ADR, RG)
        draw_line(X_SBUS, 645, 600, 645, c_idle) # MDR -> SBUS
        draw_line(X_DBUS, 660, 600, 660, c_idle) # MDR -> DBUS
        draw_line(730, 645, X_RBUS, 645, c_idle) # RBUS -> MDR
        draw_line(730, 575, X_RBUS, 575, c_idle) # RBUS -> ADR
        
        # Fire Gri Către Registre (Acestea taie tot ecranul orizontal)
        draw_line(X_SBUS, 350, 850, 350, c_idle) # RG -> SBUS
        draw_line(X_DBUS, 370, 850, 370, c_idle) # RG -> DBUS
        draw_line(X_RBUS, 350, 850, 350, c_idle) # RBUS -> RG

        # --- 2. SUPRAPUNEM FIRELE ACTIVE DACA AVEM STEP INFO ---
        if not step_info:
            return

        sbus_src = step_info.get('sbus_sursa', 'NONE')
        dbus_src = step_info.get('dbus_dest', 'NONE') # E sursa pentru DBUS în codul tău
        rbus_dst = step_info.get('rbus_dest', 'NONE')
        alu_op = step_info.get('alu_op', 'NONE')

        # Activare SBUS (Tragem liniile groase portocalii)
        if sbus_src != 'NONE':
            draw_line(X_SBUS, 50, X_SBUS, 700, c_sbus, 5) # Aprindem magistrala principală
            bus_canvas.shapes.append(cv.Text(X_SBUS-15, 40, "SBUS", ft.TextStyle(color=c_sbus, weight="bold", size=12)))
            draw_line(X_SBUS, 100, 550, 100, c_sbus, 4)   # Intră în ALU

            # Mapăm cine trimite pe SBUS
            if sbus_src == 'PdPCs': draw_line(X_SBUS, 335, 550, 335, c_sbus, 4); highlight_block(ui_pc_box, "source_s")
            elif sbus_src == 'PdSPs': draw_line(X_SBUS, 405, 550, 405, c_sbus, 4); highlight_block(ui_sp_box, "source_s")
            elif sbus_src == 'PdTs': draw_line(X_SBUS, 475, 550, 475, c_sbus, 4); highlight_block(ui_t_box, "source_s")
            elif sbus_src == 'PdFLAGs': draw_line(X_SBUS, 195, 550, 195, c_sbus, 4); highlight_block(ui_flag_box, "source_s")
            elif sbus_src == 'PdMDRs': draw_line(X_SBUS, 645, 600, 645, c_sbus, 4); highlight_block(ui_mdr_box, "source_s")
            elif sbus_src in ['PdRGs', 'PdRGsNeg']: draw_line(X_SBUS, 350, 850, 350, c_sbus, 4); highlight_block(ui_rg_box, "source_s")

        # Activare DBUS (Liniile groase albastre)
        if dbus_src != 'NONE':
            draw_line(X_DBUS, 50, X_DBUS, 700, c_dbus, 5) 
            bus_canvas.shapes.append(cv.Text(X_DBUS-15, 40, "DBUS", ft.TextStyle(color=c_dbus, weight="bold", size=12)))
            draw_line(X_DBUS, 120, 550, 120, c_dbus, 4)   # Intră în ALU
            
            if dbus_src == 'PdPCd': draw_line(X_DBUS, 345, 550, 345, c_dbus, 4); highlight_block(ui_pc_box, "source_d")
            elif dbus_src == 'PdMDRd': draw_line(X_DBUS, 660, 600, 660, c_dbus, 4); highlight_block(ui_mdr_box, "source_d")
            elif dbus_src == 'PdRGd': draw_line(X_DBUS, 370, 850, 370, c_dbus, 4); highlight_block(ui_rg_box, "source_d")

        # Activare ALU
        if alu_op not in ['NONE', 'PASS_S'] or (sbus_src != 'NONE'):
            highlight_block(ui_alu_box, "alu")
            ui_alu_val.value = f"OP: {alu_op}"
        else:
            ui_alu_val.value = "OP: NONE"

        # Activare RBUS (Liniile groase verzi)
        if rbus_dst != 'NONE':
            draw_line(X_RBUS, 50, X_RBUS, 700, c_rbus, 5) 
            bus_canvas.shapes.append(cv.Text(X_RBUS-15, 40, "RBUS", ft.TextStyle(color=c_rbus, weight="bold", size=12)))
            draw_line(710, 110, X_RBUS, 110, c_rbus, 4)   # Iese din ALU

            # Mapăm cine primește de pe RBUS
            if rbus_dst == 'PmPC': draw_line(710, 335, X_RBUS, 335, c_rbus, 4); highlight_block(ui_pc_box, "dest")
            elif rbus_dst == 'PmT': draw_line(710, 475, X_RBUS, 475, c_rbus, 4); highlight_block(ui_t_box, "dest")
            elif rbus_dst == 'PmFLAG': draw_line(710, 195, X_RBUS, 195, c_rbus, 4); highlight_block(ui_flag_box, "dest")
            elif rbus_dst == 'PmADR': draw_line(730, 575, X_RBUS, 575, c_rbus, 4); highlight_block(ui_adr_box, "dest")
            elif rbus_dst == 'PmMDR': draw_line(730, 645, X_RBUS, 645, c_rbus, 4); highlight_block(ui_mdr_box, "dest")
            elif rbus_dst == 'PmRG': draw_line(X_RBUS, 350, 850, 350, c_rbus, 4); highlight_block(ui_rg_box, "dest")
            elif rbus_dst == 'PmIR': draw_line(430, 575, X_RBUS, 575, c_rbus, 4); highlight_block(ui_ir_box, "dest")

    # --- UI STÂNGA ȘI MAIN LOGIC ---
    asm_input = ft.TextField(multiline=True, min_lines=12, max_lines=12, label="Cod Assembly (.asm)", text_style=ft.TextStyle(font_family="Consolas", size=12), border_color=ft.Colors.BLUE_300)
    status_text = ft.Text("Sistem pregătit.", weight="bold", size=13, color=ft.Colors.BLUE_GREY_500)
    memory_table = ft.DataTable(columns=[ft.DataColumn(ft.Text("Addr")), ft.DataColumn(ft.Text("Data"))], rows=[], heading_row_height=30, data_row_min_height=25, data_row_max_height=25)

    def main_update(step_info=None):
        ui_pc_val.value = f"0x{cpu.PC:04X}"; ui_ir_val.value = f"0x{cpu.IR:04X}"; ui_mar_val.value = f"0x{cpu.MAR:04X}"
        ui_mdr_val.value = f"0x{cpu.MDR:04X}"; ui_sp_val.value = f"0x{cpu.SP:04X}"; ui_t_val.value = f"0x{cpu.T:04X}"
        ui_adr_val.value = f"0x{cpu.ADR:04X}"; ui_flag_val.value = f"0x{cpu.FLAG:04X} (Z:{cpu.Z_flag})"
        for i in range(16): rg_texts[i].value = f"R{i:<2}: 0x{cpu.R[i]:04X}"

        reset_all_blocks()
        update_buses(step_info)

        memory_table.rows.clear()
        for i in range(25):
            val = cpu.MPM[i]
            color = ft.Colors.BLUE_50 if i == cpu.PC else ft.Colors.TRANSPARENT
            memory_table.rows.append(ft.DataRow(cells=[ft.DataCell(ft.Text(f"0x{i:04X}", size=11)), ft.DataCell(ft.Text(f"0x{val:04X}", size=11))], color=color))
        page.update()

    def on_load(e):
        try:
            nonlocal cpu; cpu = Secventiator()
            with open("test.asm", "w") as f: f.write(asm_input.value)
            parser = AsmParser("test.asm"); parser.save_to_file(parser.parse(), "temp_parsed.json")
            assembler = Assembler16Bit("temp_parsed.json"); assembler.assemble("program.bin")
            cpu.incarca_program_binar("program.bin")
            main_update()
            status_text.value = "Compilat & Încărcat cu succes!"
            status_text.color = ft.Colors.GREEN
        except Exception as ex:
            status_text.value = f"Eroare compilare!"; status_text.color = ft.Colors.RED
        page.update()

    def on_step(e):
        rezultat = cpu.step()
        if rezultat["status"] == "HALT":
            status_text.value = "PROCESOR OPRIT (HALT)"; status_text.color = ft.Colors.RED
        elif rezultat["status"] == "OK":
            status_text.value = f"Se execută MPC: 0x{cpu.MPC:02X}"; status_text.color = ft.Colors.BLUE_700
        main_update(rezultat)

    left_control_panel = ft.Container(
        content=ft.Column([
            asm_input,
            ft.Row([
                ft.ElevatedButton("Load", on_click=on_load, bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE, icon=ft.Icons.UPLOAD),
                ft.ElevatedButton("Step", icon=ft.Icons.SKIP_NEXT, on_click=on_step, bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE)
            ]),
            status_text, ft.Divider(),
            ft.Text("Memorie Principală (MPM)", weight="bold", size=13, color=ft.Colors.BLUE_GREY_800),
            ft.Container(content=ft.Column([memory_table], scroll=ft.ScrollMode.AUTO), height=350, border_radius=5, border=ft.Border(top=ft.BorderSide(1, ft.Colors.BLUE_GREY_100), bottom=ft.BorderSide(1, ft.Colors.BLUE_GREY_100), left=ft.BorderSide(1, ft.Colors.BLUE_GREY_100), right=ft.BorderSide(1, ft.Colors.BLUE_GREY_100)))
        ]), width=320, padding=15, bgcolor=ft.Colors.WHITE, shadow=ft.BoxShadow(spread_radius=2, blur_radius=10, color=ft.Colors.BLACK12, offset=ft.Offset(2, 0))
    )

    page.add(ft.Row([left_control_panel, ft.Container(content=datapath_board, expand=True)], expand=True))
    main_update()

if __name__ == "__main__":
    try: ft.run(main)
    except AttributeError: ft.app(target=main)