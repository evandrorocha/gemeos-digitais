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
    print("=== TESTE 3: Regras Puras da Rede de Petri (highSensor isolado não gera anomalia) ===")
    engine = PetriNetEngine()
    engine.update_from_sanitized_event(make_event("start", True))

    # highSensor aciona sozinho: não deve disparar anomalia nas regras formais da Rede de Petri
    anomaly = engine.update_from_sanitized_event(make_event("highSensor", True))
    summary = engine.get_status_summary()
    assert summary["health_status"] == "HEALTHY"
    assert len(summary["active_anomalies"]) == 0
    print("✅ highSensor isolado ignorado pela Rede de Petri (regras puras ativas)")
    print("✅ TESTE 3 PASSOU COM SUCESSO!\n")


def test_sensor_stuck_on():
    print("=== TESTE 4: Sensor palletSensor Stuck ON por mais de 8 segundos ===")
    engine = PetriNetEngine()
    engine.update_from_sanitized_event(make_event("start", True))
    engine.update_from_sanitized_event(make_event("palletSensor", True))

    # Força passagem de tempo no timer
    engine._sensor_high_start_time["palletSensor"] = time.time() - 10.0

    # Verificação de timeout/stuck desativada a pedido do usuário
    anomaly = engine.check_anomalies()
    assert anomaly is None  # Timeouts desativados por hora
    print("✅ TESTE 4 PASSOU: Timeouts de tempo desativados conforme solicitado!\n")


def test_transit_timeout():
    print("=== TESTE 5: Timeout de Transporte na Esteira de Entrada (Desativado) ===")
    engine = PetriNetEngine()
    engine.update_from_sanitized_event(make_event("start", True))
    engine.update_from_sanitized_event(make_event("conveyorEntry", True))
    engine.update_from_sanitized_event(make_event("palletSensor", True))
    engine.update_from_sanitized_event(make_event("palletSensor", False))

    # Força passagem de tempo em trânsito sem atingir loaded
    engine._box_in_transit_start_time = time.time() - 20.0

    anomaly = engine.check_anomalies()
    assert anomaly is None  # Timeouts desativados por hora
    print("✅ TESTE 5 PASSOU: Timeouts de transporte desativados conforme solicitado!\n")


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

    # 1. Simula violação de transição da Rede de Petri (loaded sem palletSensor)
    engine.update_from_sanitized_event(make_event("loaded", True))
    assert engine.get_status_summary()["health_status"] == "CRITICAL_FAULT"

    # 3. Simula botão RESET físico no Factory I/O (reset_P)
    engine.update_from_sanitized_event(make_event("reset", True))
    summary = engine.get_status_summary()
    assert summary["health_status"] == "HEALTHY"
    assert engine.petri_net.estados.get("p1") == 1
    assert engine.petri_net.estados.get("p16") == 1
    print("✅ Botão físico RESET do Factory I/O limpa os alarmes e restaura o estado inicial!")
    print("✅ TESTE 7 PASSOU COM SUCESSO!\n")


def test_pallet_arrival_in_resting_state():
    print("=== TESTE 8: Chegada de Caixa em Repouso (p1) sem Falso Alarme ===")
    engine = PetriNetEngine()
    summary = engine.get_status_summary()
    assert summary["health_status"] == "HEALTHY"
    assert "p1" in summary["active_places"]

    # Caixa chega no palletSensor enquanto a planta ainda está parada em repouso (p1)
    engine.update_from_sanitized_event(make_event("palletSensor", True))
    summary = engine.get_status_summary()
    assert summary["health_status"] == "HEALTHY", "Caixa na entrada em repouso NÃO pode ser considerada anomalia!"
    assert len(summary["active_anomalies"]) == 0
    print("✅ Caixa posicionada no palletSensor em p1 não gerou falso alarme!")

    # Operador agora pressiona START (start_P)
    engine.update_from_sanitized_event(make_event("start", True))
    engine.update_from_sanitized_event(make_event("start", False))
    summary = engine.get_status_summary()
    assert summary["health_status"] == "HEALTHY"
    # A caixa que já estava no palletSensor é consumida imediatamente e avança para p4!
    assert "p4" in summary["active_places"]
    assert "p16" not in summary["active_places"]  # Mesa reservada
    print("✅ START consumiu a peça pré-existente e avançou perfeitamente para p4!")
    print("✅ TESTE 8 PASSOU COM SUCESSO!\n")


