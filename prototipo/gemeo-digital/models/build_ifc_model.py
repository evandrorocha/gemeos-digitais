"""
Gera o modelo BIM/IFC4 de referencia da linha Sorting by Height (ISO 16739).

Este script eh a fonte de verdade da geometria: roda-se uma vez (ou sempre que a
disposicao fisica da linha mudar) e produz dois artefatos versionados:
  - sorting_by_height.ifc      -> arquivo IFC4 (STEP) com a hierarquia espacial
                                   completa (Project > Site > Building > Storey)
                                   e um elemento por componente fisico monitorado.
  - ifc_element_map.json       -> mapa tag OPC UA -> GlobalId/classe/posicao IFC,
                                   consumido pelo aas_model.py (submodelo
                                   SpatialContext) e pelo ifc_viewer.py.

Topologia e posicoes: extraidas do arquivo real da cena instalada localmente
("Sorting by Height (Basic).factoryio", formato XML). Alguns fatos vieram
diretamente do arquivo:
  - highSensor e palletSensor NAO sao dois dispositivos separados: sao dois
    feixes (beam5 "High sensor", beam7 "Pallet sensor") da MESMA cortina de
    luz (LightCurtainEmitter/Receiver), ancorada logo antes da mesa de
    transferencia.
  - atLeftEntry/atLeftExit/atRightEntry/atRightExit sao 4 pares sensor
    retrorreflexivo + espelho, um em cada extremidade das duas esteiras de
    saida -- ausentes nas versoes anteriores deste script.
  - A topologia real: a esteira de entrada (RollerConveyor4M, 4m) alimenta a
    mesa de transferencia (ChainTransfer) ao longo do eixo X; as duas esteiras
    de saida (RollerConveyor4M, 4m cada) saem perpendicularmente, ao longo do
    eixo Y, uma para cada lado.
A escala de posicao (0.2 m por unidade da cena) foi inferida comparando a
distancia entre objetos adjacentes com o comprimento real conhecido dos
RollerConveyor4M (4 m) -- nao eh um valor documentado oficialmente, mas bate
de forma consistente em varias medidas independentes da cena (ver conversas
do projeto). Dimensoes que a cena NAO revela (largura das esteiras, tamanho
exato da mesa) continuam nominais/estimadas.

Nota de modelagem: o IFC4 (ISO 16739-1:2018) eh um schema orientado a AEC e nao
possui classes dedicadas para esteiras/sensores industriais (isso so aparece em
IFC4.3, ainda pouco suportado por ferramentas). Por isso os elementos abaixo usam
IfcTransportElement / IfcSensor com PredefinedType=USERDEFINED + ObjectType
descritivo, que eh o mecanismo padrao do schema para categorias fora do enum.
"""

import json
import os

import numpy as np
import ifcopenshell
import ifcopenshell.api
from ifcopenshell.util.shape_builder import ShapeBuilder

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
IFC_OUTPUT_PATH = os.path.join(OUTPUT_DIR, "sorting_by_height.ifc")
MAP_OUTPUT_PATH = os.path.join(OUTPUT_DIR, "ifc_element_map.json")

# tag OPC UA -> (classe IFC, ObjectType, nome, centro (x,y) em metros,
#                tamanho (comprimento, largura, altura) em metros,
#                estilo de geometria, rotacao em graus ao redor do eixo vertical,
#                elevacao da base em metros)
# Centro = centro do elemento no plano XY (nao um canto); a base (Z) fica no
# chao (0.0) exceto para os feixes da cortina de luz, que ficam elevados.
ELEMENTS = {
    "transferTable": (
        "IfcTransportElement", "Chain Transfer Table", "Mesa de Transferencia",
        (0.0, 0.0), (1.6, 2.0, 0.3), "transfer_table", 0.0, 0.0,
    ),
    "conveyorEntry": (
        "IfcTransportElement", "Conveyor Segment (4M)", "Esteira de Entrada",
        (4.0, 0.0), (4.0, 0.6, 0.3), "conveyor", 0.0, 0.0,
    ),
    "conveyorLeft": (
        "IfcTransportElement", "Conveyor Segment (4M)", "Esteira de Saida - Baixa",
        (0.0, -4.0), (4.0, 0.6, 0.3), "conveyor", 90.0, 0.0,
    ),
    "conveyorRight": (
        "IfcTransportElement", "Conveyor Segment (4M)", "Esteira de Saida - Alta",
        (0.0, 4.0), (4.0, 0.6, 0.3), "conveyor", 90.0, 0.0,
    ),
    # highSensor e palletSensor: dois feixes da mesma cortina de luz, ancorada
    # a meio caminho entre a esteira de entrada e a mesa de transferencia.
    # highSensor = feixe alto (beam5); palletSensor = feixe baixo, rente a
    # esteira, dispara para qualquer caixa (beam7).
    "highSensor": (
        "IfcSensor", "Light Curtain - High Beam", "Cortina Optica - Feixe Alto",
        (1.0, 0.0), (0.06, 2.0, 0.06), "height_gate", 0.0, 0.45,
    ),
    "palletSensor": (
        "IfcSensor", "Light Curtain - Pallet Beam", "Cortina Optica - Feixe de Presenca",
        (1.0, 0.0), (0.06, 2.0, 0.06), "height_gate", 0.0, 0.12,
    ),
    "atLeftEntry": (
        "IfcSensor", "Retroreflective Photoelectric Sensor", "Sensor - Entrada Esquerda",
        (0.0, -0.8), (1.6, 0.06, 0.08), "photobeam_pair", 0.0, 0.15,
    ),
    "atRightEntry": (
        "IfcSensor", "Retroreflective Photoelectric Sensor", "Sensor - Entrada Direita",
        (0.0, 0.8), (1.6, 0.06, 0.08), "photobeam_pair", 0.0, 0.15,
    ),
    "atLeftExit": (
        "IfcSensor", "Retroreflective Photoelectric Sensor", "Sensor - Saida Esquerda",
        (0.0, -5.2), (1.6, 0.06, 0.08), "photobeam_pair", 0.0, 0.15,
    ),
    "atRightExit": (
        "IfcSensor", "Retroreflective Photoelectric Sensor", "Sensor - Saida Direita",
        (0.0, 5.2), (1.6, 0.06, 0.08), "photobeam_pair", 0.0, 0.15,
    ),
}

