import asyncio
from asyncua import Client, ua


# Endereço do servidor OPC UA do CODESYS
URL = "opc.tcp://127.0.0.1:4840"

# NodeId do PLC_PRG
PLC_PRG_NODE = (
    "ns=4;s=|var|CODESYS Control Win V3 x64."
    "Application.PLC_PRG"
)


class SubscriptionHandler:
    """
    Recebe as mudanças enviadas pelo servidor OPC UA.
    """

    def datachange_notification(self, node, val, data):
        try:
            print(f"{node.nodeid} = {val}")
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

        # Cria o handler que receberá as mudanças
        handler = SubscriptionHandler()

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
                await asyncio.sleep(1)

        except KeyboardInterrupt:

            print("\nEncerrando...")

        finally:

            await subscription.delete()


if __name__ == "__main__":
    asyncio.run(main())