def test_exit_sensor_clearing_in_resting_state():
    print("=== TESTE 9: Caixa Residual Saindo em Repouso (atLeftExit em p1) sem Falso Alarme ===")
    engine = PetriNetEngine()
    summary = engine.get_status_summary()
    assert summary["health_status"] == "HEALTHY"
    assert "p1" in summary["active_places"]

    # Uma caixa que estava na esteira esquerda termina de sair (feixe cortado e depois desobstruído)
    engine.update_from_sanitized_event(make_event("atLeftExit", False))
    engine.update_from_sanitized_event(make_event("atLeftExit", True))

    summary = engine.get_status_summary()
    assert summary["health_status"] == "HEALTHY", "Caixa saindo da linha em repouso NÃO pode gerar alarme!"
    assert len(summary["active_anomalies"]) == 0
    assert summary["caixas_esquerda"] == 1
    assert summary["caixas_total"] == 1
    print("✅ Caixa residual na saída em p1 foi contabilizada sem gerar falso alarme!")
    print("✅ TESTE 9 PASSOU COM SUCESSO!\n")


def test_nc_sensors_normal_running_no_false_stuck_on():
    print("=== TESTE 10: Sensores Retrorreflexivos (NF) em Operação Normal não Disparam Falso Stuck ON ===")
    engine = PetriNetEngine()
    engine.update_from_sanitized_event(make_event("start", True))
    engine.update_from_sanitized_event(make_event("conveyorLeft", True))
    engine.update_from_sanitized_event(make_event("conveyorRight", True))

    # Sensores atLeftExit e atRightExit em estado livre/normal (True)
    engine.update_from_sanitized_event(make_event("atLeftExit", True))
    engine.update_from_sanitized_event(make_event("atRightExit", True))

    # Passam 15 segundos de esteira rodando vazia
    time.sleep(0.01)
    anomaly = engine.check_anomalies()
    assert anomaly is None
    summary = engine.get_status_summary()
    assert summary["health_status"] == "HEALTHY"
    assert len(summary["active_anomalies"]) == 0
    print("✅ Sensores NF desobstruídos em esteira rodando operam perfeitamente sem falso alarme!")
    print("✅ TESTE 10 PASSOU COM SUCESSO!\n")


def test_capacity_limit_exceeded():
    print("=== TESTE 11: Limite de Capacidade de Fichas (Esteira Lotada) ===")
    engine = PetriNetEngine()

    # Simula 5 caixas na esteira esquerda (p7 = 5) -> Dentro do limite
    engine.petri_net.estados["p7"] = 5
    anomaly = engine.check_anomalies()
    assert anomaly is None
    summary = engine.get_status_summary()
    assert summary["health_status"] == "HEALTHY"
    assert len(summary["active_anomalies"]) == 0

    # 6ª caixa entra na esteira esquerda (p7 = 6) -> Excede limite de 5
    engine.petri_net.estados["p7"] = 6
    anomaly = engine.check_anomalies()
    assert anomaly is not None
    assert anomaly.anomaly_type == "CAPACITY_LIMIT_EXCEEDED"
    assert anomaly.severity == "CRITICAL"
    assert "p7" in anomaly.message

    summary = engine.get_status_summary()
    assert summary["health_status"] == "CRITICAL_FAULT"
    assert len(summary["active_anomalies"]) == 1
    print(f"✅ Anomalia de capacidade capturada com sucesso: {anomaly.message}")

    # Caixa sai da esteira (p7 = 5) -> Volta para o limite seguro
    engine.petri_net.estados["p7"] = 5
    anomaly = engine.check_anomalies()
    assert anomaly is None
    summary = engine.get_status_summary()
    assert summary["health_status"] == "HEALTHY"
    assert len(summary["active_anomalies"]) == 0
    print("✅ Auto-recuperação de capacidade validada com sucesso!")
    print("✅ TESTE 11 PASSOU COM SUCESSO!\n")


if __name__ == "__main__":
    test_normal_cycle()
    test_pallet_sensor_stuck_off()
    test_optical_inconsistency()
    test_sensor_stuck_on()
    test_transit_timeout()
    test_reset_cleans_phantom_tokens()
    test_auto_recovery()
    test_pallet_arrival_in_resting_state()
    test_exit_sensor_clearing_in_resting_state()
    test_nc_sensors_normal_running_no_false_stuck_on()
    test_capacity_limit_exceeded()
    print("🎉 TODOS OS 11 TESTES DE INTEGRAÇÃO PASSARAM COM SUCESSO!")
