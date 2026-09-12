import os
import asyncio
from asyncua import Client, ua
from redeDePetri import RedePetri


URL = os.getenv("OPCUA_SERVER_URL", "opc.tcp://127.0.0.1:4840")

PLC_PRG_NODE = os.getenv(
    "PLC_PRG_NODE_ID",
    "ns=4;s=|var|CODESYS Control Win V3 x64.Application.PLC_PRG"
)

EVENTOS = {
    "start_P": ["t1"],
    "startDT_P": ["t1"],
    "palletSensor_P": ["t2"],
    "loaded_P": ["t4"],
    "atLeftEntry_P": ["t6"],
    "atLeftExit_P": ["t7"],
    "atRightEntry_P": ["t9"],
    "atRightExit_P": ["t10"],
    "stop_N": ["t12"],
    "reset_P": ["t14"],
}


class SubscriptionHandler:
    def __init__(self, tag_names, event_queue, on_datachange=None, on_status_change=None):
        self.tag_names = tag_names
        self.event_queue = event_queue
        self.on_datachange = on_datachange
        self.on_status_change = on_status_change

    def datachange_notification(self, node, value, data):
        try:
            tag_name = self.tag_names.get(str(node.nodeid), str(node.nodeid))

            if self.on_datachange is not None:
                self.on_datachange(tag_name, value)
            else:
                suffix = "P" if value else "N"
                event = f"{tag_name}_{suffix}"
                self.event_queue.put_nowait(event)

        except Exception as error:
            print(f"Erro na notificação OPC UA: {error}")

    def status_change_notification(self, status):
        try:
            if self.on_status_change is not None:
                self.on_status_change(status)
        except Exception as error:
            print(f"Erro na notificação de status OPC UA: {error}")


class OPCUAService:
    def __init__(self, rede_petri, url=URL, plc_node=PLC_PRG_NODE, on_datachange=None, on_status_change=None):
        self.rede_petri = rede_petri
        self.url = url
        self.plc_node_id = plc_node
        self.on_datachange = on_datachange
        self.on_status_change = on_status_change

        self.client = None
        self.subscription = None
        self.event_queue = asyncio.Queue(maxsize=100)
        self.stop_event = asyncio.Event()

        self.tags = []
        self.tags_por_nome = {}
        self.tag_names = {}

        self.identification_started = False

    async def connect(self):
        self.tags = []
        self.tags_por_nome = {}
        self.tag_names = {}

        self.client = Client(url=self.url)
        await self.client.connect()

        candidate_nodes = [
            self.plc_node_id,
            self.plc_node_id.replace("Control Win V3.", "Control Win V3 x64."),
            self.plc_node_id.replace("Control Win V3 x64.", "Control Win V3.")
        ]

        children = []
        for candidate in candidate_nodes:
            try:
                node = self.client.get_node(candidate)
                ch = await node.get_children()
                if ch:
                    self.plc_node_id = candidate
                    children = ch
                    break
            except Exception:
                continue

        for node in children:
            node_class = await node.read_node_class()

            if node_class != ua.NodeClass.Variable:
                continue

            browse_name = await node.read_browse_name()
            tag_name = browse_name.Name

            self.tags.append(node)
            self.tags_por_nome[tag_name] = node
            self.tag_names[str(node.nodeid)] = tag_name

        handler = SubscriptionHandler(
            self.tag_names,
            self.event_queue,
            on_datachange=self.on_datachange,
            on_status_change=self.on_status_change
        )

        self.subscription = await self.client.create_subscription(100, handler)

        # Batch subscription em lotes de 20 para respeitar o limite de operações do CODESYS
        for i in range(0, len(self.tags), 20):
            chunk = self.tags[i:i+20]
            await self.subscription.subscribe_data_change(chunk)

        print(f"Conectado. {len(self.tags)} tags monitoradas.")

    async def write_tag(self, tag_name, value):
        node = self.tags_por_nome.get(tag_name)

        if node is None:
            raise ValueError(f"Tag '{tag_name}' não encontrada.")

        try:
            if not hasattr(self, "_data_types_cache"):
                self._data_types_cache = {}
            if tag_name not in self._data_types_cache:
                self._data_types_cache[tag_name] = await node.read_data_type_as_variant_type()
            data_type = self._data_types_cache[tag_name]
            data_value = ua.DataValue(ua.Variant(value, data_type))

            await node.write_value(data_value)
            return True

        except Exception as erro:
            print(f"Erro ao escrever na tag '{tag_name}': {erro}")
            return False

    async def read_tag(self, tag_name):
        node = self.tags_por_nome.get(tag_name)

        if node is None:
            raise ValueError(f"Tag '{tag_name}' não encontrada.")

        return await node.read_value()

    async def process_event(self, event):
        if event == "start_P" or event == "startDT_P":
            self.identification_started = True

        if event == "stopDT_P":
            await self.write_tag("stopDT", False)
            return

        if event == "startDT_P":
            await self.write_tag("startDT", False)

        if event == "resetDT_P":
            await self.write_tag("resetDT", False)

        if not self.identification_started:
            return

        if event == "alto_P":
            self.rede_petri.atualizar_variavel("alto", 1)

        elif event == "alto_N":
            self.rede_petri.atualizar_variavel("alto", 0)

        elif event in EVENTOS:
            # Ignora START redundante se a Rede de Petri já saiu de p1
            if event in ("start_P", "startDT_P") and self.rede_petri.estados.get("p1", 0) == 0:
                return

            success, message = self.rede_petri.processar_evento(event)

            if not success:
                await self.write_tag("stopDT", True)

            print(message)

    async def run(self):
        await self.connect()

        await self.write_tag("stopDT", False)
        await self.write_tag("startDT", False)
        await self.write_tag("resetDT", False)

        print("Monitoramento iniciado.")

        while not self.stop_event.is_set():
            try:
                event = await asyncio.wait_for(
                    self.event_queue.get(),
                    timeout=0.5,
                )

                try:
                    await self.process_event(event)
                finally:
                    self.event_queue.task_done()

            except asyncio.TimeoutError:
                continue

    async def close(self):
        self.stop_event.set()

        if self.subscription is not None:
            try:
                await self.subscription.delete()
            except Exception:
                pass
            self.subscription = None

        if self.client is not None:
            try:
                await self.client.disconnect()
            except Exception:
                pass
            self.client = None

        self.tags = []
        self.tags_por_nome = {}
        self.tag_names = {}