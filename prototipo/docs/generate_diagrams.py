import matplotlib.pyplot as plt
import matplotlib.patches as patches
from pathlib import Path

img_dir = Path(__file__).resolve().parent / "img"
img_dir.mkdir(parents=True, exist_ok=True)


def draw_architecture_diagram():
    fig, ax = plt.subplots(figsize=(15, 11), dpi=300)
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 11)
    ax.axis("off")

    c_primary = "#1E3A8A"   # Azul escuro
    c_teal = "#0D9488"      # Verde-azulado
    c_green = "#10B981"     # Verde
    c_red = "#DC2626"       # Vermelho
    c_slate = "#334155"     # Grafite
    c_box = "#FFFFFF"       # Branco

    fig.patch.set_facecolor("#FFFFFF")

    # =========================================================================
    # CAMADA 1: Ativo Físico & Automação (TOPO)
    # =========================================================================
    layer1 = patches.FancyBboxPatch((0.6, 7.6), 13.8, 2.9, boxstyle="round,pad=0.2",
                                    facecolor="#EFF6FF", edgecolor=c_primary, linewidth=2)
    ax.add_patch(layer1)
    ax.text(0.9, 10.15, "CAMADA 1: Ativo Fisico e Automacao (prototipo/factoryio/)",
            fontsize=12, fontweight="bold", color=c_primary)

    # 1.1 Factory I/O
    b_fio = patches.FancyBboxPatch((1.0, 8.0), 3.6, 1.8, boxstyle="round,pad=0.1",
                                   facecolor=c_box, edgecolor=c_slate, linewidth=1.5)
    ax.add_patch(b_fio)
    ax.text(2.8, 9.15, "Factory I/O (3D)", fontsize=11, fontweight="bold", ha="center", color=c_slate)
    ax.text(2.8, 8.45, "• Esteiras rolantes e Sensores\n• Mesa Transfer transversal\n• Sorting by Height (Basic)",
            fontsize=8.5, ha="center", color="#64748B")

    # 1.2 CODESYS
    b_plc = patches.FancyBboxPatch((5.7, 8.0), 3.6, 1.8, boxstyle="round,pad=0.1",
                                   facecolor=c_box, edgecolor=c_slate, linewidth=1.5)
    ax.add_patch(b_plc)
    ax.text(7.5, 9.15, "CODESYS SoftPLC", fontsize=11, fontweight="bold", ha="center", color=c_slate)
    ax.text(7.5, 8.45, "• Control Win V3 x64 (IEC 61131)\n• Logica Ladder de Automacao\n• 53 tags de controle ativas",
            fontsize=8.5, ha="center", color="#64748B")

    # 1.3 Servidor OPC UA
    b_opc = patches.FancyBboxPatch((10.4, 8.0), 3.6, 1.8, boxstyle="round,pad=0.1",
                                   facecolor=c_box, edgecolor=c_primary, linewidth=1.8)
    ax.add_patch(b_opc)
    ax.text(12.2, 9.15, "Servidor OPC UA", fontsize=11, fontweight="bold", ha="center", color=c_primary)
    ax.text(12.2, 8.45, "• Porta 4840 (IEC 62541)\n• Publicacao de Tags em Tempo Real\n• Acesso Anonimo Habilitado",
            fontsize=8.5, ha="center", color="#64748B")

    # Conexões Camada 1
    ax.annotate("", xy=(5.7, 8.9), xytext=(4.6, 8.9),
                arrowprops=dict(arrowstyle="<->", color=c_primary, lw=2))
    ax.text(5.15, 9.15, "Sinais I/O", fontsize=8.5, ha="center", fontweight="bold", color=c_primary)

    ax.annotate("", xy=(10.4, 8.9), xytext=(9.3, 8.9),
                arrowprops=dict(arrowstyle="<->", color=c_primary, lw=2))
    ax.text(9.85, 9.15, "Tags IEC", fontsize=8.5, ha="center", fontweight="bold", color=c_primary)

    # =========================================================================
    # CAMADA 2: Núcleo do Gêmeo Digital (MEIO)
    # =========================================================================
    layer2 = patches.FancyBboxPatch((0.6, 3.6), 13.8, 3.5, boxstyle="round,pad=0.2",
                                    facecolor="#F0FDFA", edgecolor=c_teal, linewidth=2)
    ax.add_patch(layer2)
    ax.text(0.9, 6.75, "CAMADA 2: Nucleo do Gemeo Digital (prototipo/gemeo-digital/)",
            fontsize=12, fontweight="bold", color=c_teal)

    # 2.4 AAS (Esquerda)
    b_aas = patches.FancyBboxPatch((0.9, 4.0), 2.7, 2.3, boxstyle="round,pad=0.1",
                                   facecolor=c_box, edgecolor=c_green, linewidth=1.5)
    ax.add_patch(b_aas)
    ax.text(2.25, 5.65, "aas_model.py", fontsize=10.5, fontweight="bold", ha="center", color=c_green)
    ax.text(2.25, 4.65, "• Eclipse BaSyx AAS\n• TechnicalIdentification\n• OperationalData\n• HealthMonitoring",
            fontsize=8.0, ha="center", color="#64748B")

    # 2.3 Motor de Petri
    b_pet = patches.FancyBboxPatch((4.0, 4.0), 2.8, 2.3, boxstyle="round,pad=0.1",
                                   facecolor=c_box, edgecolor=c_red, linewidth=1.5)
    ax.add_patch(b_pet)
    ax.text(5.4, 5.65, "petri_engine.py", fontsize=10.5, fontweight="bold", ha="center", color=c_red)
    ax.text(5.4, 4.65, "• Rede de Petri (p1..p16)\n• Stuck ON / Stuck OFF\n• Timeout de Transporte\n• Inferencia de Falhas",
            fontsize=8.0, ha="center", color="#64748B")

    # 2.2 Sanitizador
    b_san = patches.FancyBboxPatch((7.2, 4.0), 2.8, 2.3, boxstyle="round,pad=0.1",
                                   facecolor=c_box, edgecolor=c_teal, linewidth=1.5)
    ax.add_patch(b_san)
    ax.text(8.6, 5.65, "data_sanitizer.py", fontsize=10.5, fontweight="bold", ha="center", color=c_teal)
    ax.text(8.6, 4.65, "• Debounce 50ms\n• Quality Checking\n• Data Lineage (UTC)\n• ISO/IEC 30173",
            fontsize=8.0, ha="center", color="#64748B")

    # 2.1 Conector OPC UA (Direita)
    b_con = patches.FancyBboxPatch((10.4, 4.0), 3.6, 2.3, boxstyle="round,pad=0.1",
                                   facecolor=c_box, edgecolor=c_primary, linewidth=1.5)
    ax.add_patch(b_con)
    ax.text(12.2, 5.65, "opc_connector.py", fontsize=10.5, fontweight="bold", ha="center", color=c_primary)
    ax.text(12.2, 4.65, "• Cliente asyncua assincrono\n• Subscricao 100ms\n• Escrita remota de tags\n• STOP de Emergencia",
            fontsize=8.0, ha="center", color="#64748B")

    # Conexão Vertical Servidor OPC UA <-> Conector
    ax.annotate("", xy=(12.2, 6.3), xytext=(12.2, 8.0),
                arrowprops=dict(arrowstyle="<->", color=c_primary, lw=2.5))
    ax.text(13.2, 7.15, "TCP 4840\n(asyncua)", fontsize=8.5, ha="center", fontweight="bold", color=c_primary)

    # Fluxos horizontais Camada 2
    ax.annotate("", xy=(10.0, 5.15), xytext=(10.4, 5.15),
                arrowprops=dict(arrowstyle="->", color=c_teal, lw=2))
    ax.text(10.2, 5.4, "Dados\nBrutos", fontsize=7.5, ha="center", color=c_teal)

    ax.annotate("", xy=(6.8, 5.15), xytext=(7.2, 5.15),
                arrowprops=dict(arrowstyle="->", color=c_teal, lw=2))
    ax.text(7.0, 5.4, "Dados\nLimpos", fontsize=7.5, ha="center", color=c_teal)

    ax.annotate("", xy=(3.6, 5.15), xytext=(4.0, 5.15),
                arrowprops=dict(arrowstyle="->", color=c_green, lw=2))
    ax.text(3.8, 5.4, "Estado &\nAlertas", fontsize=7.5, ha="center", color=c_green)

    # Linha STOP de Emergência (Petri -> Connector)
    ax.annotate("", xy=(10.4, 4.25), xytext=(6.8, 4.25),
                arrowprops=dict(arrowstyle="->", color=c_red, lw=2, linestyle="--"))
    ax.text(8.6, 3.9, "[EMERGENCIA] Comando STOP Autonomo", fontsize=8.0, ha="center", fontweight="bold", color=c_red)

    # =========================================================================
    # CAMADA 3: Aplicação Supervisória (BASE)
    # =========================================================================
    layer3 = patches.FancyBboxPatch((0.6, 0.4), 13.8, 2.7, boxstyle="round,pad=0.2",
                                    facecolor="#F8FAFC", edgecolor=c_primary, linewidth=2)
    ax.add_patch(layer3)
    ax.text(0.9, 2.75, "CAMADA 3: Aplicacao do Usuario e Supervisorio (prototipo/dashboard/app.py)",
            fontsize=12, fontweight="bold", color=c_primary)

    b_d1 = patches.FancyBboxPatch((0.9, 0.65), 3.8, 1.8, boxstyle="round,pad=0.1",
                                  facecolor=c_box, edgecolor=c_slate, linewidth=1.5)
    ax.add_patch(b_d1)
    ax.text(2.8, 1.9, "Painel de Saude & KPIs", fontsize=10, fontweight="bold", ha="center", color=c_primary)
    ax.text(2.8, 1.15, "• 100% Qualidade de Dados (ISO 30173)\n• Estado de Saude (HEALTHY/FAULT)\n• Contador Total de Caixas",
            fontsize=8.0, ha="center", color="#64748B")

    b_d2 = patches.FancyBboxPatch((5.3, 0.65), 4.4, 1.8, boxstyle="round,pad=0.1",
                                  facecolor=c_box, edgecolor=c_slate, linewidth=1.5)
    ax.add_patch(b_d2)
    ax.text(7.5, 1.9, "Sinotico 2D & Rede de Petri", fontsize=10, fontweight="bold", ha="center", color=c_teal)
    ax.text(7.5, 1.15, "• LEDs dos Sensores e Motores ao Vivo\n• Grafo de Estados Iluminado (p1..p16)\n• Tabela de Auditoria e Linhagem",
            fontsize=8.0, ha="center", color="#64748B")

    b_d3 = patches.FancyBboxPatch((10.3, 0.65), 3.7, 1.8, boxstyle="round,pad=0.1",
                                  facecolor=c_box, edgecolor=c_red, linewidth=1.5)
    ax.add_patch(b_d3)
    ax.text(12.15, 1.9, "Controle & Injecao de Falhas", fontsize=10, fontweight="bold", ha="center", color=c_red)
    ax.text(12.15, 1.15, "• Comandos: START, STOP, RESET\n• Injecao: Stuck OFF / Stuck ON\n• Simulacao de Transicao Ilegal",
            fontsize=8.0, ha="center", color="#64748B")

    # Conexões Camada 2 <-> Camada 3
    ax.annotate("", xy=(2.25, 2.45), xytext=(2.25, 4.0),
                arrowprops=dict(arrowstyle="->", color=c_green, lw=2))
    ax.text(3.1, 3.2, "Metricas AAS", fontsize=8.0, fontweight="bold", color=c_green)

    ax.annotate("", xy=(12.2, 4.0), xytext=(12.2, 2.45),
                arrowprops=dict(arrowstyle="->", color=c_primary, lw=2))
    ax.text(13.2, 3.2, "Comandos do\nOperador", fontsize=8.0, ha="center", fontweight="bold", color=c_primary)

    out_file = img_dir / "arquitetura_3_camadas.png"
    plt.tight_layout()
    plt.savefig(out_file, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"Diagrama de Arquitetura completo recuperado com sucesso: {out_file}")


