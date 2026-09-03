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

Cada elemento eh montado como um pequeno conjunto de solidos primitivos (pernas,
leito, roletes, cabecotes de sensor) em vez de um unico bloco retangular -- o
suficiente para ser reconhecivel como esteira/sensor/mesa de transferencia num
visualizador 3D, sem exigir um software de autoria CAD.

Coordenadas: aproximadas/nominais, estimadas a partir do layout tipico da cena
"Sorting by Height - Basic" do Factory I/O (nao medidas via laser scan da cena
real). Servem para visualizacao e para validar o pipeline BIM-AAS; se a planta
fisica for remontada ou a cena for outra, ajuste o dicionario ELEMENTS abaixo.

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

# tag OPC UA -> (classe IFC, ObjectType, nome, posicao (x,y,z) em metros,
#                tamanho (x,y,z) em metros, estilo de geometria)
# Posicao = canto inferior/origem local do elemento (nao o centro).
ELEMENTS = {
    "conveyorEntry": (
        "IfcTransportElement", "Conveyor Segment", "Esteira de Entrada",
        (0.0, 0.0, 0.0), (2.0, 0.3, 0.3), "conveyor",
    ),
    "palletSensor": (
        "IfcSensor", "Optical Presence Sensor", "Sensor de Presenca",
        (0.2, 0.10, 0.30), (0.05, 0.10, 0.05), "presence_sensor",
    ),
    "highSensor": (
        "IfcSensor", "Optical Height Sensor", "Sensor de Altura",
        (1.0, -0.05, 0.60), (0.05, 0.40, 0.05), "height_gate",
    ),
    "transferTable": (
        "IfcTransportElement", "Chain Transfer Table", "Mesa de Transferencia",
        (2.0, -0.5, 0.0), (0.6, 1.3, 0.3), "transfer_table",
    ),
    "conveyorLeft": (
        "IfcTransportElement", "Conveyor Segment", "Esteira de Saida - Baixa",
        (2.6, -1.5, 0.0), (1.5, 0.3, 0.3), "conveyor",
    ),
    "conveyorRight": (
        "IfcTransportElement", "Conveyor Segment", "Esteira de Saida - Alta",
        (2.6, 1.0, 0.0), (1.5, 0.3, 0.3), "conveyor",
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


def _presence_sensor_solids(builder, length, width, height):
    """Sensor optico compacto: corpo + lente cilindrica voltada para a esteira."""
    solids = [builder.block(position=(0.0, 0.0, 0.0), x_length=length, y_length=width, z_length=height)]
    lens_radius = min(height, width) * 0.35
    lens_circle = builder.circle(radius=lens_radius)
    solids.append(builder.extrude(
        lens_circle, magnitude=0.02, position=(length / 2, width, height / 2),
        position_z_axis=(0.0, 1.0, 0.0), position_x_axis=(1.0, 0.0, 0.0),
    ))
    return solids


def _height_gate_solids(builder, length, width, height):
    """Sensor de altura como barreira optica: 2 cabecotes (emissor/receptor) + barra fina."""
    head = max(height, 0.03)
    return [
        builder.block(position=(0.0, 0.0, 0.0), x_length=length, y_length=head, z_length=head),
        builder.block(position=(0.0, width - head, 0.0), x_length=length, y_length=head, z_length=head),
        builder.block(
            position=(0.0, head * 0.3, height * 0.3),
            x_length=length, y_length=max(width - head * 0.6, 0.01), z_length=max(height * 0.4, 0.01),
        ),
    ]


SHAPE_BUILDERS = {
    "conveyor": _conveyor_solids,
    "transfer_table": _transfer_table_solids,
    "presence_sensor": _presence_sensor_solids,
    "height_gate": _height_gate_solids,
}


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

    for tag, (ifc_class, object_type, name, position, size, shape_kind) in ELEMENTS.items():
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

        matrix = np.eye(4)
        matrix[:3, 3] = position
        ifcopenshell.api.run("geometry.edit_object_placement", ifc_file, product=element, matrix=matrix)

        element_map[tag] = {
            "ifc_global_id": element.GlobalId,
            "ifc_class": ifc_class,
            "object_type": object_type,
            "name": name,
            "position_m": {"x": position[0], "y": position[1], "z": position[2]},
            "size_m": {"x": size[0], "y": size[1], "z": size[2]},
        }

    ifc_file.write(IFC_OUTPUT_PATH)
    with open(MAP_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(element_map, f, indent=2, ensure_ascii=False)

    print(f"IFC gerado: {IFC_OUTPUT_PATH}")
    print(f"Mapa de elementos gerado: {MAP_OUTPUT_PATH}")


if __name__ == "__main__":
    build()
