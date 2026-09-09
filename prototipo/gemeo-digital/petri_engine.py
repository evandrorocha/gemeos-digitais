"""
Motor de Diagnóstico baseado em Rede de Petri do Gêmeo Digital
Integra o modelo formal da Rede de Petri (backend/redeDePetri.py) com detecção em tempo real
de falhas de sensores físicos do Factory I/O (Stuck ON, Stuck OFF, Violação de Sequência e Timeouts).
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import sys
import time
from typing import Dict, List, Optional, Any

logger = logging.getLogger("PETRI_ENGINE")

# Importação da classe formal RedePetri criada no backend
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

try:
    from redeDePetri import RedePetri
except ImportError:
    RedePetri = None

if RedePetri is None:
    class RedePetri:
        """Implementação formal de contingência caso backend/redeDePetri.py não esteja acessível."""
        def __init__(self, estados=None, lugares2transicoes=None, transicoes2lugares=None, eventos=None, variaveis=None, condicoes=None):
            self.estados = estados if estados is not None else {}
            self.lugares2transicoes = lugares2transicoes if lugares2transicoes is not None else {}
            self.transicoes2lugares = transicoes2lugares if transicoes2lugares is not None else {}
            self.eventos = eventos if eventos is not None else {}
            self.variaveis = variaveis if variaveis is not None else {}
            self.condicoes = condicoes if condicoes is not None else {}

        def adicionar_estado(self, lugar, fichas=0):
            self.estados[lugar] = fichas

        def adicionar_transicao(self, lugar_origem, transicao, lugares_destino):
            if lugar_origem not in self.lugares2transicoes:
                self.lugares2transicoes[lugar_origem] = []
            if transicao not in self.lugares2transicoes[lugar_origem]:
                self.lugares2transicoes[lugar_origem].append(transicao)
            self.transicoes2lugares[transicao] = lugares_destino

        def adicionar_evento(self, evento, transicoes):
            self.eventos[evento] = transicoes

        def adicionar_variavel(self, nome, valor=0):
            self.variaveis[nome] = valor

        def atualizar_variavel(self, nome, valor):
            self.variaveis[nome] = valor

        def transicao_pode_disparar(self, transicao):
            if transicao in self.condicoes:
                variavel, valor_esperado = self.condicoes[transicao]
                if self.variaveis.get(variavel) != valor_esperado:
                    return False
            return True

        def transicoes_disponiveis(self):
            entradas = {}
            for lugar, transicoes in self.lugares2transicoes.items():
                for transicao in transicoes:
                    if transicao not in entradas:
                        entradas[transicao] = []
                    entradas[transicao].append(lugar)

            disponiveis = {}
            for transicao, lugares in entradas.items():
                fichas_disponiveis = all(self.estados.get(lugar, 0) > 0 for lugar in lugares)
                if not fichas_disponiveis:
                    continue
                if not self.transicao_pode_disparar(transicao):
                    continue
                disponiveis[transicao] = lugares
            return disponiveis

        def processar_evento(self, evento):
            if evento not in self.eventos:
                return False, f"Falha: evento '{evento}' nao esta cadastrado."

            transicoes_evento = self.eventos[evento]
            disponiveis = self.transicoes_disponiveis()
            transicoes_escolhidas = [t for t in transicoes_evento if t in disponiveis]

            if not transicoes_escolhidas:
                return False, f"Falha: nenhuma transicao associada ao evento '{evento}' esta habilitada."

            for transicao in transicoes_escolhidas:
                for lugar in disponiveis[transicao]:
                    self.estados[lugar] -= 1
                for lugar in self.transicoes2lugares[transicao]:
                    if lugar in self.estados:
                        self.estados[lugar] += 1

            while True:
                disponiveis = self.transicoes_disponiveis()
                transicao_lambda = None
                lugares_origem = None
                for transicao, lugares in disponiveis.items():
                    if not any(transicao in transicoes for transicoes in self.eventos.values()):
                        transicao_lambda = transicao
                        lugares_origem = lugares
                        break
                if transicao_lambda is None:
                    break
                for lugar in lugares_origem:
                    self.estados[lugar] -= 1
                for lugar in self.transicoes2lugares[transicao_lambda]:
                    if lugar in self.estados:
                        self.estados[lugar] += 1

            return True, f"Evento '{evento}' processado com sucesso."

        def mostrar_estados(self):
            print("Estados:", {k: v for k, v in self.estados.items() if v > 0})

from config import (
    TIMEOUT_CONVEYOR_ENTRY_SEC,
    TIMEOUT_TRANSFER_SEC,
    MAX_PRESENCE_TIME_SEC
)
from data_sanitizer import SanitizedEvent


@dataclass
class AnomalyReport:
    """Relatório estruturado de anomalia detectada pelo Gêmeo Digital (ISO/IEC 30173)."""
    anomaly_id: str
    anomaly_type: str
    severity: str  # "CRITICAL", "WARNING", "INFO"
    component: str
    message: str
    timestamp_iso: str
    timestamp_unix: float
    current_marking: List[str]
    suggested_action: str
    backend_message: str = ""
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def create_initial_petri_net() -> RedePetri:
    """
    Constrói a instância formal da Rede de Petri do processo Sorting by Height,
    utilizando exatamente a topologia e transições definidas na arquitetura.
    """

    # Lugares (marcação inicial: p1 = 1 para repouso, p16 = 1 para mesa livre)
    lugares = {
        "p1": 1, "p2": 0, "p3": 0, "p4": 0,
        "p5": 0, "p6": 0, "p7": 0, "p8": 0,
        "p9": 0, "p10": 0, "p11": 0, "p12": 0,
        "p13": 0, "p16": 1
    }

    # Transições de saída de cada lugar
    lugares2transicoes = {
        "p1": ["t1"],
        "p2": ["t2"],
        "p3": ["t3"],
        "p4": ["t4"],
        "p5": ["t5", "t8"],
        "p6": ["t6"],
        "p7": ["t7"],
        "p8": ["t9"],
        "p9": ["t10"],
        "p10": ["t11"],
        "p11": ["t12", "t14"],
        "p12": ["t13"],
        "p13": ["t15"],
        "p16": ["t3"]
    }

    # Lugares de destino de cada transição
    transicoes2lugares = {
        "t1": ["p2", "p11"],
        "t2": ["p3"],
        "t3": ["p2", "p4"],
        "t4": ["p5"],
        "t5": ["p6"],
        "t6": ["p7", "p16"],
        "t7": ["p10"],
        "t8": ["p8"],
        "t9": ["p9", "p16"],
        "t10": ["p10"],
        "t11": ["empty"],
        "t12": ["p12"],
        "t13": ["p1"],
        "t14": ["p13"],
        "t15": ["p1"]
    }

    # Associação entre eventos de chão de fábrica e transições
    eventos = {
        "start_P": ["t1"],
        "palletSensor_P": ["t2"],
        "loaded_P": ["t4"],
        "atLeftEntry_P": ["t6"],
        "atLeftExit_P": ["t7"],
        "atRightEntry_P": ["t9"],
        "atRightExit_P": ["t10"],
        "stop_P": ["t12"],
        "reset_P": ["t14"]
    }

    # Variáveis internas e condições de guarda
    variaveis = {"alto": 0}
    condicoes = {
        "t5": ("alto", 0),
        "t8": ("alto", 1)
    }

    return RedePetri(
        estados=lugares,
        lugares2transicoes=lugares2transicoes,
        transicoes2lugares=transicoes2lugares,
        eventos=eventos,
        variaveis=variaveis,
        condicoes=condicoes
    )


class PetriNetEngine:
    """
    Motor de Diagnóstico Industrial do Gêmeo Digital:
    - Executa o motor formal da Rede de Petri (RedePetri) a partir dos eventos sanitizados do CLP.
    - Diagnostica violações de sequência causadas por sensores que falharam ou foram pulados.
    - Monitora temporizações contínuas de transporte e tempos máximos de presença (Stuck ON/OFF).
    - Reporta anomalias estruturadas em tempo real e orquestra a parada autônoma de segurança.
    """

    NO_SENSORS = ["palletSensor", "highSensor", "loaded"]
    NC_SENSORS = ["atLeftEntry", "atLeftExit", "atRightEntry", "atRightExit", "stop"]
    MONITORED_SENSORS = ["palletSensor", "highSensor", "loaded", "atLeftEntry", "atLeftExit", "atRightEntry", "atRightExit"]

    def __init__(self):
        # Núcleo formal da Rede de Petri
        self.petri_net = create_initial_petri_net()

        # Último estado das tags de processo conhecidas
        self.tags: Dict[str, Any] = {
            "start": False, "stop": False, "reset": False, "desligar": False,
            "palletSensor": False, "highSensor": False, "loaded": False, "alto": False,
            "conveyorEntry": False, "conveyorLeft": False, "conveyorRight": False,
            "transferLeft": False, "transferRight": False, "load": False,
            "atLeftEntry": False, "atLeftExit": False, "atRightEntry": False, "atRightExit": False,
            "contador": 0
        }

        # Histórico de valor anterior para detecção precisa de bordas (_P / _N)
        self._prev_tags: Dict[str, Any] = {}

        # Temporizadores de presença e transporte
        self._sensor_high_start_time: Dict[str, Optional[float]] = {}
        self._box_in_transit_start_time: Optional[float] = None
        self._transfer_left_start_time: Optional[float] = None
        self._transfer_right_start_time: Optional[float] = None
        self._exit_left_start_time: Optional[float] = None
        self._exit_right_start_time: Optional[float] = None

        # Contadores de classificação de produção
        self.caixas_esquerda: int = 0
        self.caixas_direita: int = 0
        self.total_historico_esquerda: int = 0
        self.total_historico_direita: int = 0
        self._last_direction: str = "esquerda"
        self._last_plc_counter: int = 0

        # Histórico de anomalias
        self.active_anomalies: List[AnomalyReport] = []
        self.anomaly_history: List[AnomalyReport] = []

    def set_baseline_tags(self, baseline: Dict[str, Any]):
        """Inicializa o estado e histórico com a leitura inicial do CLP sem disparar falsas bordas."""
        now = time.time()
        for k, v in baseline.items():
            self.tags[k] = v
            self._prev_tags[k] = v
            if k == "contador" and isinstance(v, (int, float)):
                self._last_plc_counter = int(v)
            if k == "transferRight" and v:
                self._transfer_right_start_time = now
            if k == "transferLeft" and v:
                self._transfer_left_start_time = now
            if k == "conveyorEntry" and v and baseline.get("palletSensor"):
                self._box_in_transit_start_time = now

    def update_from_sanitized_event(self, event: SanitizedEvent) -> Optional[AnomalyReport]:
        """
        Processa um evento industrial sanitizado do OPC UA, atualiza a Rede de Petri,
        detecta bordas de subida/descida e executa a verificação de anomalias.
        """
        tag = event.tag_name
        val = event.value
        old_val = self._prev_tags.get(tag, None)

        # Atualiza o estado atual da tag
        self.tags[tag] = val
        now = time.time()

        # Detecção de borda (Rising Edge: _P, Falling Edge: _N)
        edge_event = None
        if isinstance(val, bool):
            if val is True and old_val is not True:
                # Se for a primeira leitura da conexão (old_val is None) em repouso e a tag for NF, não gera falso pulso
                if old_val is None and tag in self.NC_SENSORS and self.petri_net.estados.get("p1", 0) > 0:
                    pass
                else:
                    edge_event = f"{tag}_P"
                    if tag in self.NO_SENSORS:
                        self._sensor_high_start_time[tag] = now
                    else:
                        # Sensor NC desobstruído (feixe restaurado): limpa timer
                        self._sensor_high_start_time[tag] = None
            elif val is False and old_val is not False:
                # Se for a primeira leitura da conexão (old_val is None) em repouso e a tag for NA, não gera falso pulso
                if old_val is None and tag in self.NO_SENSORS and self.petri_net.estados.get("p1", 0) > 0:
                    pass
                else:
                    edge_event = f"{tag}_N"
                    if tag in self.NC_SENSORS:
                        # Sensor NC cortado/bloqueado: inicia timer de permanência
                        self._sensor_high_start_time[tag] = now
                    else:
                        # Sensor NA livre: limpa timer
                        self._sensor_high_start_time[tag] = None
        elif isinstance(val, (int, float)):
            # Tags numéricas (ex: contador do CLP)
            if old_val is not None and val != old_val:
                edge_event = f"{tag}_{val}"

        self._prev_tags[tag] = val
        if edge_event:
            logger.info(f"⚡ [EVENTO]: {edge_event} | Estados ativos: {[k for k,v in self.petri_net.estados.items() if v > 0]}")

        # Atualização da variável interna 'alto' quando o CLP reporta a classificação
        if edge_event == "alto_P":
            self.petri_net.atualizar_variavel("alto", 1)
        elif edge_event == "alto_N":
            self.petri_net.atualizar_variavel("alto", 0)

        # Se o operador apertar o botão físico RESET no Factory I/O:
        if edge_event == "reset_P":
            self.reset()
            return None

        # ---------------------------------------------------------------------
        # AUTO-RECUPERAÇÃO: Remove anomalias ativas quando a condição física normaliza
        # ---------------------------------------------------------------------
        # 1. Qualquer transição de um sensor (_P ou _N) prova que ele não está travado
        if edge_event:
            sensor_name = edge_event[:-2]
            if sensor_name in self.MONITORED_SENSORS or sensor_name == "stop":
                self.auto_clear_anomaly_for_component(sensor_name)

        # 3. Se um sensor que estava com Stuck OFF ou Timeout voltou a emitir pulso (_P):
        if edge_event and edge_event.endswith("_P"):
            sensor_name = edge_event[:-2]
            self.auto_clear_anomaly_for_component(sensor_name)

        # 4. Ao iniciar novo ciclo (start_P) ou reset (reset_P), limpa anomalias
        if edge_event in ["start_P", "reset_P"]:
            self.clear_anomalies()

        # Rastreamento da rota de classificação ativa (Esquerda = Baixa, Direita = Alta)
        if edge_event == "transferLeft_P" or (tag == "transferLeft" and val):
            self._last_direction = "esquerda"
        elif edge_event == "transferRight_P" or (tag == "transferRight" and val):
            self._last_direction = "direita"
        elif edge_event == "loaded_P":
            if self.tags.get("alto") or self.tags.get("highSensor") or self.petri_net.variaveis.get("alto") == 1:
                self._last_direction = "direita"
            else:
                self._last_direction = "esquerda"

        # Atualização dos rastreadores de movimento físico e contadores de produção
        if edge_event == "palletSensor_P":
            self._box_in_transit_start_time = now
        elif edge_event in ["loaded_P", "loaded_N"]:
            self._box_in_transit_start_time = None
        elif edge_event == "atLeftEntry_P":
            self._exit_left_start_time = now
        elif edge_event == "atLeftExit_P":
            self.caixas_esquerda += 1
            self.total_historico_esquerda += 1
            self._exit_left_start_time = None
        elif edge_event == "atRightEntry_P":
            self._exit_right_start_time = now
        elif edge_event == "atRightExit_P":
            self.caixas_direita += 1
            self.total_historico_direita += 1
            self._exit_right_start_time = None

        # Sincronização direta com o contador de peças físico do CLP
        if tag == "contador" and isinstance(val, (int, float)):
            val_int = int(val)
            if old_val is not None:
                old_int = int(old_val)
                if val_int > old_int:
                    delta = val_int - old_int
                    twin_total = self.caixas_esquerda + self.caixas_direita
                    if twin_total < val_int:
                        missing = min(delta, val_int - twin_total)
                        if self._last_direction == "direita":
                            self.caixas_direita += missing
                            self.total_historico_direita += missing
                        else:
                            self.caixas_esquerda += missing
                            self.total_historico_esquerda += missing
            self._last_plc_counter = val_int

        if tag == "transferLeft":
            self._transfer_left_start_time = now if val else None
        elif tag == "transferRight":
            self._transfer_right_start_time = now if val else None
        elif tag == "conveyorEntry" and not val:
            if not self.tags.get("load") and self.petri_net.estados.get("p4", 0) == 0:
                self._box_in_transit_start_time = None

        # Sincronização automática: se a esteira está rodando e a Rede de Petri ainda está em p1,
        # significa que a linha iniciou mesmo que o pulso elétrico do botão de start tenha sido instantâneo.
        if self.petri_net.estados.get("p1", 0) > 0:
            if edge_event in ["start_P", "conveyorEntry_P"] or self.tags.get("conveyorEntry"):
                self.petri_net.processar_evento("start_P")
                if self.tags.get("palletSensor") and self.petri_net.estados.get("p2", 0) > 0:
                    self.petri_net.processar_evento("palletSensor_P")
                return None
            elif edge_event == "palletSensor_P":
                self._box_in_transit_start_time = now
                return self.check_anomalies()

        # Se um sensor de saída (atLeftExit ou atRightExit) aciona fora de p7/p9 mas sem pular entrada (não em p6/p8),
        # trata-se do escoamento normal de uma caixa de ciclo anterior pela esteira de saída.
        if edge_event == "atLeftExit_P" and self.petri_net.estados.get("p6", 0) == 0 and self.petri_net.estados.get("p7", 0) == 0:
            return self.check_anomalies()
        if edge_event == "atRightExit_P" and self.petri_net.estados.get("p8", 0) == 0 and self.petri_net.estados.get("p9", 0) == 0:
            return self.check_anomalies()

        # Verificação imediata: Peça chegou em loaded sem token em p4 (palletSensor não detectou a peça)
        if edge_event == "loaded_P" and self.petri_net.estados.get("p4", 0) == 0:
            anomaly = self._diagnose_sequence_violation(edge_event, "Peça atingiu a mesa transfer sem detecção no palletSensor")
            return self._register_anomaly(anomaly)

        # Disparo da transição formal na Rede de Petri caso o evento pertença ao modelo
        if edge_event and edge_event in self.petri_net.eventos:
            sucesso, msg = self.petri_net.processar_evento(edge_event)
            if not sucesso:
                # Transição não permitida: O evento ocorreu fora da ordem esperada da planta!
                anomaly = self._diagnose_sequence_violation(edge_event, msg)
                return self._register_anomaly(anomaly)

            # Se acabamos de dar partida (p1 -> p2) e já existia uma caixa aguardando no palletSensor:
            if edge_event == "start_P" and self.tags.get("palletSensor"):
                if self.petri_net.estados.get("p2", 0) > 0:
                    self.petri_net.processar_evento("palletSensor_P")

        # Executa a checagem contínua de anomalias (timeouts e stuck)
        return self.check_anomalies()

    def auto_clear_anomaly_for_component(self, component_name: str, anomaly_type: Optional[str] = None):
        """
        Desativa automaticamente as anomalias ativas quando o sensor correspondente
        volta a responder dentro dos parâmetros normais de operação.
        """
        remaining = []
        cleared_any = False
        for anom in self.active_anomalies:
            match_comp = (not component_name) or (component_name.lower() in anom.component.lower())
            match_type = (anomaly_type is None) or (anom.anomaly_type == anomaly_type)
            if match_comp and match_type and anom.is_active:
                anom.is_active = False
                cleared_any = True
            else:
                remaining.append(anom)
        self.active_anomalies = remaining
        if cleared_any and component_name in self._sensor_high_start_time:
            self._sensor_high_start_time[component_name] = None

    def _diagnose_sequence_violation(self, edge_event: str, error_msg: str) -> AnomalyReport:
        """
        Interpreta uma falha matemática de disparo de transição e diagnostica
        a causa-raiz física no Factory I/O (qual sensor falhou ou foi pulado).
        """
        now = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        current_active = [p for p, fichas in self.petri_net.estados.items() if fichas > 0]

        # Caso 1: Sensor loaded acionou sem passar pelo palletSensor (p4 vazio e p2 ativo -> Stuck OFF na entrada)
        if edge_event == "loaded_P" and self.petri_net.estados.get("p4", 0) == 0 and self.petri_net.estados.get("p2", 0) > 0:
            return AnomalyReport(
                anomaly_id=f"ANOM_SEQ_PALLET_{int(now)}",
                anomaly_type="SENSOR_STUCK_OFF",
                severity="CRITICAL",
                component="palletSensor (Sensor de Presença na Entrada)",
                message=f"Violação de Sequência: Peça atingiu a mesa transfer (loaded) sem ser detectada pelo sensor de entrada. Sensor 'palletSensor' falhou (Stuck OFF / Aberto)! [Backend: \"{error_msg}\"]",
                timestamp_iso=now_iso,
                timestamp_unix=now,
                current_marking=current_active,
                suggested_action="Inspecione o sensor óptico 'palletSensor' no Factory I/O (remova a falha Fail OFF ou desobstrua a lente).",
                backend_message=error_msg
            )

        # Caso 2: Sensor de saída atLeftExit acionou sem passar por atLeftEntry (Stuck OFF no desvio esquerdo)
        if edge_event == "atLeftExit_P" and self.petri_net.estados.get("p6", 0) > 0:
            return AnomalyReport(
                anomaly_id=f"ANOM_SEQ_ATLEFT_{int(now)}",
                anomaly_type="SENSOR_STUCK_OFF",
                severity="CRITICAL",
                component="atLeftEntry (Sensor Entrada Saída Esquerda)",
                message=f"Violação de Sequência: Peça atingiu o fim da linha esquerda sem ser detectada na entrada do desvio. Sensor 'atLeftEntry' falhou (Stuck OFF)! [Backend: \"{error_msg}\"]",
                timestamp_iso=now_iso,
                timestamp_unix=now,
                current_marking=current_active,
                suggested_action="Inspecione o sensor 'atLeftEntry' no Factory I/O (remova a falha Fail OFF).",
                backend_message=error_msg
            )

        # Caso 3: Sensor de saída atRightExit acionou sem passar por atRightEntry (Stuck OFF no desvio direito)
        if edge_event == "atRightExit_P" and self.petri_net.estados.get("p8", 0) > 0:
            return AnomalyReport(
                anomaly_id=f"ANOM_SEQ_ATRIGHT_{int(now)}",
                anomaly_type="SENSOR_STUCK_OFF",
                severity="CRITICAL",
                component="atRightEntry (Sensor Entrada Saída Direita)",
                message=f"Violação de Sequência: Peça atingiu o fim da linha direita sem ser detectada na entrada do desvio. Sensor 'atRightEntry' falhou (Stuck OFF)! [Backend: \"{error_msg}\"]",
                timestamp_iso=now_iso,
                timestamp_unix=now,
                current_marking=current_active,
                suggested_action="Inspecione o sensor 'atRightEntry' no Factory I/O (remova a falha Fail OFF).",
                backend_message=error_msg
            )

        # Violação formal de sequência em estados ativos
        comp_name = edge_event.replace("_P", "").replace("_N", "")
        return AnomalyReport(
            anomaly_id=f"ANOM_ILLEGAL_TRANS_{int(now)}",
            anomaly_type="ILLEGAL_TRANSITION",
            severity="CRITICAL",
            component=comp_name,
            message=f"Violação Formal de Estados: O evento '{edge_event}' ocorreu fora da sequência esperada na marcação {current_active}. [Backend: \"{error_msg}\"]",
            timestamp_iso=now_iso,
            timestamp_unix=now,
            current_marking=current_active,
            suggested_action=f"Verifique o alinhamento da planta, sensores e se o componente '{comp_name}' falhou ou foi acionado indevidamente.",
            backend_message=error_msg
        )

    def check_anomalies(self) -> Optional[AnomalyReport]:
        """
        Verificações periódicas de anomalias.
        Atualmente todas as regras de timeout e inconsistência customizadas foram removidas,
        confiando exclusivamente nas transições formais da Rede de Petri do backend.
        """
        return None

    def inject_synthetic_anomaly(self, anomaly_type: str) -> AnomalyReport:
        """Permite injetar anomalias programadas para testes e demonstrações de auditoria."""
        now = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        current_active = [p for p, v in self.petri_net.estados.items() if v > 0]

        if anomaly_type == "STUCK_OFF_HIGH_SENSOR":
            anomaly = AnomalyReport(
                anomaly_id=f"SYNTH_STUCK_OFF_{int(now)}",
                anomaly_type="SENSOR_STUCK_OFF",
                severity="CRITICAL",
                component="highSensor (Sensor de Altura)",
                message="[FALHA INJETADA] Sensor de altura não respondeu durante a passagem de caixa alta. Transição proibida!",
                timestamp_iso=now_iso,
                timestamp_unix=now,
                current_marking=current_active,
                suggested_action="Substituir ou limpar o sensor óptico de topo no Factory I/O."
            )
        elif anomaly_type == "STUCK_ON_PRESENCE":
            anomaly = AnomalyReport(
                anomaly_id=f"SYNTH_STUCK_ON_{int(now)}",
                anomaly_type="SENSOR_STUCK_ON",
                severity="CRITICAL",
                component="palletSensor (Sensor de Entrada)",
                message="[FALHA INJETADA] Sensor de presença travado em nível lógico alto permanente. Risco de colisão!",
                timestamp_iso=now_iso,
                timestamp_unix=now,
                current_marking=current_active,
                suggested_action="Desobstruir a entrada da esteira no Factory I/O."
            )
        elif anomaly_type == "ILLEGAL_TRANSITION":
            anomaly = AnomalyReport(
                anomaly_id=f"SYNTH_ILLEGAL_TRANS_{int(now)}",
                anomaly_type="ILLEGAL_TRANSITION",
                severity="CRITICAL",
                component="transferLeft / transferRight (Mesa de Desvio)",
                message="[FALHA INJETADA] Ativação indevida de motor sem token ativo no lugar correspondente da Rede de Petri.",
                timestamp_iso=now_iso,
                timestamp_unix=now,
                current_marking=current_active,
                suggested_action="Verificar integridade do programa Ladder e sensores de posição."
            )
        else:
            anomaly = AnomalyReport(
                anomaly_id=f"SYNTH_GENERIC_{int(now)}",
                anomaly_type="GENERIC_FAULT",
                severity="WARNING",
                component="Planta Sorting by Height",
                message=f"[FALHA INJETADA] Anomalia simulada: {anomaly_type}",
                timestamp_iso=now_iso,
                timestamp_unix=now,
                current_marking=current_active,
                suggested_action="Inspecionar linha de produção."
            )

        return self._register_anomaly(anomaly)

    def _register_anomaly(self, anomaly: AnomalyReport) -> AnomalyReport:
        """Registra a anomalia se ela já não estiver ativa (evita duplicatas sucessivas)."""
        if not any(a.anomaly_type == anomaly.anomaly_type and a.component == anomaly.component and a.is_active for a in self.active_anomalies):
            self.active_anomalies.append(anomaly)
            self.anomaly_history.append(anomaly)
        return anomaly

    def clear_anomalies(self):
        """Desativa as anomalias ativas após intervenção do operador."""
        for a in self.active_anomalies:
            a.is_active = False
        self.active_anomalies.clear()
        self._sensor_high_start_time.clear()
        self._box_in_transit_start_time = None
        self._transfer_left_start_time = None
        self._transfer_right_start_time = None
        self._exit_left_start_time = None
        self._exit_right_start_time = None

    def reset(self, reset_counters: bool = False):
        """
        Restaura a Rede de Petri para sua marcação inicial segura (p1=1, p16=1, demais=0),
        eliminando fichas residuais ou vazamentos em paradas/resets.
        """
        self.clear_anomalies()
        self.petri_net = create_initial_petri_net()
        self._prev_tags.clear()
        for s in self.MONITORED_SENSORS:
            self.tags[s] = False
            self._prev_tags[s] = False
        self.tags["loaded"] = False
        self._prev_tags["loaded"] = False
        self.tags["highSensor"] = False
        self._prev_tags["highSensor"] = False
        self.tags["palletSensor"] = False
        self._prev_tags["palletSensor"] = False
        self.tags["start"] = False
        self._prev_tags["start"] = False
        self.tags["reset"] = False
        self._prev_tags["reset"] = False
        if reset_counters:
            self.caixas_esquerda = 0
            self.caixas_direita = 0
            self.tags["contador"] = 0
            self._last_plc_counter = 0

    def get_status_summary(self) -> Dict[str, Any]:
        """
        Retorna o estado completo e atualizado da Rede de Petri e da saúde do ativo.
        Executa uma checagem contínua de anomalias a cada chamada.
        """
        # Garante avaliação de timeouts e estados travados em tempo real
        self.check_anomalies()

        # Lugares ativos (onde o número de fichas é maior que zero)
        active_places = [p for p, v in self.petri_net.estados.items() if v > 0]
        places_state = {p: (self.petri_net.estados.get(p, 0) > 0) for p in [f"p{i}" for i in range(1, 17)]}

        has_critical_fault = any(a.severity == "CRITICAL" and a.is_active for a in self.active_anomalies)
        
        plc_count = int(self.tags.get("contador", 0))
        twin_total = self.caixas_esquerda + self.caixas_direita
        # O total geral reflete as caixas contadas pela esteira ou o contador oficial do CLP
        total_classificadas = max(twin_total, plc_count)

        return {
            "health_status": "CRITICAL_FAULT" if has_critical_fault else "HEALTHY",
            "active_places": active_places,
            "active_transitions": [],
            "places_state": places_state,
            "petri_estados": dict(self.petri_net.estados),
            "tags_state": dict(self.tags),
            "caixas_esquerda": self.caixas_esquerda,
            "caixas_direita": self.caixas_direita,
            "caixas_total": total_classificadas,
            "historico_esquerda": self.total_historico_esquerda,
            "historico_direita": self.total_historico_direita,
            "active_anomalies": [a.to_dict() for a in self.active_anomalies if a.is_active],
            "anomaly_history": [a.to_dict() for a in self.anomaly_history],
            "total_anomalies_recorded": len(self.anomaly_history)
        }
