import asyncio

from redeDePetri import RedePetri
from opcuaService import OPCUAService

LUGARES = {"p1": 1, "p2": 0, "p3": 0, "p4": 0, 
           "p5": 0, "p6": 0, "p7": 0, "p8": 0, 
           "p9": 0, "p10": 0, "p11": 0, "p12": 0, 
           "p13": 0, "p16": 1}

LUGARES2TRANSICOES = {"p1": ["t1"], 
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

TRANSICOES2LUGARES = {"t1": ["p2", "p11"],
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

EVENTOS = {"start_P": ["t1"], 
           "palletSensor_P": ["t2"],
           "loaded_P": ["t4"],
           "atLeftEntry_P": ["t6"],
           "atLeftExit_P": ["t7"],
           "atRightEntry_P": ["t9"],
           "atRightExit_P": ["t10"],
           "stop_N": ["t12"],
           "reset_P": ["t14"]}

VARIAVEIS = {"alto": 0}
CONDICOES = {"t5": ("alto", 0),
             "t8": ("alto", 1)}

async def main():
    rede_petri = RedePetri(
        LUGARES,
        LUGARES2TRANSICOES,
        TRANSICOES2LUGARES,
        EVENTOS,
        VARIAVEIS,
        CONDICOES,
    )

    service = OPCUAService(rede_petri)

    try:
        await service.run()

    except KeyboardInterrupt:
        print("Encerrando aplicação...")

    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(main())