"""
Motor de Diagnóstico baseado em Rede de Petri
Executa o modelo formal da esteira de separação de caixas (Sorting by Height),
rastreia a marcação dos lugares (p1..p16) e detecta anomalias em tempo real
(Stuck ON, Stuck OFF, Violação de Sequência e Timeouts de Transporte).
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import time
from typing import Dict, List, Optional, Set, Any
from config import (
    TIMEOUT_CONVEYOR_ENTRY_SEC,
    TIMEOUT_TRANSFER_SEC,
    MAX_PRESENCE_TIME_SEC
)
from data_sanitizer import SanitizedEvent


@dataclass
class AnomalyReport:
    """Relatório estruturado de anomalia detectada pelo Gêmeo Digital."""
    anomaly_id: str
    anomaly_type: str
    severity: str  # "CRITICAL", "WARNING", "INFO"
    component: str
    message: str
    timestamp_iso: str
    timestamp_unix: float
    current_marking: List[str]
    suggested_action: str
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PetriNetEngine:
    """
    Motor da Rede de Petri do Gêmeo Digital:
    - Mantém a marcação dos lugares ativos (p1 a p16).
    - Avalia transições disparadas por eventos sanitizados.
    - Executa regras de diagnóstico e detecção de anomalias.
    """

    def __init__(self):
        # Lugares ativos (Marcação inicial: p1 = True)
        self.places: Dict[str, bool] = {f"p{i}": False for i in range(1, 17)}
        self.places["p1"] = True  # Estado inicial: Repouso
        self.places["p14"] = True # Condição de inicialização do Ladder
        self.places["p16"] = True

        # Transições ativas
        self.transitions: Dict[str, bool] = {f"t{i}": False for i in range(1, 18)}

        # Variáveis de processo espelhadas no Gêmeo Digital
        self.tags: Dict[str, Any] = {
            "start": False, "stop": False, "reset": False, "desligar": False,
            "palletSensor": False, "highSensor": False, "loaded": False, "alto": False,
            "conveyorEntry": False, "conveyorLeft": False, "conveyorRight": False,
            "transferLeft": False, "transferRight": False, "load": False,
            "atLeftEntry": False, "atLeftExit": False, "atRightEntry": False, "atRightExit": False,
            "contador": 0
        }

        # Timers para detecção de anomalias
        self._conveyor_entry_start_time: Optional[float] = None
        self._pallet_sensor_start_time: Optional[float] = None
        self._box_in_transit_start_time: Optional[float] = None
        self._transfer_start_time: Optional[float] = None
        self._high_sensor_triggered_for_current_pallet = False

        # Histórico de anomalias
        self.active_anomalies: List[AnomalyReport] = []
        self.anomaly_history: List[AnomalyReport] = []

    def update_from_sanitized_event(self, event: SanitizedEvent) -> Optional[AnomalyReport]:
        """
        Processa um evento sanitizado do OPC UA, atualiza a Rede de Petri
        e executa a checagem de regras de anomalia.
        """
        tag = event.tag_name
        val = event.value

        # Atualiza a tag espelhada
        self.tags[tag] = val

        # Se a tag for um lugar (p1..p16) ou transição (t1..t17) reportado pelo CLP:
        if tag in self.places:
            self.places[tag] = bool(val)
        elif tag in self.transitions:
            self.transitions[tag] = bool(val)

        # Atualiza temporizadores internos
        now = time.time()
        if tag == "conveyorEntry":
            if val:
                self._conveyor_entry_start_time = now
            else:
                self._conveyor_entry_start_time = None
                self._box_in_transit_start_time = None

        if tag == "palletSensor":
            if val:
                self._pallet_sensor_start_time = now
                self._box_in_transit_start_time = now  # Inicia rastreio da caixa em trânsito
                self._high_sensor_triggered_for_current_pallet = False
            else:
                self._pallet_sensor_start_time = None

        if tag == "highSensor" and val:
            self._high_sensor_triggered_for_current_pallet = True

        if tag == "loaded" and val:
            # Caixa chegou com sucesso na mesa transfer!
            self._box_in_transit_start_time = None

        if tag in ["transferLeft", "transferRight"]:
            if val:
                self._transfer_start_time = now
            else:
                self._transfer_start_time = None

        # Executa a verificação de anomalias
        return self.check_anomalies()

    def check_anomalies(self) -> Optional[AnomalyReport]:
        """
        Aplica as regras formais de detecção de anomalias.
        Retorna o relatório da anomalia se alguma for disparada.
        """
        now = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        current_active_places = [p for p, active in self.places.items() if active]

        # ---------------------------------------------------------------------
        # REGRA 1: Detecção de Sensor de Presença Travado (Stuck ON)
        # Se o sensor de entrada ficar aceso por mais tempo do que a passagem da caixa
        # ---------------------------------------------------------------------
        if self.tags.get("palletSensor") and self._pallet_sensor_start_time:
            elapsed = now - self._pallet_sensor_start_time
            if elapsed > MAX_PRESENCE_TIME_SEC and self.tags.get("conveyorEntry"):
                anomaly = AnomalyReport(
                    anomaly_id=f"ANOM_STUCK_ON_{int(now)}",
                    anomaly_type="SENSOR_STUCK_ON",
                    severity="CRITICAL",
                    component="palletSensor (Sensor de Entrada)",
                    message=f"Sensor de presença travado em ON por {elapsed:.1f}s com esteira em movimento. Risco de engavetamento!",
                    timestamp_iso=now_iso,
                    timestamp_unix=now,
                    current_marking=current_active_places,
                    suggested_action="Inspecionar lente óptica do sensor de entrada e desobstruir linha."
                )
                return self._register_anomaly(anomaly)

        # ---------------------------------------------------------------------
        # REGRA 2: Detecção de Timeout de Transporte (Caixa Engavetada / Motor Travado)
        # Só monitora se uma caixa de fato entrou na linha (passou pelo palletSensor)
        # ---------------------------------------------------------------------
        if self._box_in_transit_start_time and self.tags.get("conveyorEntry"):
            elapsed = now - self._box_in_transit_start_time
            # Se a caixa entrou há mais tempo que o limite e ainda não atingiu a mesa:
            if elapsed > TIMEOUT_CONVEYOR_ENTRY_SEC and not self.tags.get("loaded"):
                anomaly = AnomalyReport(
                    anomaly_id=f"ANOM_TIMEOUT_ENTRY_{int(now)}",
                    anomaly_type="TRANSPORT_TIMEOUT",
                    severity="CRITICAL",
                    component="conveyorEntry (Esteira de Entrada)",
                    message=f"Tempo limite de transporte da caixa excedido ({elapsed:.1f}s > {TIMEOUT_CONVEYOR_ENTRY_SEC}s). Caixa travou na esteira!",
                    timestamp_iso=now_iso,
                    timestamp_unix=now,
                    current_marking=current_active_places,
                    suggested_action="Verificar se o pallet travou nos roletes ou se a esteira está patinando."
                )
                return self._register_anomaly(anomaly)

        return None

    def inject_synthetic_anomaly(self, anomaly_type: str) -> AnomalyReport:
        """Permite injetar anomalias programadas para testes e demonstrações."""
        now = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        current_active_places = [p for p, active in self.places.items() if active]

        if anomaly_type == "STUCK_OFF_HIGH_SENSOR":
            anomaly = AnomalyReport(
                anomaly_id=f"SYNTH_STUCK_OFF_{int(now)}",
                anomaly_type="SENSOR_STUCK_OFF",
                severity="CRITICAL",
                component="highSensor (Sensor de Altura)",
                message="[FALHA INJETADA] Sensor de altura não respondeu durante a passagem de caixa alta. Transição proibida!",
                timestamp_iso=now_iso,
                timestamp_unix=now,
                current_marking=current_active_places,
                suggested_action="Substituir ou limpar o sensor óptico de topo."
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
                current_marking=current_active_places,
                suggested_action="Desobstruir a entrada da esteira."
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
                current_marking=current_active_places,
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
                current_marking=current_active_places,
                suggested_action="Inspecionar linha de produção."
            )

        return self._register_anomaly(anomaly)

    def _register_anomaly(self, anomaly: AnomalyReport) -> AnomalyReport:
        """Registra a anomalia se ela já não estiver ativa."""
        # Evita duplicatas do mesmo tipo em sequência rápida
        if not any(a.anomaly_type == anomaly.anomaly_type and a.is_active for a in self.active_anomalies):
            self.active_anomalies.append(anomaly)
            self.anomaly_history.append(anomaly)
        return anomaly

    def clear_anomalies(self):
        """Limpa as anomalias ativas após intervenção do operador."""
        for a in self.active_anomalies:
            a.is_active = False
        self.active_anomalies.clear()
        self._conveyor_entry_start_time = None
        self._pallet_sensor_start_time = None
        self._box_in_transit_start_time = None
        self._transfer_start_time = None

    def get_status_summary(self) -> Dict[str, Any]:
        """Retorna o estado completo da Rede de Petri e da saúde do ativo."""
        active_places = [p for p, v in self.places.items() if v]
        active_transitions = [t for t, v in self.transitions.items() if v]
        has_critical_fault = any(a.severity == "CRITICAL" and a.is_active for a in self.active_anomalies)

        return {
            "health_status": "CRITICAL_FAULT" if has_critical_fault else "HEALTHY",
            "active_places": active_places,
            "active_transitions": active_transitions,
            "places_state": self.places,
            "tags_state": self.tags,
            "active_anomalies": [a.to_dict() for a in self.active_anomalies if a.is_active],
            "total_anomalies_recorded": len(self.anomaly_history)
        }
