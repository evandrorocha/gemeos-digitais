"""
Módulo de Configuração do Gêmeo Digital
Centraliza parâmetros de conexão OPC UA, temporizações e limites de detecção de anomalias.
"""

import os

# Configuração de Conexão OPC UA
# No Docker, conecta ao host via 'opc.tcp://host.docker.internal:4840'
OPCUA_SERVER_URL = os.getenv("OPCUA_SERVER_URL", "opc.tcp://127.0.0.1:4840")

# Prefixo do nó no CODESYS Control Win V3 x64
PLC_PRG_NODE_ID = os.getenv(
    "PLC_PRG_NODE_ID",
    "ns=4;s=|var|CODESYS Control Win V3 x64.Application.PLC_PRG"
)

# Parâmetros de Sanitização de Dados
DEBOUNCE_TIME_MS = int(os.getenv("DEBOUNCE_TIME_MS", "50"))  # 50ms para eliminar repiques de sensores
SAMPLING_RATE_MS = int(os.getenv("SAMPLING_RATE_MS", "100")) # Taxa de subscrição OPC UA

# Parâmetros de Temporização da Linha (Detecção de Timeout / Engavetamento)
TIMEOUT_CONVEYOR_ENTRY_SEC = float(os.getenv("TIMEOUT_CONVEYOR_ENTRY_SEC", "4.0"))
TIMEOUT_TRANSFER_SEC = float(os.getenv("TIMEOUT_TRANSFER_SEC", "3.0"))
MAX_PRESENCE_TIME_SEC = float(os.getenv("MAX_PRESENCE_TIME_SEC", "2.5"))

# Tags Críticas Monitoradas na Linha
CRITICAL_TAGS = [
    "start", "stop", "reset", "desligar",
    "palletSensor", "highSensor", "loaded", "alto",
    "conveyorEntry", "conveyorLeft", "conveyorRight",
    "transferLeft", "transferRight", "load",
    "atLeftEntry", "atLeftExit", "atRightEntry", "atRightExit",
    "contador", "aux0"
]

# Lugares da Rede de Petri (p1 a p16)
PETRI_PLACES = [f"p{i}" for i in range(1, 17)]

# Transições da Rede de Petri (t1 a t17)
PETRI_TRANSITIONS = [f"t{i}" for i in range(1, 18)]
