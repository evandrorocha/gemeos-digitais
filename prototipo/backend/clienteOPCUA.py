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
           "p13": 0, "p16": 1}

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

eventos = {"start_P": ["t1"], 
           "palletSensor_P": ["t2"],
           "loaded_P": ["t4"],
           "atLeftEntry_P": ["t6"],
           "atLeftExit_P": ["t7"],
           "atRightEntry_P": ["t9"],
           "atRightExit_P": ["t10"],
           "stop_N": ["t12"],
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
        
async def enviar_comando(tags_por_nome, tag, novo_valor):
    """
    Escreve um valor em uma tag OPC UA.

    Args:
        tags_por_nome: dicionário com nome da tag -> objeto Node.
        tag: nome da tag no CODESYS.
        novo_valor: valor a ser escrito.
    """
    node = tags_por_nome.get(tag)

    if node is None:
        raise ValueError(f"Tag '{tag}' não encontrada.")

    try:
        tipo = await node.read_data_type_as_variant_type()
        valor = ua.DataValue(
            ua.Variant(novo_valor, tipo)
        )

        await node.write_value(valor)

        print(f"Comando enviado: {tag} = {novo_valor}")
        return True

    except Exception as erro:
        print(f"Erro ao escrever na tag '{tag}': {erro}")
        return False

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
        tags_por_nome = {}
        for node in tags:
            browse_name = await node.read_browse_name()
            nome = browse_name.Name

            tag_names[str(node.nodeid)] = browse_name.Name
            tags_por_nome[nome] = node

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

        identificationStarted = False

        # Iniciar valores das tags de escrita do servidor OPC UA
        await enviar_comando(tags_por_nome, "stopDT", False)
        await enviar_comando(tags_por_nome, "startDT", False)

        try:
            while True:
                event_message = await event_queue.get()

                try:
                    # Apenas faz a verificação de eventos quando der start
                    if event_message == "start_P": identificationStarted = True
                    # Desativa trigger da tag de escrita
                    if event_message == "stopDT_P": 
                        await enviar_comando(tags_por_nome, "stopDT", False)
                    if event_message == "startDT_P": 
                        await enviar_comando(tags_por_nome, "startDT", False)

                    if identificationStarted:
                        if event_message == "alto_P":
                            redeSortingByHeight.atualizar_variavel("alto", 1)
                        elif event_message == "alto_N":
                            redeSortingByHeight.atualizar_variavel("alto", 0)
                        elif event_message in eventos:
                            if (not redeSortingByHeight.processar_evento(event_message)[0]):
                                await enviar_comando(tags_por_nome, "stopDT", True)
                finally:
                    event_queue.task_done()

        except KeyboardInterrupt:
            print("\nEncerrando...")

        finally:
            await subscription.delete()


if __name__ == "__main__":
    asyncio.run(main())