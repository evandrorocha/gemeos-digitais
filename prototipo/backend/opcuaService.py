import asyncio
from asyncua import Client, ua
from redeDePetri import RedePetri


URL = "opc.tcp://127.0.0.1:4840"

PLC_PRG_NODE = (
    "ns=4;s=|var|CODESYS Control Win V3."
    "Application.PLC_PRG"
)

EVENTOS = {
    "start_P": ["t1"],
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
    def __init__(self, tag_names, event_queue):
        self.tag_names = tag_names
        self.event_queue = event_queue

    def datachange_notification(self, node, value, data):
        try:
            tag_name = self.tag_names.get(str(node.nodeid), str(node.nodeid))

            suffix = "P" if value else "N"
            event = f"{tag_name}_{suffix}"

            self.event_queue.put_nowait(event)

        except Exception as error:
            print(f"Erro na notificação OPC UA: {error}")


class OPCUAService:
    def __init__(self, rede_petri, url=URL, plc_node=PLC_PRG_NODE):
        self.rede_petri = rede_petri
        self.url = url
        self.plc_node_id = plc_node

        self.client = None
        self.subscription = None
        self.event_queue = asyncio.Queue(maxsize=100)
        self.stop_event = asyncio.Event()

        self.tags = []
        self.tags_por_nome = {}
        self.tag_names = {}

        self.identification_started = False

    async def connect(self):
        self.client = Client(url=self.url)
        await self.client.connect()

        plc_node = self.client.get_node(self.plc_node_id)
        children = await plc_node.get_children()

        for node in children:
            node_class = await node.read_node_class()

            if node_class != ua.NodeClass.Variable:
                continue

            browse_name = await node.read_browse_name()
            tag_name = browse_name.Name

            self.tags.append(node)
            self.tags_por_nome[tag_name] = node
            self.tag_names[str(node.nodeid)] = tag_name

        handler = SubscriptionHandler(self.tag_names, self.event_queue)

        self.subscription = await self.client.create_subscription(100, handler)

        await self.subscription.subscribe_data_change(self.tags)

        print(f"Conectado. {len(self.tags)} tags monitoradas.")

    async def write_tag(self, tag_name, value):
        node = self.tags_por_nome.get(tag_name)

        if node is None:
            raise ValueError(f"Tag '{tag_name}' não encontrada.")

        try:
            data_type = await node.read_data_type_as_variant_type()
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
        if event == "start_P":
            self.identification_started = True

        if event == "stopDT_P":
            await self.write_tag("stopDT", False)
            return

        if event == "startDT_P":
            await self.write_tag("startDT", False)
            return

        if not self.identification_started:
            return

        if event == "alto_P":
            self.rede_petri.atualizar_variavel("alto", 1)

        elif event == "alto_N":
            self.rede_petri.atualizar_variavel("alto", 0)

        elif event in EVENTOS:
            success, message = self.rede_petri.processar_evento(event)

            if not success:
                await self.write_tag("stopDT", True)

            print(message)

    async def run(self):
        await self.connect()

        await self.write_tag("stopDT", False)
        await self.write_tag("startDT", False)

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
            await self.subscription.delete()

        if self.client is not None:
            await self.client.disconnect()