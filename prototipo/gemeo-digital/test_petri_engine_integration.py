"""
Suite de Testes Automatizados da Integração do PetriNetEngine
Valida o comportamento formal e a detecção de todas as falhas físicas de sensores do Factory I/O.
"""

import sys
import time
from pathlib import Path

# Configura o path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))

from petri_engine import PetriNetEngine, AnomalyReport
from data_sanitizer import SanitizedEvent


def make_event(tag: str, val: bool) -> SanitizedEvent:
    now = time.time()
    return SanitizedEvent(
        tag_name=tag,
        value=val,
        raw_value=val,
        quality="GOOD",
        timestamp_iso="2026-09-07T00:00:00Z",
        timestamp_unix=now,
        source="TEST_UNIT",
        is_valid=True
    )


def test_normal_cycle():
    print("=== TESTE 1: Ciclo Normal (Caixa Baixa) ===")
    engine = PetriNetEngine()
    summary = engine.get_status_summary()
    assert summary["health_status"] == "HEALTHY"
    assert "p1" in summary["active_places"]
    assert "p16" in summary["active_places"]

    # START
    engine.update_from_sanitized_event(make_event("start", True))
    engine.update_from_sanitized_event(make_event("start", False))
    summary = engine.get_status_summary()
    assert "p2" in summary["active_places"]
    assert "p11" in summary["active_places"]
    assert "p1" not in summary["active_places"]

    # Caixa entra no palletSensor
    engine.update_from_sanitized_event(make_event("palletSensor", True))
    summary = engine.get_status_summary()
    # Transição t3 lambda dispara imediatamente, reservando a mesa (p16=0) e liberando p2 e p4
    assert "p4" in summary["active_places"]
    assert "p2" in summary["active_places"]
    assert "p16" not in summary["active_places"]

    engine.update_from_sanitized_event(make_event("palletSensor", False))

    # Caixa chega em loaded (mesa)
    engine.update_from_sanitized_event(make_event("loaded", True))
    summary = engine.get_status_summary()
    assert "p6" in summary["active_places"]  # Caixa baixa (alto=0)
    assert "p4" not in summary["active_places"]

    engine.update_from_sanitized_event(make_event("loaded", False))

    # Desvio esquerdo (atLeftEntry)
    engine.update_from_sanitized_event(make_event("atLeftEntry", True))
    summary = engine.get_status_summary()
    assert "p7" in summary["active_places"]
    assert "p16" in summary["active_places"]  # Mesa liberada!

    engine.update_from_sanitized_event(make_event("atLeftEntry", False))

    # Fim da linha (atLeftExit)
    engine.update_from_sanitized_event(make_event("atLeftExit", True))
    summary = engine.get_status_summary()
    assert "p7" not in summary["active_places"]
    assert "p10" not in summary["active_places"]  # Consumido por t11 lambda
    assert summary["health_status"] == "HEALTHY"
    assert summary["caixas_esquerda"] == 1
    assert summary["caixas_direita"] == 0
    assert summary["caixas_total"] == 1
    print("✅ TESTE 1 PASSOU COM SUCESSO! (Contador: 1 caixa à esquerda, 0 à direita)\n")


def test_pallet_sensor_stuck_off():
    print("=== TESTE 2: Falha palletSensor Stuck OFF (Pulo de sensor) ===")
    engine = PetriNetEngine()
    engine.update_from_sanitized_event(make_event("start", True))
    engine.update_from_sanitized_event(make_event("start", False))

    # A caixa não é vista no palletSensor, mas chega direto em loaded!
    anomaly = engine.update_from_sanitized_event(make_event("loaded", True))

    summary = engine.get_status_summary()
    assert summary["health_status"] == "CRITICAL_FAULT"
    assert len(summary["active_anomalies"]) > 0
    anom = summary["active_anomalies"][0]
    assert anom["anomaly_type"] == "SENSOR_STUCK_OFF"
    assert "palletSensor" in anom["component"]
    print(f"✅ Anomalia capturada corretamente: {anom['message']}")
    print("✅ TESTE 2 PASSOU COM SUCESSO!\n")


def test_optical_inconsistency():
    print("=== TESTE 3: Inconsistência Óptica (highSensor ON sem palletSensor) ===")
    engine = PetriNetEngine()
    engine.update_from_sanitized_event(make_event("start", True))

    # highSensor aciona sozinho
    anomaly = engine.update_from_sanitized_event(make_event("highSensor", True))
    summary = engine.get_status_summary()
    assert summary["health_status"] == "CRITICAL_FAULT"
    assert "highSensor" in summary["active_anomalies"][0]["component"]
    print(f"✅ Inconsistência capturada: {summary['active_anomalies'][0]['message']}")
    print("✅ TESTE 3 PASSOU COM SUCESSO!\n")


