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
import concurrent.futures
import json
import time
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from opc_connector import DigitalTwinConnector
try:
    import ifc_viewer
except Exception:
    ifc_viewer = None

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
        margin-bottom: 16px;
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
            if not self.connector._monitor_task or self.connector._monitor_task.done():
                self.connector._monitor_task = self.loop.create_task(self.connector._periodic_monitor_loop())
            self.loop.run_forever()

    def execute_async(self, coro, timeout=15.0):
        """
        Executa comandos de forma thread-safe na thread do conector.
        Retorna: (sucesso: bool, resultado_ou_erro: Any, foi_timeout: bool)
        """
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        try:
            res = future.result(timeout=timeout)
            return True, res, False
        except concurrent.futures.TimeoutError:
            msg = f"Tempo limite ({timeout:.1f}s) esgotado aguardando resposta do CLP/OPC UA."
            print(f"[TIMEOUT AO EXECUTAR COMANDO]: {msg}")
            return False, msg, True
        except Exception as e:
            msg = f"Erro na execução do comando: {e}"
            print(f"[ERRO AO EXECUTAR COMANDO]: {msg}")
            return False, msg, False


@st.cache_resource
def get_service():
    """Garante que apenas UMA instância do conector OPC UA roda na aplicação."""
    return DigitalTwinBackgroundService()


service = get_service()
dt = service.connector


def execute_command(coro, success_msg: str, timeout: float = 15.0) -> bool:
    """
    Executa comando assíncrono no conector OPC UA, gerenciando timeouts e erros visíveis.
    Retorna True em caso de sucesso, False se houver falha ou timeout.
    """
    ok, res, is_timeout = service.execute_async(coro, timeout=timeout)
    if is_timeout:
        err_desc = (
            f"⏳ **TIMEOUT DE COMUNICAÇÃO ({timeout:.0f}s):** O comando demorou mais de {timeout:.0f} segundos para responder no CLP! "
            f"No seu notebook ou sob alta concorrência de CPU (CODESYS + Factory I/O + Docker), "
            f"as mensagens OPC UA podem acumular atraso ou o CLP demorou para responder."
        )
        st.session_state["last_opc_error"] = err_desc
        st.toast(f"⏳ ERRO: Timeout ({timeout:.0f}s) no CLP!", icon="⚠️")
        return False
    elif not ok:
        err_desc = f"❌ **ERRO OPC UA AO EXECUTAR COMANDO:** {res}"
        st.session_state["last_opc_error"] = err_desc
        st.toast(f"❌ Erro ao enviar comando: {res}", icon="🚨")
        return False
    else:
        st.session_state.pop("last_opc_error", None)
        st.toast(success_msg, icon="🚀" if ("🚀" in success_msg or "oper" in success_msg) else "✅")
        return True


