"""
Conector OPC UA Bidirecional do Gêmeo Digital
Gerencia a subscrição assíncrona com o CODESYS, sanitização de dados,
alimentação do motor de Rede de Petri, atualização do AAS e envio de comandos de controle.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Any
from asyncua import Client, Node, ua
from config import OPCUA_SERVER_URL, PLC_PRG_NODE_ID, SAMPLING_RATE_MS
from data_sanitizer import DataSanitizer, SanitizedEvent
from petri_engine import PetriNetEngine, AnomalyReport
from aas_model import AssetAdministrationShell

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OPC_CONNECTOR")


class SubscriptionHandler:
    """Recebe as notificações de DataChange do servidor OPC UA."""

    def __init__(self, connector: "DigitalTwinConnector"):
        self.connector = connector

    def datachange_notification(self, node: Node, val: Any, data: Any):
        try:
            # Extrai o nome da tag do BrowseName ou NodeId
            node_str = str(node.nodeid.Identifier)
            tag_name = node_str.split(".")[-1]

            # Processa no conector do gêmeo digital
            self.connector.process_incoming_tag(tag_name, val)
        except Exception as e:
            logger.error(f"Erro ao processar datachange da tag: {e}")


class DigitalTwinConnector:
    """
    Controlador central do Gêmeo Digital:
    Conecta ao CLP, sanitiza dados, executa a Rede de Petri e atualiza o AAS.
    """

    def __init__(self, url: str = OPCUA_SERVER_URL):
        self.url = url
        self.client: Optional[Client] = None
        self.sanitizer = DataSanitizer()
        self.petri_engine = PetriNetEngine()
        self.aas = AssetAdministrationShell()
        self.is_connected = False
        self._subscription = None
        self._nodes_cache: Dict[str, Node] = {}
        self.on_state_change_callbacks: List[Callable[[Dict[str, Any]], None]] = []

    def register_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Registra um callback para notificar interfaces externas (ex: Dashboard)."""
        self.on_state_change_callbacks.append(callback)

    def process_incoming_tag(self, tag_name: str, raw_value: Any):
        """Pipeline de processamento: Bruto -> Sanitizado -> Petri -> AAS -> Ação."""
        # 1. Sanitização do Dado
        event = self.sanitizer.sanitize(tag_name, raw_value, source_uri=self.url)
        if event is None:
            return # Ruído descartado

        # 2. Atualização da Rede de Petri e Detecção de Falhas
        anomaly = self.petri_engine.update_from_sanitized_event(event)

        # 3. Atualização do Modelo AAS (BaSyx)
        petri_status = self.petri_engine.get_status_summary()
        self.aas.update_from_telemetry(self.petri_engine.tags, petri_status)

        # 4. Ação Autônoma do Gêmeo Digital: Se houver anomalia crítica, envia STOP de emergência
        if anomaly and anomaly.severity == "CRITICAL":
            logger.warning(f"🚨 ANOMALIA CRÍTICA DETECTADA: {anomaly.message}")
            asyncio.create_task(self.emergency_stop(reason=anomaly.message))

        # 5. Notifica ouvintes registrados
        current_state = self.get_full_state()
        for cb in self.on_state_change_callbacks:
            try:
                cb(current_state)
            except Exception as e:
                logger.error(f"Erro em callback de estado: {e}")

    async def connect_and_subscribe(self):
        """Estabelece a conexão OPC UA e inicia a subscrição assíncrona."""
        logger.info(f"Conectando ao servidor OPC UA em {self.url}...")
        self.client = Client(url=self.url)
        await self.client.connect()
        self.is_connected = True
        logger.info("✅ Conectado com sucesso ao CODESYS OPC UA!")

        # Obtém o nó do PLC_PRG e todas as variáveis
        plc_node = self.client.get_node(PLC_PRG_NODE_ID)
        children = await plc_node.get_children()

        tags_to_subscribe = []
        for child in children:
            nclass = await child.read_node_class()
            if nclass == ua.NodeClass.Variable:
                bname = await child.read_browse_name()
                self._nodes_cache[bname.Name] = child
                tags_to_subscribe.append(child)

        logger.info(f"Cache criado com {len(self._nodes_cache)} variáveis.")

        # Cria a subscrição
        handler = SubscriptionHandler(self)
        self._subscription = await self.client.create_subscription(SAMPLING_RATE_MS, handler)
        await self._subscription.subscribe_data_change(tags_to_subscribe)
        logger.info(f"Subscrição ativada para {len(tags_to_subscribe)} tags.")

    async def write_tag(self, tag_name: str, value: Any):
        """Escreve um valor em uma tag no CODESYS via OPC UA."""
        if not self.is_connected or not self.client:
            logger.error("Tentativa de escrita sem conexão ativa!")
            return False

        try:
            node = self._nodes_cache.get(tag_name)
            if not node:
                nid = f"{PLC_PRG_NODE_ID}.{tag_name}"
                node = self.client.get_node(nid)
                self._nodes_cache[tag_name] = node

            # Se for booleano
            if isinstance(value, bool):
                dv = ua.DataValue(ua.Variant(value, ua.VariantType.Boolean))
            elif isinstance(value, int):
                dv = ua.DataValue(ua.Variant(value, ua.VariantType.Int16))
            else:
                dv = ua.DataValue(ua.Variant(value))

            await node.write_value(dv)
            logger.info(f"Comando gravado com sucesso: {tag_name} = {value}")
            return True
        except Exception as e:
            logger.error(f"Erro ao escrever na tag {tag_name}: {e}")
            return False

    async def emergency_stop(self, reason: str = "Parada de Emergência acionada pelo Gêmeo Digital"):
        """Envia o comando de parada imediata para o CLP."""
        logger.warning(f"🛑 [EMERGÊNCIA] {reason}")
        await self.write_tag("desligar", True)
        await self.write_tag("stop", True)

    async def reset_plant(self):
        """Envia o comando de reset para restabelecer a operação normal."""
        logger.info("🔄 [RESET] Enviando comando de reset para a planta...")
        self.petri_engine.clear_anomalies()
        await self.write_tag("desligar", False)
        await self.write_tag("stop", False)
        await self.write_tag("reset", True)
        await asyncio.sleep(0.3)
        await self.write_tag("reset", False)

    async def start_plant(self):
        """Envia o pulso de START para a planta."""
        logger.info("▶️ [START] Enviando pulso de partida...")
        await self.write_tag("start", True)
        await asyncio.sleep(0.3)
        await self.write_tag("start", False)

    def inject_fault(self, fault_type: str):
        """Injeta uma falha no motor da Rede de Petri e aciona o protocolo de segurança."""
        anomaly = self.petri_engine.inject_synthetic_anomaly(fault_type)
        if anomaly.severity == "CRITICAL":
            asyncio.create_task(self.emergency_stop(reason=anomaly.message))
        return anomaly

    def get_full_state(self) -> Dict[str, Any]:
        """Retorna o estado consolidado de todas as camadas do Gêmeo Digital."""
        petri_summary = self.petri_engine.get_status_summary()
        self.aas.update_from_telemetry(self.petri_engine.tags, petri_summary)
        return {
            "is_connected": self.is_connected,
            "sanitizer_metrics": self.sanitizer.get_audit_summary(),
            "petri_net": petri_summary,
            "aas_model": self.aas.to_basyx_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def disconnect(self):
        """Encerra a conexão limpa com o servidor."""
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass
            self.is_connected = False
            logger.info("Conexão OPC UA finalizada.")
