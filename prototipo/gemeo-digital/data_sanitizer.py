"""
Módulo de Sanitização e Governança de Dados
Aplica filtragem de repique (debouncing), validação de qualidade, tipagem estrita
e enriquecimento com metadados de linhagem conforme normas ISO/IEC 30173 e ISO 23247.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import time
from typing import Any, Optional, Dict, List
from config import DEBOUNCE_TIME_MS


@dataclass
class SanitizedEvent:
    """Representa um evento industrial higienizado e enriquecido com metadados de governança."""
    tag_name: str
    value: Any
    raw_value: Any
    quality: str
    timestamp_iso: str
    timestamp_unix: float
    source: str
    is_valid: bool
    filtered_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DataSanitizer:
    """
    Sanitizador de Dados Industriais:
    - Elimina ruídos de repique mecânico (Debouncing).
    - Valida integridade e tipo das variáveis.
    - Audita a linhagem e qualidade de cada leitura.
    """

    def __init__(self, debounce_ms: int = DEBOUNCE_TIME_MS, max_history: int = 100):
        self.debounce_sec = debounce_ms / 1000.0
        self.max_history = max_history
        self._last_event_time: Dict[str, float] = {}
        self._last_event_value: Dict[str, Any] = {}
        self.audit_log: List[SanitizedEvent] = []
        self.total_received = 0
        self.total_sanitized = 0
        self.total_filtered_noise = 0

    def sanitize(self, tag_name: str, raw_value: Any, source_uri: str = "CODESYS_OPCUA") -> Optional[SanitizedEvent]:
        """
        Higieniza um valor bruto recebido via OPC UA.
        Retorna o evento estruturado ou None se for ruído descartado.
        """
        now_unix = time.time()
        now_iso = datetime.now(timezone.utc).isoformat()
        self.total_received += 1

        # 1. Checagem de Qualidade e Valores Nulos
        if raw_value is None:
            event = SanitizedEvent(
                tag_name=tag_name,
                value=None,
                raw_value=raw_value,
                quality="BAD_NULL_VALUE",
                timestamp_iso=now_iso,
                timestamp_unix=now_unix,
                source=source_uri,
                is_valid=False,
                filtered_reason="Valor nulo recebido do servidor"
            )
            self._record(event)
            return None

        # 2. Tipagem Estrita
        clean_value = raw_value
        if isinstance(raw_value, bool):
            clean_value = bool(raw_value)
        elif isinstance(raw_value, (int, float)):
            clean_value = int(raw_value) if float(raw_value).is_integer() else float(raw_value)

        # 3. Filtragem de Repique (Debouncing)
        last_time = self._last_event_time.get(tag_name, 0.0)
        last_val = self._last_event_value.get(tag_name, None)
        elapsed = now_unix - last_time

        # Se o valor mudou rapidamente em menos tempo que o limite de debouncing:
        if last_val is not None and clean_value != last_val and elapsed < self.debounce_sec:
            self.total_filtered_noise += 1
            # Registra no log de auditoria como ruído descartado
            event = SanitizedEvent(
                tag_name=tag_name,
                value=clean_value,
                raw_value=raw_value,
                quality="UNCERTAIN_NOISE_REBOUND",
                timestamp_iso=now_iso,
                timestamp_unix=now_unix,
                source=source_uri,
                is_valid=False,
                filtered_reason=f"Repique descartado (variação em {elapsed*1000:.1f}ms < {self.debounce_sec*1000}ms)"
            )
            self._record(event)
            return None

        # Atualiza o estado estável
        self._last_event_time[tag_name] = now_unix
        self._last_event_value[tag_name] = clean_value
        self.total_sanitized += 1

        # 4. Criação do Pacote Sanitizado com Metadados de Governança
        event = SanitizedEvent(
            tag_name=tag_name,
            value=clean_value,
            raw_value=raw_value,
            quality="GOOD",
            timestamp_iso=now_iso,
            timestamp_unix=now_unix,
            source=source_uri,
            is_valid=True,
            metadata={
                "data_type": type(clean_value).__name__,
                "standard": "ISO/IEC 30173",
                "debounced": True
            }
        )
        self._record(event)
        return event

    def _record(self, event: SanitizedEvent):
        """Registra o evento no histórico de auditoria rotativo."""
        self.audit_log.append(event)
        if len(self.audit_log) > self.max_history:
            self.audit_log.pop(0)

    def get_audit_summary(self) -> Dict[str, Any]:
        """Retorna estatísticas de qualidade de dados para o Dashboard."""
        return {
            "total_received": self.total_received,
            "total_sanitized": self.total_sanitized,
            "total_filtered_noise": self.total_filtered_noise,
            "data_quality_percentage": (
                round((self.total_sanitized / max(1, self.total_received)) * 100, 2)
            ),
            "recent_events": [e.to_dict() for e in reversed(self.audit_log[-15:])]
        }
