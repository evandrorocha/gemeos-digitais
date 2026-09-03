from asyncua import Client
import asyncio


async def main():

    url = "opc.tcp://127.0.0.1:4840"

    async with Client(url=url) as client:

        plc_prg = client.get_node(
            "ns=4;s=|var|CODESYS Control Win V3.Application.PLC_PRG"
        )

        children = await plc_prg.get_children()

        tags = {}

        for node in children:

            browse_name = await node.read_browse_name()

            tags[browse_name.Name] = await node.read_value()

        print(tags)


asyncio.run(main())