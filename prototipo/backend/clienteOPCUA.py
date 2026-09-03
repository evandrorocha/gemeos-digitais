import asyncio
from asyncua import Client, ua
from prototipo.backend.redeDePetri import RedePetri


# Endereço do servidor OPC UA do CODESYS
URL = "opc.tcp://127.0.0.1:4840"

# NodeId do PLC_PRG
PLC_PRG_NODE = (
    "ns=4;s=|var|CODESYS Control Win V3."
    "Application.PLC_PRG"
)

# Rede de Petri
lugares = {"p1": 2, "p2": 0}
transicoes = {"p1": {"t1": ["p1", "p2"], "t2": ["p3"]}, "p2": {"t3": ["p4"]}}
eventos = {"sensor1_P": ["t1", "t2"], "sensor2_N": ["t3"]}
rede = RedePetri(lugares, transicoes, eventos)


class SubscriptionHandler:
    """
    Recebe as mudanças enviadas pelo servidor OPC UA.
    """

    def __init__(self, tag_names):
        self.tag_names = tag_names
        self.current_name = ""
        self.current_value = False
        self.current_checked = False

    def datachange_notification(self, node, val, data):
        try:
            name = self.tag_names.get(str(node.nodeid), str(node.nodeid))
            # print(f"{name:20} = {val}")

            self.current_name = name
            self.current_value = val
            self.current_checked = False

        except Exception as e:
            print(f"Erro ao processar atualização: {e}")


async def main():

    print("Conectando ao CODESYS OPC UA...")

    async with Client(url=URL) as client:

        print("Conectado!")
        print()

        # Obtém o nó PLC_PRG
        plc_prg = client.get_node(PLC_PRG_NODE)

        # Obtém todas as variáveis dentro de PLC_PRG
        children = await plc_prg.get_children()

        # Selecionamos apenas Variable Nodes
        tags = []

        print("Tags encontradas:")
        print("-" * 60)

        for node in children:

            node_class = await node.read_node_class()

            if node_class == ua.NodeClass.Variable:

                browse_name = await node.read_browse_name()

                print(
                    f"{browse_name.Name:20} "
                    f"{node.nodeid}"
                )

                tags.append(node)

        print("-" * 60)
        print(f"{len(tags)} tags monitoradas.")
        print()

        tag_names = {}
        for node in tags:
            browse_name = await node.read_browse_name()
            tag_names[str(node.nodeid)] = browse_name.Name

        # Cria o handler que receberá as mudanças
        handler = SubscriptionHandler(tag_names)

        # Cria uma subscription
        subscription = await client.create_subscription(
            100,  # período de publicação em ms
            handler
        )

        # Monitora todas as tags encontradas
        await subscription.subscribe_data_change(tags)

        print("Monitoramento iniciado.")
        print("Aguardando alterações...\n")

        try:

            # Mantém o programa executando
            while True:

                if (not handler.current_checked):
                    print(f"{handler.current_name:20} = {handler.current_value}")
                    handler.current_checked = True                

                await asyncio.sleep(0.5)

        except KeyboardInterrupt:

            print("\nEncerrando...")

        finally:

            await subscription.delete()


if __name__ == "__main__":
    asyncio.run(main())