def test_sensor_stuck_on():
    print("=== TESTE 4: Sensor palletSensor Stuck ON por mais de 8 segundos ===")
    engine = PetriNetEngine()
    engine.update_from_sanitized_event(make_event("start", True))
    engine.update_from_sanitized_event(make_event("palletSensor", True))

    # Força passagem de tempo no timer
    engine._sensor_high_start_time["palletSensor"] = time.time() - 10.0

    anomaly = engine.check_anomalies()
    assert anomaly is not None
    assert anomaly.anomaly_type == "SENSOR_STUCK_ON"
    assert "palletSensor" in anomaly.component
    print(f"✅ Falha Stuck ON capturada: {anomaly.message}")
    print("✅ TESTE 4 PASSOU COM SUCESSO!\n")


def test_transit_timeout():
    print("=== TESTE 5: Timeout de Transporte na Esteira de Entrada (loaded não aciona) ===")
    engine = PetriNetEngine()
    engine.update_from_sanitized_event(make_event("start", True))
    engine.update_from_sanitized_event(make_event("conveyorEntry", True))
    engine.update_from_sanitized_event(make_event("palletSensor", True))
    engine.update_from_sanitized_event(make_event("palletSensor", False))

    # Força passagem de tempo em trânsito sem atingir loaded (> 15s)
    engine._box_in_transit_start_time = time.time() - 20.0

    anomaly = engine.check_anomalies()
    assert anomaly is not None
    assert anomaly.anomaly_type == "TRANSPORT_TIMEOUT"
    assert "loaded" in anomaly.component
    print(f"✅ Timeout de Transporte capturado: {anomaly.message}")
    print("✅ TESTE 5 PASSOU COM SUCESSO!\n")


def test_reset_cleans_phantom_tokens():
    print("=== TESTE 6: Higienização de Marcação no Reset ===")
    engine = PetriNetEngine()
    engine.update_from_sanitized_event(make_event("start", True))
    engine.update_from_sanitized_event(make_event("palletSensor", True))

    # Linha em p4, p16=0
    assert engine.petri_net.estados.get("p4") == 1
    assert engine.petri_net.estados.get("p16") == 0

    # Comando de Reset
    engine.reset()
    summary = engine.get_status_summary()
    assert summary["health_status"] == "HEALTHY"
    assert engine.petri_net.estados.get("p1") == 1
    assert engine.petri_net.estados.get("p16") == 1
    assert engine.petri_net.estados.get("p4", 0) == 0
    assert engine.petri_net.estados.get("p2", 0) == 0
    print("✅ Reset higienizou perfeitamente a marcação inicial (p1=1, p16=1)!")
    print("✅ TESTE 6 PASSOU COM SUCESSO!\n")


def test_auto_recovery():
    print("=== TESTE 7: Auto-Recuperação quando o Sensor Volta a Funcionar ===")
    engine = PetriNetEngine()
    engine.update_from_sanitized_event(make_event("start", True))
    engine.update_from_sanitized_event(make_event("palletSensor", True))

    # 1. Simula sensor Stuck ON
    engine._sensor_high_start_time["palletSensor"] = time.time() - 10.0
    engine.check_anomalies()
    assert engine.get_status_summary()["health_status"] == "CRITICAL_FAULT"

    # 2. Usuário desfaz a falha no Factory I/O (sensor vai para 0)
    engine.update_from_sanitized_event(make_event("palletSensor", False))
    summary = engine.get_status_summary()
    assert summary["health_status"] == "HEALTHY"
    assert len(summary["active_anomalies"]) == 0
    assert len(summary["anomaly_history"]) > 0  # Permanece no histórico para auditoria!
    print("✅ Alerta de Stuck ON removido automaticamente quando o sensor voltou para 0!")

    # 3. Simula botão RESET físico no Factory I/O (reset_P)
    engine.update_from_sanitized_event(make_event("reset", True))
    summary = engine.get_status_summary()
    assert summary["health_status"] == "HEALTHY"
    assert engine.petri_net.estados.get("p1") == 1
    assert engine.petri_net.estados.get("p16") == 1
    print("✅ Botão físico RESET do Factory I/O limpa os alarmes e restaura o estado inicial!")
    print("✅ TESTE 7 PASSOU COM SUCESSO!\n")


if __name__ == "__main__":
    test_normal_cycle()
    test_pallet_sensor_stuck_off()
    test_optical_inconsistency()
    test_sensor_stuck_on()
    test_transit_timeout()
    test_reset_cleans_phantom_tokens()
    test_auto_recovery()
    print("🎉 TODOS OS 7 TESTES DE INTEGRAÇÃO PASSARAM COM SUCESSO!")
