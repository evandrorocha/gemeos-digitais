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
                        "p14": ["t16"],
                        "p15": ["t17"],
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
                        "t15": ["p1"],
                        "t16": ["p15"],
                        "t17": ["p14"]}

eventos = {"start_P": ["t1"], 
           "palletSensor_P": ["t2"],
           "loaded_P": ["t4"],
           "alto_P": ["t18"],
           "alto_N": ["t5"],
           "atLeftEntry_P": ["t6"],
           "atLeftExit_P": ["t7"],
           "atRightEntry_P": ["t9", "t17"],
           "atRightExit_P": ["t10"],
           "highSensor": ["t16"],
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

    def createEventMessage(self):
        # # Descarta o evento do contador
        # if (self.current_name == "contador"): return

        # Adiciona informação de borda de subida (P) ou borda de descida (N)
        if self.current_value:
            mensagem = self.current_name + "_P"
        else:
            mensagem = self.current_name + "_N"
        return mensagem
        


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
            while True:

                if (not handler.current_checked):
                    # print(f"{handler.current_name:20} = {handler.current_value}")
                    print(handler.createEventMessage())

                    handler.current_checked = True                
                    eventMessage = handler.createEventMessage()

                    # Descarta evento do contador
                    if (eventMessage == "contador_P") or (eventMessage == "contador_N"):
                        continue
                    # Caso altere a tag "alto", muda o valor interno na rede de petri
                    if (eventMessage == "alto_P"):              
                        redeSortingByHeight.atualizar_variavel("alto", 1)
                    elif (eventMessage == "alto_N"):
                        redeSortingByHeight.atualizar_variavel("alto", 0)
                    # Atualiza a rede e printa o estado atual
                    else:
                        redeSortingByHeight.processar_evento(eventMessage)

                await asyncio.sleep(0.5)

        except KeyboardInterrupt:

            print("\nEncerrando...")

        finally:

            await subscription.delete()


if __name__ == "__main__":
    asyncio.run(main())