def draw_sequence_diagram():
    fig, ax = plt.subplots(figsize=(13, 8.5), dpi=300)
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 8.5)
    ax.axis("off")

    fig.patch.set_facecolor("#FFFFFF")

    actors = [
        ("Operador", 1.5, "#1E3A8A"),
        ("Factory I/O", 4.0, "#334155"),
        ("CODESYS CLP", 6.5, "#334155"),
        ("Gemeo Digital", 9.0, "#0D9488"),
        ("Dashboard Web", 11.5, "#1E3A8A"),
    ]

    for name, x, col in actors:
        b = patches.FancyBboxPatch((x - 1.0, 7.5), 2.0, 0.7, boxstyle="round,pad=0.1",
                                   facecolor=col, edgecolor=col)
        ax.add_patch(b)
        ax.text(x, 7.85, name, fontsize=9.5, fontweight="bold", ha="center", color="#FFFFFF")
        ax.plot([x, x], [0.7, 7.5], linestyle="--", color="#CBD5E1", lw=1.5)

    # 1. CICLO NORMAL
    ax.add_patch(patches.Rectangle((0.5, 6.5), 12.0, 0.5, facecolor="#F0FDF4", edgecolor="#10B981"))
    ax.text(6.5, 6.75, "1. CICLO DE OPERACAO NORMAL", fontsize=9.5, fontweight="bold", ha="center", color="#15803D")

    ax.annotate("", xy=(9.0, 6.1), xytext=(1.5, 6.1), arrowprops=dict(arrowstyle="->", color="#1E3A8A", lw=1.5))
    ax.text(5.25, 6.25, "1. Clica em START", fontsize=8.5, color="#1E3A8A", ha="center")

    ax.annotate("", xy=(6.5, 5.7), xytext=(9.0, 5.7), arrowprops=dict(arrowstyle="->", color="#0D9488", lw=1.5))
    ax.text(7.75, 5.85, "2. PLC_PRG.start = TRUE", fontsize=8.5, color="#0D9488", ha="center")

    ax.annotate("", xy=(4.0, 5.3), xytext=(6.5, 5.3), arrowprops=dict(arrowstyle="->", color="#334155", lw=1.5))
    ax.text(5.25, 5.45, "3. Liga Esteira de Entrada", fontsize=8.5, color="#334155", ha="center")

    # 2. CENARIO DE ANOMALIA
    ax.add_patch(patches.Rectangle((0.5, 4.3), 12.0, 0.5, facecolor="#FEF2F2", edgecolor="#EF4444"))
    ax.text(6.5, 4.55, "2. CENARIO DE ANOMALIA (Falha: Sensor de Altura Stuck OFF)",
            fontsize=9.5, fontweight="bold", ha="center", color="#B91C1C")

    ax.annotate("", xy=(6.5, 3.9), xytext=(4.0, 3.9), arrowprops=dict(arrowstyle="->", color="#EF4444", lw=1.5))
    ax.text(5.25, 4.05, "4. Caixa chega na mesa (loaded = TRUE sem sensor de altura)", fontsize=8.5, color="#EF4444", ha="center")

    ax.annotate("", xy=(9.0, 3.5), xytext=(6.5, 3.5), arrowprops=dict(arrowstyle="->", color="#EF4444", lw=1.5))
    ax.text(7.75, 3.65, "5. DataChange: loaded = TRUE (Transicao Proibida!)", fontsize=8.5, color="#EF4444", ha="center")

    ax.annotate("", xy=(6.5, 3.0), xytext=(9.0, 3.0), arrowprops=dict(arrowstyle="->", color="#DC2626", lw=2))
    ax.text(7.75, 3.15, "6. [STOP AUTONOMO] PLC_PRG.desligar = TRUE", fontsize=8.5, fontweight="bold", color="#DC2626", ha="center")

    ax.annotate("", xy=(4.0, 2.6), xytext=(6.5, 2.6), arrowprops=dict(arrowstyle="->", color="#DC2626", lw=2))
    ax.text(5.25, 2.75, "7. Desliga motores da esteira imediatamente", fontsize=8.5, fontweight="bold", color="#DC2626", ha="center")

    ax.annotate("", xy=(11.5, 2.2), xytext=(9.0, 2.2), arrowprops=dict(arrowstyle="->", color="#DC2626", lw=1.5))
    ax.text(10.25, 2.35, "8. Publica Alarme Critico e Diagnostico", fontsize=8.5, color="#DC2626", ha="center")

    # 3. RECUPERACAO
    ax.add_patch(patches.Rectangle((0.5, 1.4), 12.0, 0.5, facecolor="#EFF6FF", edgecolor="#1E3A8A"))
    ax.text(6.5, 1.65, "3. RECUPERACAO E GOVERNANCA (Intervencao do Operador)",
            fontsize=9.5, fontweight="bold", ha="center", color="#1E3A8A")

    ax.annotate("", xy=(9.0, 1.0), xytext=(1.5, 1.0), arrowprops=dict(arrowstyle="->", color="#1E3A8A", lw=1.5))
    ax.text(5.25, 1.15, "9. Operador conserta sensor e clica em RESET", fontsize=8.5, color="#1E3A8A", ha="center")

    ax.annotate("", xy=(6.5, 0.6), xytext=(9.0, 0.6), arrowprops=dict(arrowstyle="->", color="#10B981", lw=1.5))
    ax.text(7.75, 0.75, "10. Limpa anomalias e envia PLC_PRG.reset = TRUE", fontsize=8.5, color="#10B981", ha="center")

    out_file = img_dir / "fluxo_sequencia.png"
    plt.tight_layout()
    plt.savefig(out_file, dpi=300, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"Diagrama de Sequência recuperado com sucesso: {out_file}")


if __name__ == "__main__":
    draw_architecture_diagram()
    draw_sequence_diagram()
