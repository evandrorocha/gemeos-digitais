import asyncio
from asyncua import Client, ua
from redeDePetri import RedePetri

# Endereço do servidor OPC UA do CODESYS
URL = "opc.tcp://127.0.0.1:4840"

# NodeId do PLC_PRG
PLC_PRG_NODE = (
    "ns=4;s=|var|CODESYS Control Win V3."
    "Application.PLC_PRG"
)

# Rede de Petri
lugares = {"p1": 1, "p2": 0, "p3": 0, "p4": 0, 
           "p5": 0, "p6": 0, "p7": 0, "p8": 0, 
           "p9": 0, "p10": 0, "p11": 0, "p12": 0, 
           "p13": 0, "p14": 1, "p15": 0, "p16": 1}

lugares2transicoes = {"p1": ["t1"], 
                        "p2": ["t2"],
                        "p3": ["t3"],
                        "p4": ["t4"],
                        "p5": ["t5", "t8"],
                        "p6": ["t6"],
                        "p7": ["t7"],
                        "p8": ["t9"],
                        "p9": ["t10"],
                        "p10": ["t11"],
                        "p11": ["t12", "t14"],
                        "p12": ["t13"],
                        "p13": ["t15"],
                        # "p14": ["t16"],
                        # "p15": ["t17"],
                        "p16": ["t3"]}

transicoes2lugares = {"t1": ["p2", "p11"],
                        "t2": ["p3"],
                        "t2": ["p3"],
                        "t3": ["p2", "p4"],
                        "t4": ["p5"],
                        "t5": ["p6"],
                        "t6": ["p7", "p16"],
                        "t7": ["p10"],
                        "t8": ["p8"],
                        "t9": ["p9", "p16"],
                        "t10": ["p10"],
                        "t11": ["empty"],
                        "t12": ["p12"],
                        "t13": ["p1"],
                        "t14": ["p13"],
                        "t15": ["p1"],}
                        # "t16": ["p15"],
                        # "t17": ["p14"]

eventos = {"start_P": ["t1"], 
           "palletSensor_P": ["t2"],
           "loaded_P": ["t4"],
           "atLeftEntry_P": ["t6"],
           "atLeftExit_P": ["t7"],
           "atRightEntry_P": ["t9"], #, "t17"
           "atRightExit_P": ["t10"],
        #    "highSensor": ["t16"],
           "stop_P": ["t12"],
           "reset_P": ["t14"]}

variaveis = {"alto": 0}
condicoes = {"t5": ("alto", 0),
             "t8": ("alto", 1)}

redeSortingByHeight = RedePetri(lugares, lugares2transicoes, transicoes2lugares, eventos, variaveis, condicoes)

class SubscriptionHandler:
    """
    Recebe as mudanças enviadas pelo servidor OPC UA.
    """

    def __init__(self, tag_names, event_queue):
        self.tag_names = tag_names
        self.event_queue = event_queue

    def datachange_notification(self, node, val, data):
        try:
            name = self.tag_names.get(
                str(node.nodeid), 
                str(node.nodeid))

            mensagem = f"{name}_{'P' if val else 'N'}"
            # Não bloqueia o callback da subscription
            self.event_queue.put_nowait(mensagem)

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

        event_queue = asyncio.Queue()
        event_queue = asyncio.Queue(maxsize=100)
        # Cria o handler que receberá as mudanças
        handler = SubscriptionHandler(tag_names, event_queue)

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
            while True:
                event_message = await event_queue.get()

                try:

                    if event_message == "alto_P":
                        redeSortingByHeight.atualizar_variavel("alto", 1)
                        print(redeSortingByHeight.variaveis["alto"])
                    elif event_message == "alto_N":
                        redeSortingByHeight.atualizar_variavel("alto", 0)
                        print(redeSortingByHeight.variaveis["alto"])
                    elif event_message in eventos:
                        print(event_message)
                        print(redeSortingByHeight.processar_evento(event_message))

                    # redeSortingByHeight.mostrar_estados()

                finally:
                    event_queue.task_done()

        except KeyboardInterrupt:
            print("\nEncerrando...")

        finally:
            await subscription.delete()


if __name__ == "__main__":
    asyncio.run(main())