# --- Parametros de estilo (pernas, leito, roletes, cabecotes de sensor) ---
LEG_SIZE = 0.04
LEG_HEIGHT = 0.45
FRAME_THICKNESS = 0.05
ROLLER_RADIUS = 0.045


def _legs(builder, length, width, leg_height=LEG_HEIGHT, inset=0.05, leg_size=LEG_SIZE):
    """4 pernas quadradas nos cantos, elevando o equipamento do chao."""
    xs = (inset, max(length - inset, inset))
    ys = (inset, max(width - inset, inset))
    return [
        builder.block(
            position=(x - leg_size / 2, y - leg_size / 2, 0.0),
            x_length=leg_size, y_length=leg_size, z_length=leg_height,
        )
        for x in xs for y in ys
    ]


def _roller(builder, x_center, width, z_center, radius=ROLLER_RADIUS):
    """Cilindro com eixo ao longo de Y (perpendicular ao sentido de deslocamento)."""
    circle = builder.circle(radius=radius)
    return builder.extrude(
        circle, magnitude=width, position=(x_center, 0.0, z_center),
        position_z_axis=(0.0, 1.0, 0.0), position_x_axis=(1.0, 0.0, 0.0),
    )


def _conveyor_solids(builder, length, width, height):
    """Esteira estilizada: pernas + leito + roletes nas duas extremidades."""
    solids = _legs(builder, length, width)
    bed_z = LEG_HEIGHT
    solids.append(builder.block(
        position=(0.0, 0.0, bed_z), x_length=length, y_length=width, z_length=FRAME_THICKNESS,
    ))
    roller_z = bed_z + FRAME_THICKNESS + ROLLER_RADIUS * 0.5
    for x in (ROLLER_RADIUS, max(length - ROLLER_RADIUS, ROLLER_RADIUS)):
        solids.append(_roller(builder, x, width, roller_z))
    return solids


def _transfer_table_solids(builder, length, width, height, n_slats=5):
    """Mesa de transferencia: pernas + leito + varias correntes/roletes transversais."""
    solids = _legs(builder, length, width)
    bed_z = LEG_HEIGHT
    solids.append(builder.block(
        position=(0.0, 0.0, bed_z), x_length=length, y_length=width, z_length=FRAME_THICKNESS,
    ))
    roller_z = bed_z + FRAME_THICKNESS + ROLLER_RADIUS * 0.3
    margin = ROLLER_RADIUS * 2
    for x in np.linspace(margin, max(length - margin, margin), n_slats):
        solids.append(_roller(builder, float(x), width, roller_z, radius=ROLLER_RADIUS * 0.6))
    return solids


def _height_gate_solids(builder, length, width, height):
    """Feixe da cortina optica como barreira: 2 cabecotes (emissor/receptor) + barra fina."""
    head = max(height, 0.03)
    return [
        builder.block(position=(0.0, 0.0, 0.0), x_length=length, y_length=head, z_length=head),
        builder.block(position=(0.0, width - head, 0.0), x_length=length, y_length=head, z_length=head),
        builder.block(
            position=(0.0, head * 0.3, height * 0.3),
            x_length=length, y_length=max(width - head * 0.6, 0.01), z_length=max(height * 0.4, 0.01),
        ),
    ]


