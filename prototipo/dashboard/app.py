"""
Dashboard Supervisório do Gêmeo Digital
Interface Web em Streamlit para Monitoramento em Tempo Real, Visualização da Rede de Petri,
Auditoria de Governança de Dados (ISO/IEC 30173), Diagnóstico de Falhas e Controle Remoto.
"""

import sys
import os
import threading
from pathlib import Path

# Adiciona a pasta do gêmeo digital ao path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR / "gemeo-digital"))

import asyncio
import json
import time
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from opc_connector import DigitalTwinConnector

# Configuração da Página
st.set_page_config(
    page_title="Gêmeo Digital Industrial | Sorting by Height",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS Personalizada (Tema Dark Premium)
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
    .metric-card {
        background: linear-gradient(135deg, #1f2937, #111827);
        border: 1px solid #374151;
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
    }
    .status-healthy {
        color: #10b981;
        font-weight: bold;
        font-size: 1.2rem;
    }
    .status-critical {
        color: #ef4444;
        font-weight: bold;
        font-size: 1.2rem;
    }
    .sensor-on {
        background-color: #10b981;
        color: white;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: bold;
        display: inline-block;
    }
    .sensor-off {
        background-color: #374151;
        color: #9ca3af;
        padding: 4px 10px;
        border-radius: 6px;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# SERVIÇO SINGLETON DO GÊMEO DIGITAL (THREAD EM SEGUNDO PLANO)
# =============================================================================
class DigitalTwinBackgroundService:
    def __init__(self):
        self.connector = DigitalTwinConnector()
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.thread.start()
        # Aguarda a inicialização e conexão
        time.sleep(1.5)

    def _run_event_loop(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.connector.connect_and_subscribe())
            self.loop.run_forever()
        except Exception as e:
            print(f"[ERRO SERVIÇO OPC UA]: {e}")

    def execute_async(self, coro):
        """Executa comandos de forma thread-safe na thread do conector."""
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        try:
            return future.result(timeout=3.0)
        except Exception as e:
            print(f"[ERRO AO EXECUTAR COMANDO]: {e}")
            return None


@st.cache_resource
def get_service():
    """Garante que apenas UMA instância do conector OPC UA roda na aplicação."""
    return DigitalTwinBackgroundService()


service = get_service()
dt = service.connector

# =============================================================================
# BARRA LATERAL (SIDEBAR): CONTROLE & INJEÇÃO DE FALHAS
# =============================================================================
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/robot-arm.png", width=70)
    st.title("Painel de Controle")
    st.caption("Controle Supervisório e Injeção de Falhas")

    st.markdown("---")
    st.subheader("🎮 Comandos do Operador")
    
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        if st.button("▶️ START", use_container_width=True, type="primary"):
            service.execute_async(dt.start_plant())
            st.toast("Comando START enviado para o CLP!", icon="🚀")

    with col_c2:
        if st.button("🔄 RESET", use_container_width=True):
            service.execute_async(dt.reset_plant())
            st.toast("Comando RESET enviado! Falhas limpas.", icon="🔄")

    if st.button("🛑 PARADA DE EMERGÊNCIA", use_container_width=True):
        service.execute_async(dt.emergency_stop(reason="Parada acionada manualmente no Dashboard"))
        st.toast("PARADA DE EMERGÊNCIA ATIVADA!", icon="🛑")

    st.markdown("---")
    st.subheader("🧪 Injeção de Falhas (Testes)")
    st.caption("Simulação de anomalias para auditoria do Gêmeo Digital")

    if st.button("⚠️ Injetar: Sensor Altura Stuck OFF", use_container_width=True):
        dt.inject_fault("STUCK_OFF_HIGH_SENSOR")
        st.toast("Falha injetada: Sensor de Altura Stuck OFF!", icon="🚨")

    if st.button("⚠️ Injetar: Presença Stuck ON", use_container_width=True):
        dt.inject_fault("STUCK_ON_PRESENCE")
        st.toast("Falha injetada: Sensor de Presença Stuck ON!", icon="🚨")

    if st.button("⚠️ Injetar: Transição Proibida", use_container_width=True):
        dt.inject_fault("ILLEGAL_TRANSITION")
        st.toast("Falha injetada: Transição Ilegal de Estados!", icon="🚨")

    st.markdown("---")
    st.caption("Padrão: ISO/IEC 30173 & ISO 23247")
    st.caption("Protocolo: OPC UA @ 127.0.0.1:4840")


# =============================================================================
# CABEÇALHO PRINCIPAL E BANNER DE ALARME
# =============================================================================
st.title("🏭 Gêmeo Digital: Linha de Separação de Caixas")
st.markdown("**Plataforma Supervisória de Diagnóstico em Tempo Real com Eclipse BaSyx & Rede de Petri**")


# Fragmento reativo que atualiza o dashboard a cada 1 segundo automaticamente
@st.fragment(run_every="1s")
def render_live_dashboard():
    # Obter estado atual do Gêmeo Digital
    state = dt.get_full_state()
    petri = state["petri_net"]
    sanitizer = state["sanitizer_metrics"]
    aas = state["aas_model"]
    tags = petri["tags_state"]
    health = petri["health_status"]
    anomalies = petri["active_anomalies"]

    # Banner de Alerta Crítico se houver falha
    if health == "CRITICAL_FAULT":
        st.error(f"""
        ### 🚨 PARADA DE EMERGÊNCIA ATIVADA PELO GÊMEO DIGITAL!
        **Anomalia Detectada:** {anomalies[0]['message'] if anomalies else 'Violação no modelo de segurança'}  
        **Componente Afetado:** `{anomalies[0]['component'] if anomalies else 'Desconhecido'}`  
        **Ação Recomendada:** {anomalies[0]['suggested_action'] if anomalies else 'Inspecione a planta física'}
        """)

    # -------------------------------------------------------------------------
    # CARDS DE MÉTRICAS (KPIs)
    # -------------------------------------------------------------------------
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        cls_status = "status-critical" if health == "CRITICAL_FAULT" else "status-healthy"
        txt_status = "🔴 PARADA DE EMERGÊNCIA" if health == "CRITICAL_FAULT" else "🟢 OPERACIONAL"
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #9ca3af; font-size: 0.9rem;">STATUS DE SAÚDE</div>
            <div class="{cls_status}">{txt_status}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #9ca3af; font-size: 0.9rem;">QUALIDADE DOS DADOS (ISO 30173)</div>
            <div style="color: #60a5fa; font-size: 1.4rem; font-weight: bold;">{sanitizer['data_quality_percentage']}%</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #9ca3af; font-size: 0.9rem;">EVENTOS SANITIZADOS</div>
            <div style="color: #a78bfa; font-size: 1.4rem; font-weight: bold;">{sanitizer['total_sanitized']}</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        active_p = petri.get("active_places", ["p1"])
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #9ca3af; font-size: 0.9rem;">ESTADO ATIVO (PETRI)</div>
            <div style="color: #34d399; font-size: 1.4rem; font-weight: bold;">{', '.join(active_p) if active_p else 'p1'}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # ABAS PRINCIPAIS DO SUPERVISÓRIO
    # -------------------------------------------------------------------------
    tab1, tab2, tab3, tab4 = st.tabs([
        "🏭 Sinótico da Planta 2D",
        "🕸️ Grafo da Rede de Petri",
        "📜 Auditoria & Governança (ISO/IEC 30173)",
        "📦 Modelo AAS (Eclipse BaSyx)"
    ])

    # -------------------------------------------------------------------------
    # TAB 1: SINÓTICO DO CHÃO DE FÁBRICA
    # -------------------------------------------------------------------------
    with tab1:
        st.subheader("Estado dos Sensores e Atuadores da Linha")
        col_s1, col_s2, col_s3 = st.columns(3)
        
        with col_s1:
            st.markdown("### 🟢 Sensores de Entrada & Altura")
            cls_pallet = "sensor-on" if tags.get("palletSensor") else "sensor-off"
            txt_pallet = "ACIONADO (1)" if tags.get("palletSensor") else "DESLIGADO (0)"
            st.markdown(f"- **Sensor de Presença (palletSensor):** <span class='{cls_pallet}'>{txt_pallet}</span>", unsafe_allow_html=True)
            
            cls_high = "sensor-on" if tags.get("highSensor") else "sensor-off"
            txt_high = "CAIXA ALTA (1)" if tags.get("highSensor") else "CAIXA BAIXA (0)"
            st.markdown(f"- **Sensor de Altura (highSensor):** <span class='{cls_high}'>{txt_high}</span>", unsafe_allow_html=True)

            cls_loaded = "sensor-on" if tags.get("loaded") else "sensor-off"
            txt_loaded = "CARGA POSICIONADA (1)" if tags.get("loaded") else "LIVRE (0)"
            st.markdown(f"- **Sensor da Mesa (loaded):** <span class='{cls_loaded}'>{txt_loaded}</span>", unsafe_allow_html=True)

        with col_s2:
            st.markdown("### 🔴 Motores & Esteiras")
            cls_entry = "sensor-on" if tags.get("conveyorEntry") else "sensor-off"
            txt_entry = "RODANDO ▶" if tags.get("conveyorEntry") else "PARADA ⏹"
            st.markdown(f"- **Esteira de Entrada (conveyorEntry):** <span class='{cls_entry}'>{txt_entry}</span>", unsafe_allow_html=True)

            cls_tleft = "sensor-on" if tags.get("transferLeft") else "sensor-off"
            txt_tleft = "ATIVO ⬅" if tags.get("transferLeft") else "PARADO"
            st.markdown(f"- **Transferência Esquerda (transferLeft):** <span class='{cls_tleft}'>{txt_tleft}</span>", unsafe_allow_html=True)

            cls_tright = "sensor-on" if tags.get("transferRight") else "sensor-off"
            txt_tright = "ATIVO ➡" if tags.get("transferRight") else "PARADO"
            st.markdown(f"- **Transferência Direita (transferRight):** <span class='{cls_tright}'>{txt_tright}</span>", unsafe_allow_html=True)

        with col_s3:
            st.markdown("### 🏁 Esteiras de Saída")
            cls_cleft = "sensor-on" if tags.get("conveyorLeft") else "sensor-off"
            txt_cleft = "RODANDO ▶" if tags.get("conveyorLeft") else "PARADA"
            st.markdown(f"- **Saída Esquerda (conveyorLeft):** <span class='{cls_cleft}'>{txt_cleft}</span>", unsafe_allow_html=True)

            cls_cright = "sensor-on" if tags.get("conveyorRight") else "sensor-off"
            txt_cright = "RODANDO ▶" if tags.get("conveyorRight") else "PARADA"
            st.markdown(f"- **Saída Direita (conveyorRight):** <span class='{cls_cright}'>{txt_cright}</span>", unsafe_allow_html=True)

            st.markdown(f"- **Contador de Peças:** `{tags.get('contador', 0)} caixas`")

    # -------------------------------------------------------------------------
    # TAB 2: REDE DE PETRI AO VIVO
    # -------------------------------------------------------------------------
    with tab2:
        st.subheader("Grafo de Estados da Rede de Petri (Modelo Formal do Gêmeo Digital)")
        st.caption("Os lugares com fichas ativas são iluminados em tempo real conforme as caixas se movem.")

        active_places = petri.get("active_places", [])

        places_info = {
            "p1": {"name": "p1 (Repouso)", "x": 0, "y": 2},
            "p2": {"name": "p2 (Entrada)", "x": 2, "y": 2},
            "p3": {"name": "p3 (Leitura Altura)", "x": 4, "y": 2},
            "p4": {"name": "p4 (Mesa Transfer)", "x": 6, "y": 2},
            "p5": {"name": "p5 (Caixa Alta)", "x": 5, "y": 3.5},
            "p6": {"name": "p6 (Caixa Baixa)", "x": 5, "y": 0.5},
            "p7": {"name": "p7 (Desvio Esq.)", "x": 8, "y": 3.5},
            "p8": {"name": "p8 (Desvio Dir.)", "x": 8, "y": 0.5},
            "p9": {"name": "p9 (Saída Alta)", "x": 10, "y": 3.5},
            "p10": {"name": "p10 (Saída Baixa)", "x": 10, "y": 0.5},
        }

        fig = go.Figure()

        for p_id, info in places_info.items():
            is_active = p_id in active_places
            fig.add_trace(go.Scatter(
                x=[info["x"]],
                y=[info["y"]],
                mode="markers+text",
                name=info["name"],
                text=[info["name"]],
                textposition="top center",
                marker=dict(
                    size=35 if is_active else 25,
                    color="#10b981" if is_active else "#374151",
                    line=dict(width=3, color="#6ee7b7" if is_active else "#1f2937")
                ),
                hoverinfo="text"
            ))

        fig.update_layout(
            showlegend=False,
            height=380,
            margin=dict(l=20, r=20, t=30, b=20),
            plot_bgcolor="#111827",
            paper_bgcolor="#111827",
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
        )

        st.plotly_chart(fig, use_container_width=True)

    # -------------------------------------------------------------------------
    # TAB 3: AUDITORIA E GOVERNANÇA (ISO/IEC 30173)
    # -------------------------------------------------------------------------
    with tab3:
        st.subheader("Log de Auditoria e Linhagem de Dados (ISO/IEC 30173)")
        st.caption("Registro cronológico dos eventos sanitizados recebidos pelo protocolo OPC UA.")

        recent_events = sanitizer.get("recent_events", [])
        if recent_events:
            df_events = pd.DataFrame(recent_events)
            cols_to_use = [c for c in ["timestamp_iso", "tag_name", "value", "quality", "source", "is_valid"] if c in df_events.columns]
            df_display = df_events[cols_to_use]
            st.dataframe(df_display, use_container_width=True, height=300)
        else:
            st.info("Nenhum evento registrado no histórico recente.")

    # -------------------------------------------------------------------------
    # TAB 4: MODELO AAS (ECLIPSE BASYX)
    # -------------------------------------------------------------------------
    with tab4:
        st.subheader("Casca Administrativa do Ativo (Asset Administration Shell - AAS)")
        st.caption("Estrutura oficial de submodelos para integração com ecossistemas BaSyx e Indústria 4.0.")

        st.json(aas)

        aas_json_str = json.dumps(aas, indent=2, ensure_ascii=False)
        st.download_button(
            label="📥 Baixar AAS em formato JSON (BaSyx)",
            data=aas_json_str,
            file_name="SortingByHeight_AAS_Model.json",
            mime="application/json"
        )


# Renderiza o dashboard ao vivo
render_live_dashboard()