# =============================================================================
# BARRA LATERAL (SIDEBAR): CONTROLE & INJEÇÃO DE FALHAS
# =============================================================================
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/robot-arm.png", width=70)
    st.title("Painel de Controle")
    st.caption("Controle Supervisório da Planta")

    # Indicador dinâmico de status da conexão OPC UA
    @st.fragment(run_every="1s")
    def render_sidebar_status():
        if dt.is_connected:
            st.success("🟢 OPC UA Conectado (CLP)", icon="⚡")
        else:
            st.warning("🟡 Reconectando ao CLP...", icon="⏳")

    render_sidebar_status()

    st.markdown("---")
    st.subheader("🎮 Comandos do Operador")

    # Botão de reinicialização completa (Reset + Rebobinar 3D + Start automático)
    if st.button("🚀 REINICIAR SISTEMA (Reset + Rebobinar + Start)", use_container_width=True, type="primary"):
        if dt.is_connected:
            with st.spinner("Reiniciando CLP, rebobinando física 3D e ligando esteira..."):
                if hasattr(dt, "restart_system"):
                    execute_command(dt.restart_system(), "Sistema reiniciado e em operação!", timeout=20.0)
                else:
                    async def _do_restart():
                        await dt.reset_plant()
                        await asyncio.sleep(1.0)
                        await dt.start_plant()
                    execute_command(_do_restart(), "Sistema reiniciado e em operação!", timeout=20.0)
        else:
            dt.petri_engine.clear_anomalies()
            dt.petri_engine.reset()
            st.toast("Gêmeo Digital reiniciado localmente.", icon="🔄")
        st.rerun()

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        if st.button("▶️ START", use_container_width=True):
            if dt.is_connected:
                execute_command(dt.start_plant(), "Comando START enviado para o CLP!", timeout=8.0)
            else:
                st.toast("Aguardando reconexão com o CLP...", icon="⏳")
            st.rerun()

    with col_c2:
        if st.button("🔄 RESET", use_container_width=True):
            if dt.is_connected:
                with st.spinner("Enviando comando RESET para o CLP..."):
                    execute_command(dt.reset_plant(), "Comando RESET enviado! Falhas limpas.", timeout=15.0)
            else:
                dt.petri_engine.clear_anomalies()
                dt.petri_engine.reset()
                st.toast("Falhas limpas localmente.", icon="🔄")
            st.rerun()

    col_e1, col_e2 = st.columns(2)
    with col_e1:
        if st.button("🛑 PARADA EMERG.", use_container_width=True):
            if dt.is_connected:
                execute_command(dt.emergency_stop(reason="Parada acionada manualmente no Dashboard"), "PARADA DE EMERGÊNCIA ATIVADA!", timeout=8.0)
            else:
                dt.petri_engine.inject_synthetic_anomaly("emergency_stop")
                st.toast("PARADA DE EMERGÊNCIA ATIVADA!", icon="🛑")
            st.rerun()
    with col_e2:
        if st.button("🗑️ ZERAR CONTAGEM", use_container_width=True):
            dt.petri_engine.reset(reset_counters=True)
            st.toast("Contadores zerados!", icon="🗑️")
            st.rerun()

    st.markdown("---")
    st.caption("Padrão: ISO/IEC 30173 & ISO 23247")
    st.caption(f"Protocolo: OPC UA ({dt.url})")


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
    caixas_esq = petri.get("caixas_esquerda", 0)
    caixas_dir = petri.get("caixas_direita", 0)
    caixas_tot = petri.get("caixas_total", caixas_esq + caixas_dir)

    # Banner de aviso quando desconectado do CLP
    if not state.get("is_connected", False):
        st.warning("⏳ **Conexão com o CLP (CODESYS) em processo de reconexão automática...** O painel se recupera automaticamente assim que o sinal OPC UA for restabelecido.", icon="⚠️")

    # Banner de aviso para Timeout ou Erros de Comando OPC UA
    if st.session_state.get("last_opc_error"):
        col_err1, col_err2 = st.columns([5, 1])
        with col_err1:
            st.error(st.session_state["last_opc_error"], icon="⏳")
        with col_err2:
            st.write("")
            if st.button("✖️ Fechar Erro", key="btn_dismiss_opc_err", use_container_width=True):
                st.session_state.pop("last_opc_error", None)
                st.rerun()

    # Banner de Alerta Crítico se houver falha
    if health == "CRITICAL_FAULT":
        col_b1, col_b2 = st.columns([5, 1])
        with col_b1:
            first_anom = anomalies[0] if anomalies else {}
            backend_msg = first_anom.get('backend_message', '')
            backend_line = f"\n            **Mensagem Original da Rede de Petri (Backend):** `{backend_msg}`  " if backend_msg else ""
            st.error(f"""
            ### 🚨 PARADA DE EMERGÊNCIA ATIVADA PELO GÊMEO DIGITAL!
            **Anomalia Detectada:** {first_anom.get('message', 'Violação no modelo de segurança')}  {backend_line}
            **Componente Afetado:** `{first_anom.get('component', 'Desconhecido')}`  
            **Ação Recomendada:** {first_anom.get('suggested_action', 'Inspecione a planta física')}
            """)
        with col_b2:
            st.write("")
            st.write("")
            if st.button("🚀 REINICIAR SISTEMA", key="btn_reset_banner", use_container_width=True, type="primary"):
                if dt.is_connected:
                    with st.spinner("Reiniciando CLP, rebobinando física 3D e ligando esteira..."):
                        if hasattr(dt, "restart_system"):
                            execute_command(dt.restart_system(), "Sistema reiniciado e em operação!", timeout=20.0)
                        else:
                            async def _do_restart():
                                await dt.reset_plant()
                                await asyncio.sleep(1.0)
                                await dt.start_plant()
                            execute_command(_do_restart(), "Sistema reiniciado e em operação!", timeout=20.0)
                else:
                    dt.petri_engine.clear_anomalies()
                    dt.petri_engine.reset()
                    st.toast("Gêmeo Digital reiniciado localmente.", icon="🔄")
                st.rerun()

    # -------------------------------------------------------------------------
    # CARDS DE MÉTRICAS OPERACIONAIS
    # -------------------------------------------------------------------------
    col1, col2 = st.columns(2)

    with col1:
        cls_status = "status-critical" if health == "CRITICAL_FAULT" else "status-healthy"
        txt_status = "🔴 PARADA DE EMERGÊNCIA" if health == "CRITICAL_FAULT" else "🟢 OPERACIONAL"
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #9ca3af; font-size: 0.9rem;">STATUS DE SAÚDE DA PLANTA</div>
            <div class="{cls_status}">{txt_status}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        active_p = petri.get("active_places", ["p1"])
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #9ca3af; font-size: 0.9rem;">ESTADO ATIVO NA REDE DE PETRI</div>
            <div style="color: #34d399; font-size: 1.4rem; font-weight: bold;">{', '.join(active_p) if active_p else 'p1'}</div>
        </div>
        """, unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # ESPAÇAMENTO VERTICAL ENTRE LINHAS DE MÉTRICAS
    # -------------------------------------------------------------------------
    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # CARDS DE CLASSIFICAÇÃO DE PRODUÇÃO (ESQUERDA / DIREITA)
    # -------------------------------------------------------------------------
    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        st.markdown(f"""
        <div class="metric-card" style="border-left: 4px solid #3b82f6;">
            <div style="color: #93c5fd; font-size: 0.85rem; font-weight: 600;">⬅️ CLASSIFICADAS À ESQUERDA (BAIXAS)</div>
            <div style="color: #60a5fa; font-size: 1.8rem; font-weight: bold;">{caixas_esq} <span style="font-size: 1rem; color: #9ca3af;">caixas</span></div>
        </div>
        """, unsafe_allow_html=True)

    with col_p2:
        st.markdown(f"""
        <div class="metric-card" style="border-left: 4px solid #a855f7;">
            <div style="color: #d8b4fe; font-size: 0.85rem; font-weight: 600;">➡️ CLASSIFICADAS À DIREITA (ALTAS)</div>
            <div style="color: #c084fc; font-size: 1.8rem; font-weight: bold;">{caixas_dir} <span style="font-size: 1rem; color: #9ca3af;">caixas</span></div>
        </div>
        """, unsafe_allow_html=True)

    with col_p3:
        st.markdown(f"""
        <div class="metric-card" style="border-left: 4px solid #10b981;">
            <div style="color: #6ee7b7; font-size: 0.85rem; font-weight: 600;">📦 TOTAL GERAL CLASSIFICADO</div>
            <div style="color: #34d399; font-size: 1.8rem; font-weight: bold;">{caixas_tot} <span style="font-size: 1rem; color: #9ca3af;">caixas</span></div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # ABAS PRINCIPAIS DO SUPERVISÓRIO
    # -------------------------------------------------------------------------
    tab1, tab2, tab3 = st.tabs([
        "🏭 Sinótico da Planta 2D",
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
            st.markdown("### 🏁 Esteiras de Saída & Produção")
            cls_cleft = "sensor-on" if tags.get("conveyorLeft") else "sensor-off"
            txt_cleft = "RODANDO ▶" if tags.get("conveyorLeft") else "PARADA"
            st.markdown(f"- **Saída Esquerda (conveyorLeft):** <span class='{cls_cleft}'>{txt_cleft}</span>", unsafe_allow_html=True)

            cls_cright = "sensor-on" if tags.get("conveyorRight") else "sensor-off"
            txt_cright = "RODANDO ▶" if tags.get("conveyorRight") else "PARADA"
            st.markdown(f"- **Saída Direita (conveyorRight):** <span class='{cls_cright}'>{txt_cright}</span>", unsafe_allow_html=True)

            st.markdown("---")
            st.markdown(f"- ⬅️ **Caixas Baixas (Esquerda):** `{caixas_esq}`")
            st.markdown(f"- ➡️ **Caixas Altas (Direita):** `{caixas_dir}`")
            st.markdown(f"- 📦 **Total Classificadas:** `{caixas_tot}` *(CLP: {tags.get('contador', 0)})*")

    # -------------------------------------------------------------------------
    # TAB 2: AUDITORIA E GOVERNANÇA (ISO/IEC 30173)
    # -------------------------------------------------------------------------
    with tab2:
        st.subheader("Indicadores de Governança e Qualidade de Dados (ISO/IEC 30173)")
        st.caption("Métricas em tempo real de conformidade, integridade e filtragem da telemetria OPC UA.")

        col_q1, col_q2, col_q3, col_q4 = st.columns(4)
        with col_q1:
            st.markdown(f"""
            <div class="metric-card" style="border-left: 4px solid #3b82f6;">
                <div style="color: #93c5fd; font-size: 0.85rem; font-weight: 600;">QUALIDADE DOS DADOS (ISO 30173)</div>
                <div style="color: #60a5fa; font-size: 1.8rem; font-weight: bold;">{sanitizer.get('data_quality_percentage', 100)}%</div>
            </div>
            """, unsafe_allow_html=True)
        with col_q2:
            st.markdown(f"""
            <div class="metric-card" style="border-left: 4px solid #8b5cf6;">
                <div style="color: #c4b5fd; font-size: 0.85rem; font-weight: 600;">TOTAL DE EVENTOS RECEBIDOS</div>
                <div style="color: #a78bfa; font-size: 1.8rem; font-weight: bold;">{sanitizer.get('total_received', 0)}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_q3:
            st.markdown(f"""
            <div class="metric-card" style="border-left: 4px solid #10b981;">
                <div style="color: #6ee7b7; font-size: 0.85rem; font-weight: 600;">EVENTOS SANITIZADOS (VÁLIDOS)</div>
                <div style="color: #34d399; font-size: 1.8rem; font-weight: bold;">{sanitizer.get('total_sanitized', 0)}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_q4:
            st.markdown(f"""
            <div class="metric-card" style="border-left: 4px solid #f59e0b;">
                <div style="color: #fde68a; font-size: 0.85rem; font-weight: 600;">RUÍDOS / REBOTES FILTRADOS</div>
                <div style="color: #fbbf24; font-size: 1.8rem; font-weight: bold;">{sanitizer.get('total_filtered_noise', 0)}</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)

        st.subheader("Log de Auditoria e Linhagem de Dados")
        st.caption("Registro cronológico dos eventos sanitizados recebidos pelo protocolo OPC UA.")

        recent_events = sanitizer.get("recent_events", [])
        if recent_events:
            df_events = pd.DataFrame(recent_events)
            cols_to_use = [c for c in ["timestamp_iso", "tag_name", "value", "quality", "source", "is_valid"] if c in df_events.columns]
            df_display = df_events[cols_to_use].astype(str)
            st.dataframe(df_display, use_container_width=True, height=250)

            # Botão de exportação para CSV (Governança e Auditoria)
            csv_data = df_display.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Baixar Log de Auditoria em CSV (Excel)",
                data=csv_data,
                file_name="Auditoria_Governanca_ISO30173.csv",
                mime="text/csv"
            )
        else:
            st.info("Nenhum evento registrado no histórico recente.")

        st.markdown("---")
        st.subheader("🚨 Histórico de Laudos de Anomalias (AnomalyReport)")
        st.caption("Registro formal de todas as anomalias detectadas, com fotografia da Rede de Petri no momento do erro e ação recomendada.")

        anomaly_history = petri.get("anomaly_history") or petri.get("active_anomalies", [])
        if anomaly_history:
            df_anom = pd.DataFrame(anomaly_history)
            cols_anom = [c for c in ["timestamp_iso", "anomaly_id", "severity", "component", "message", "backend_message", "current_marking", "suggested_action"] if c in df_anom.columns]
            st.dataframe(df_anom[cols_anom].astype(str), use_container_width=True, height=220)
        else:
            st.success("✅ Nenhuma anomalia registrada no histórico de operação.")

    # -------------------------------------------------------------------------
    # TAB 3: MODELO AAS (ECLIPSE BASYX)
    # -------------------------------------------------------------------------
    with tab3:
        st.subheader("Casca Administrativa do Ativo (Asset Administration Shell - AAS)")
        st.caption("Estrutura oficial de submodelos para integração com ecossistemas BaSyx e Indústria 4.0.")

        st.json(aas)

        aas_json_str = json.dumps(aas, indent=2, ensure_ascii=False)
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button(
                label="📥 Baixar AAS em formato JSON (BaSyx)",
                data=aas_json_str,
                file_name="SortingByHeight_AAS_Model.json",
                mime="application/json",
                use_container_width=True
            )
        with col_d2:
            try:
                aasx_bytes = dt.aas.to_aasx_bytes()
                st.download_button(
                    label="📦 Baixar Pacote Oficial AASX (.aasx)",
                    data=aasx_bytes,
                    file_name="SortingByHeight_AAS.aasx",
                    mime="application/asset-administration-shell-package",
                    use_container_width=True
                )
            except Exception as e:
                st.caption(f"AASX: {e}")

    # -------------------------------------------------------------------------
    # TAB 5: VISUALIZAÇÃO 3D A PARTIR DO MODELO BIM/IFC REAL (OCULTA TEMPORARIAMENTE)
    # -------------------------------------------------------------------------
    # with tab5:
    #     st.subheader("Cena 3D gerada a partir do modelo IFC real (ISO 16739)")
    #     st.caption("Geometria extraída via ifcopenshell de `gemeo-digital/models/sorting_by_height.ifc`. Cada elemento é colorido pelo estado ao vivo do Gêmeo Digital: cinza = parado, verde = ativo/detectando, vermelho = componente citado em anomalia crítica.")
    # 
    #     if ifc_viewer is None or not ifc_viewer.ifc_model_available():
    #         st.warning("Visualização IFC indisponível (pacote ifcopenshell ausente ou modelo IFC não encontrado).")
    #     else:
    #         fig_3d = ifc_viewer.build_3d_figure(tags, petri)
    #         st.plotly_chart(fig_3d, use_container_width=True, key="ifc_3d_view")
    #         st.caption("Coordenadas nominais/aproximadas (não medidas via laser scan da cena real do Factory I/O) — ver `models/build_ifc_model.py`.")


# Renderiza o dashboard ao vivo
render_live_dashboard()