def _photobeam_pair_solids(builder, length, width, height):
    """Par sensor retrorreflexivo + espelho: 2 corpos pequenos separados por 'length',
    com uma lente esferica no corpo do sensor voltada para o espelho."""
    box = max(width, 0.02)
    solids = [
        builder.block(position=(0.0, 0.0, 0.0), x_length=box, y_length=box, z_length=height),
        builder.block(position=(length - box, 0.0, 0.0), x_length=box, y_length=box, z_length=height),
    ]
    solids.append(builder.sphere(radius=box * 0.35, center=(box, box / 2, height / 2)))
    return solids


SHAPE_BUILDERS = {
    "conveyor": _conveyor_solids,
    "transfer_table": _transfer_table_solids,
    "height_gate": _height_gate_solids,
    "photobeam_pair": _photobeam_pair_solids,
}


def _placement_matrix(center_xy, length, width, angle_deg=0.0, base_z=0.0):
    """Matriz de posicionamento que roda o solido (construido com canto na
    origem local) ao redor do eixo vertical e centraliza seu footprint em
    center_xy, com a base elevada em base_z."""
    theta = np.radians(angle_deg)
    c, s = np.cos(theta), np.sin(theta)
    rotation = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
    local_center = np.array([length / 2.0, width / 2.0, 0.0])
    translation = np.array([center_xy[0], center_xy[1], base_z]) - rotation @ local_center

    matrix = np.eye(4)
    matrix[:3, :3] = rotation
    matrix[:3, 3] = translation
    return matrix


def build() -> None:
    ifc_file = ifcopenshell.api.run("project.create_file", version="IFC4")

    project = ifcopenshell.api.run(
        "root.create_entity", ifc_file, ifc_class="IfcProject",
        name="Gemeo Digital - Sorting by Height (LPS/UFRJ)",
    )
    # O padrao do ifcopenshell.api.unit.assign_unit() eh MILIMETROS; como as
    # coordenadas em ELEMENTS acima sao em METROS, METERS precisa ser forcado
    # aqui -- caso contrario a geometria fica gravada 1000x menor do que o
    # numero literal sugere.
    ifcopenshell.api.run(
        "unit.assign_unit", ifc_file,
        length={"is_metric": True, "raw": "METERS"},
    )

    model_context = ifcopenshell.api.run("context.add_context", ifc_file, context_type="Model")
    body_context = ifcopenshell.api.run(
        "context.add_context", ifc_file, context_type="Model",
        context_identifier="Body", target_view="MODEL_VIEW", parent=model_context,
    )

    site = ifcopenshell.api.run("root.create_entity", ifc_file, ifc_class="IfcSite", name="LPS - UFRJ")
    building = ifcopenshell.api.run("root.create_entity", ifc_file, ifc_class="IfcBuilding", name="Celula de Triagem")
    storey = ifcopenshell.api.run("root.create_entity", ifc_file, ifc_class="IfcBuildingStorey", name="Terreo")

    ifcopenshell.api.run("aggregate.assign_object", ifc_file, relating_object=project, products=[site])
    ifcopenshell.api.run("aggregate.assign_object", ifc_file, relating_object=site, products=[building])
    ifcopenshell.api.run("aggregate.assign_object", ifc_file, relating_object=building, products=[storey])

    builder = ShapeBuilder(ifc_file)
    element_map = {}

    for tag, (ifc_class, object_type, name, center_xy, size, shape_kind, angle_deg, base_z) in ELEMENTS.items():
        element = ifcopenshell.api.run(
            "root.create_entity", ifc_file, ifc_class=ifc_class,
            predefined_type="USERDEFINED", name=name,
        )
        element.ObjectType = object_type
        ifcopenshell.api.run("spatial.assign_container", ifc_file, relating_structure=storey, products=[element])

        shape_fn = SHAPE_BUILDERS[shape_kind]
        solids = shape_fn(builder, size[0], size[1], size[2])
        representation = builder.get_representation(body_context, solids)
        ifcopenshell.api.run("geometry.assign_representation", ifc_file, product=element, representation=representation)

        matrix = _placement_matrix(center_xy, size[0], size[1], angle_deg, base_z)
        ifcopenshell.api.run("geometry.edit_object_placement", ifc_file, product=element, matrix=matrix)

        element_map[tag] = {
            "ifc_global_id": element.GlobalId,
            "ifc_class": ifc_class,
            "object_type": object_type,
            "name": name,
            "center_m": {"x": center_xy[0], "y": center_xy[1]},
            "size_m": {"x": size[0], "y": size[1], "z": size[2]},
            "rotation_deg": angle_deg,
        }

    ifc_file.write(IFC_OUTPUT_PATH)
    with open(MAP_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(element_map, f, indent=2, ensure_ascii=False)

    print(f"IFC gerado: {IFC_OUTPUT_PATH}")
    print(f"Mapa de elementos gerado: {MAP_OUTPUT_PATH}")


if __name__ == "__main__":
    build()
