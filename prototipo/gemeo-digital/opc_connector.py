"""
Conector OPC UA Bidirecional do Gêmeo Digital
Gerencia a subscrição assíncrona com o CODESYS, sanitização de dados,
alimentação do motor de Rede de Petri, atualização do AAS e envio de comandos de controle.
"""

import asyncio
import logging
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Any
from asyncua import Client, Node, ua
from config import OPCUA_SERVER_URL, PLC_PRG_NODE_ID, SAMPLING_RATE_MS
from data_sanitizer import DataSanitizer, SanitizedEvent
from petri_engine import PetriNetEngine, AnomalyReport
from aas_model import AssetAdministrationShell

# Importação da classe OPCUAService desenvolvida pelo Caio no backend
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from opcuaService import OPCUAService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OPC_CONNECTOR")


class DigitalTwinConnector:
    """
    Controlador central do Gêmeo Digital:
    Utiliza a camada de transporte OPCUAService do Caio, sanitiza dados,
    executa a Rede de Petri e atualiza o modelo AAS.
    """

    def __init__(self, url: str = OPCUA_SERVER_URL):
        self.url = url
        self.petri_engine = PetriNetEngine()
        self.sanitizer = DataSanitizer()
        self.aas = AssetAdministrationShell()
        self.is_connected = False
        self.last_data_received_time: float = 0.0
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self.on_state_change_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._incoming_box_is_tall: bool = False

        # Instancia o serviço de transporte OPC UA oficial do backend (desenvolvido pelo Caio)
        self.service = OPCUAService(
            rede_petri=self.petri_engine.petri_net,
            url=self.url,
            plc_node=PLC_PRG_NODE_ID,
            on_datachange=self.process_incoming_tag,
            on_status_change=self._handle_opcua_status_change
        )
        self.client: Optional[Client] = None
        self._nodes_cache: Dict[str, Node] = {}
        self._node_id_to_name: Dict[str, str] = {}

    def _handle_opcua_status_change(self, status):
        """Notificação de status da subscrição OPC UA."""
        status_code = getattr(status, "Status", status)
        code_name = getattr(status_code, "name", str(status_code))
        # BadShutdown ocorre normalmente quando uma sessão anterior é finalizada
        if code_name in ("BadShutdown", "Good", "BadNoSubscription"):
            logger.debug(f"Notificação normal de status OPC UA: {code_name}")
            return
        if "Bad" in code_name:
            logger.warning(f"Queda real de conexão indicada pelo servidor OPC UA: {code_name}")
            self.is_connected = False

    def register_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Registra um callback para notificar interfaces externas (ex: Dashboard)."""
        self.on_state_change_callbacks.append(callback)

    def process_incoming_tag(self, tag_name: str, raw_value: Any):
        """Pipeline de processamento: Bruto -> Sanitizado -> Petri -> AAS -> Ação."""
        self.last_data_received_time = time.time()
        self.is_connected = True

        # 1. Sanitização do Dado
        event = self.sanitizer.sanitize(tag_name, raw_value, source_uri=self.url)
        if event is None:
            return # Ruído descartado

        # Se o operador apertar o botão físico RESET no Factory I/O:
        if tag_name == "reset" and event.value is True:
            logger.info("Botão físico RESET do Factory I/O pressionado. Executando reset_plant()...")
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(self.reset_plant(), self._loop)
            else:
                asyncio.create_task(self.reset_plant())

        # Coordenação de Classificação no CLP:
        # 1. Quando highSensor detecta Caixa Alta na esteira de entrada:
        if tag_name == "highSensor" and event.value is True:
            self._incoming_box_is_tall = True
            logger.info("📦 [CLASSIFICAÇÃO] Caixa Alta detectada pelo sensor óptico! Ativando alto=True no CLP.")
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(self.write_tag("alto", True), self._loop)
            else:
                asyncio.create_task(self.write_tag("alto", True))

        # 2. Quando a caixa chega na mesa de transferência (loaded=True):
        elif tag_name == "loaded" and event.value is True:
            target_alto = bool(self._incoming_box_is_tall)
            if self.petri_engine.tags.get("alto") != target_alto:
                if self._loop and self._loop.is_running():
                    asyncio.run_coroutine_threadsafe(self.write_tag("alto", target_alto), self._loop)
                else:
                    asyncio.create_task(self.write_tag("alto", target_alto))

        # 3. Quando a caixa é transferida e desocupa a mesa (loaded vai para False):
        elif tag_name == "loaded" and event.value is False:
            self._incoming_box_is_tall = False
            # Só reseta 'alto' para False no CLP se o highSensor não estiver vendo outra caixa alta entrando simultaneamente
            if not self.petri_engine.tags.get("highSensor") and self.petri_engine.tags.get("alto"):
                if self._loop and self._loop.is_running():
                    asyncio.run_coroutine_threadsafe(self.write_tag("alto", False), self._loop)
                else:
                    asyncio.create_task(self.write_tag("alto", False))

        # 2. Atualização da Rede de Petri e Detecção de Falhas
        anomaly = self.petri_engine.update_from_sanitized_event(event)

        # 3. Atualização do Modelo AAS (BaSyx)
        petri_status = self.petri_engine.get_status_summary()
        self.aas.update_from_telemetry(self.petri_engine.tags, petri_status)

        # 4. Ação Autônoma do Gêmeo Digital: Se houver anomalia crítica, envia STOP de emergência
        if anomaly and anomaly.severity == "CRITICAL":
            logger.warning(f"🚨 ANOMALIA CRÍTICA DETECTADA: {anomaly.message}")
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(self.emergency_stop(reason=anomaly.message), self._loop)
            else:
                asyncio.create_task(self.emergency_stop(reason=anomaly.message))

        # 5. Notifica ouvintes registrados
        current_state = self.get_full_state()
        for cb in self.on_state_change_callbacks:
            try:
                cb(current_state)
            except Exception as e:
                logger.error(f"Erro em callback de estado: {e}")

    async def reconnect(self):
        """Restabelece a conexão limpa com o servidor OPC UA via OPCUAService."""
        if self.service:
            try:
                await self.service.close()
            except Exception:
                pass
        self.is_connected = False
        self._nodes_cache.clear()
        self._node_id_to_name.clear()

        logger.info(f"Conectando ao servidor OPC UA em {self.url} via OPCUAService...")
        await self.service.connect()
        self.is_connected = True
        self.client = self.service.client
        self._nodes_cache = self.service.tags_por_nome
        self._node_id_to_name = self.service.tag_names
        logger.info(f"✅ Conectado com sucesso via OPCUAService! {len(self._nodes_cache)} tags monitoradas.")

        initial_baseline = {}
        for tag_name, node in self._nodes_cache.items():
            try:
                initial_baseline[tag_name] = await node.read_value()
            except Exception:
                pass

        self.petri_engine.set_baseline_tags(initial_baseline)
        logger.info(f"Cache e baseline inicial sincronizados ({len(initial_baseline)} variáveis).")

    async def connect_and_subscribe(self):
        """Estabelece a conexão OPC UA e inicia a subscrição assíncrona."""
        self._loop = asyncio.get_running_loop()
        await self.reconnect()

        # Inicia loop de monitoramento contínuo em segundo plano para detecção em tempo real de timeouts
        if not self._monitor_task or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self._periodic_monitor_loop())

        # Auto-Higienização e Inicialização Segura do CLP
        logger.info("🔧 Executando auto-higienização da Rede de Petri no CLP...")
        await self.auto_initialize_plc()

    async def _periodic_monitor_loop(self):
        """Loop contínuo de segundo plano para monitorar timeouts, sensores travados e reconexão automática."""
        last_liveness_check = time.time()
        while True:
            try:
                now = time.time()
                # 1. Heartbeat proativo a cada 5.0 segundos apenas se não houver dados recentes
                time_since_data = now - getattr(self, "last_data_received_time", 0.0)
                if self.is_connected and (now - last_liveness_check > 5.0):
                    last_liveness_check = now
                    # Se recebemos telemetria recente nos últimos 5 segundos, a conexão está viva
                    if time_since_data > 5.0:
                        try:
                            if self.client:
                                await self.client.check_connection()
                            else:
                                self.is_connected = False
                        except Exception as e:
                            logger.warning(f"Queda de conexão detectada via check_connection: {e}")
                            self.is_connected = False

                # 2. Se desconectado, tenta reconexão automática com intervalo controlado
                if not self.is_connected:
                    logger.info("Conexão OPC UA inativa ou perdida. Tentando reconectar...")
                    try:
                        await self.reconnect()
                    except Exception as e:
                        logger.debug(f"Aguardando servidor OPC UA ficar disponível: {e}")
                        await asyncio.sleep(3.0)
                        continue

                # 3. Checagem em tempo real de anomalias (timeouts e travamentos)
                anomaly = self.petri_engine.check_anomalies()
                if anomaly and anomaly.severity == "CRITICAL" and anomaly.is_active:
                    # Se ainda não desligou, dispara emergency_stop autônomo
                    if self.is_connected and not self.petri_engine.tags.get("stopDT"):
                        logger.warning(f"🚨 [MONITOR PERIÓDICO] Falha crítica detectada: {anomaly.message}")
                        await self.emergency_stop(reason=anomaly.message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no loop periódico de monitoramento: {e}")
                err_str = str(e).lower()
                if "disconnect" in err_str or "connection" in err_str or "closed" in err_str:
                    self.is_connected = False
            await asyncio.sleep(0.25)

    async def auto_initialize_plc(self):
        """Garante que as travas do Gêmeo Digital estejam liberadas e o CLP em prontidão."""
        try:
            await self.write_tag("stopDT", False)
            await self.write_tag("startDT", False)
            await self.write_tag("desligar", False)
            if "p1" in self.service.tags_por_nome:
                for p in [f"p{i}" for i in range(2, 16)]:
                    await self.write_tag(p, False)
                await self.write_tag("p1", True)
                await self.write_tag("p16", True)
            logger.info("✅ Conexão inicializada. Travas liberadas e estado de prontidão verificado no CLP.")
        except Exception as e:
            logger.warning(f"Aviso na inicialização do conector: {e}")

    async def write_tag(self, tag_name: str, value: Any):
        """Escreve um valor em uma tag no CODESYS via OPCUAService de forma segura."""
        if not self.is_connected or not self.service or not self.client:
            logger.warning(f"Tentativa de escrita em '{tag_name}' sem conexão ativa!")
            return False

        # Garante que só escrevemos em nós que realmente existem no CLP
        if tag_name not in self.service.tags_por_nome:
            logger.debug(f"Tag '{tag_name}' não existe no CLP (variável puramente interna). Ignorando envio físico.")
            return False

        try:
            success = await self.service.write_tag(tag_name, value)
            if success:
                logger.info(f"Comando gravado com sucesso: {tag_name} = {value}")
            else:
                try:
                    if self.client:
                        await self.client.check_connection()
                except Exception:
                    self.is_connected = False
            return success
        except Exception as e:
            logger.error(f"Erro ao escrever na tag {tag_name}: {e}")
            err_str = str(e).lower()
            if "disconnect" in err_str or "connection" in err_str or "closed" in err_str:
                self.is_connected = False
            return False

    async def read_tag(self, tag_name: str):
        """Lê o valor de uma tag utilizando o OPCUAService."""
        if not self.service or not self.is_connected:
            return None
        return await self.service.read_tag(tag_name)

    async def emergency_stop(self, reason: str = "Parada de Emergência acionada pelo Gêmeo Digital"):
        """Envia o comando de parada imediata para o CLP desligando todos os motores na hora."""
        logger.warning(f"🛑 [EMERGÊNCIA] {reason}")
        await self.write_tag("stopDT", True)
        await self.write_tag("stop", False)  # Botão de parada acionado (NF -> False)
        await self.write_tag("conveyorEntry", False)
        await self.write_tag("load", False)
        await self.write_tag("transferLeft", False)
        await self.write_tag("transferRight", False)

    async def reset_plant(self):
        """Envia o comando de reset para restabelecer a operação normal e a marcação inicial de Petri."""
        logger.info("🔄 [RESET] Enviando comando de reset e restaurando marcação inicial no CLP...")
        self.petri_engine.clear_anomalies()
        self.petri_engine.reset()
        
        # 1. Desarma as tags de controle do Gêmeo Digital (DT)
        await self.write_tag("stopDT", False)
        await self.write_tag("startDT", False)
        
        # 2. Desarma travas e zera comandos de start
        self._incoming_box_is_tall = False
        await self.write_tag("stop", True)  # NF restaurado
        await self.write_tag("desligar", False)
        await self.write_tag("alto", False)
        await self.write_tag("start", False)

        # 3. Envia pulso de reset físico para o circuito Ladder do CLP
        await self.write_tag("reset", True)
        await asyncio.sleep(0.3)
        await self.write_tag("reset", False)

        # 4. Restaura estritamente a marcação inicial da Rede de Petri no CLP (limpa bobinas presas)
        if "p1" in self.service.tags_por_nome:
            for p in [f"p{i}" for i in range(2, 16)]:
                await self.write_tag(p, False)
            await self.write_tag("p1", True)
            await self.write_tag("p16", True)
            logger.info("✅ Marcação inicial restaurada no CLP (p1=True, p16=True, p2..p15=False).")

    async def start_plant(self):
        """Envia o pulso de START para a planta garantindo transição limpa para p2."""
        logger.info("▶️ [START] Liberando travas e iniciando movimento da esteira...")
        self.petri_engine.clear_anomalies()

        await self.write_tag("stopDT", False)
        await self.write_tag("stop", True)

        await self.write_tag("start", True)
        await self.write_tag("startDT", True)
        await asyncio.sleep(0.3)
        await self.write_tag("start", False)
        await self.write_tag("startDT", False)

    def inject_fault(self, fault_type: str):
        """Injeta uma falha no motor da Rede de Petri e aciona o protocolo de segurança de forma thread-safe."""
        anomaly = self.petri_engine.inject_synthetic_anomaly(fault_type)
        if anomaly and anomaly.severity == "CRITICAL":
            if self._loop and self._loop.is_running():
                asyncio.run_coroutine_threadsafe(self.emergency_stop(reason=anomaly.message), self._loop)
            else:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.emergency_stop(reason=anomaly.message))
                except RuntimeError:
                    logger.warning("Nenhum loop assíncrono disponível para disparar emergency_stop da falha.")
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
        if self._monitor_task:
            self._monitor_task.cancel()
        if self.client:
            try:
                await self.client.disconnect()
            except Exception:
                pass
            self.is_connected = False
            logger.info("Conexão OPC UA finalizada.")
