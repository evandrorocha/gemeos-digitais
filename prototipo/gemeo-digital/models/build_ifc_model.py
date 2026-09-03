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

# tag OPC UA -> (classe IFC, ObjectType, nome, posicao (x,y,z) em metros, tamanho (x,y,z) em metros)
# Posicao = canto inferior do bloco (nao o centro).
ELEMENTS = {
    "conveyorEntry": (
        "IfcTransportElement", "Conveyor Segment", "Esteira de Entrada",
        (0.0, 0.0, 0.0), (2.0, 0.3, 0.3),
    ),
    "palletSensor": (
        "IfcSensor", "Optical Presence Sensor", "Sensor de Presenca",
        (0.2, 0.10, 0.30), (0.05, 0.10, 0.05),
    ),
    "highSensor": (
        "IfcSensor", "Optical Height Sensor", "Sensor de Altura",
        (1.0, -0.05, 0.60), (0.05, 0.40, 0.05),
    ),
    "transferTable": (
        "IfcTransportElement", "Chain Transfer Table", "Mesa de Transferencia",
        (2.0, -0.5, 0.0), (0.6, 1.3, 0.3),
    ),
    "conveyorLeft": (
        "IfcTransportElement", "Conveyor Segment", "Esteira de Saida - Baixa",
        (2.6, -1.5, 0.0), (1.5, 0.3, 0.3),
    ),
    "conveyorRight": (
        "IfcTransportElement", "Conveyor Segment", "Esteira de Saida - Alta",
        (2.6, 1.0, 0.0), (1.5, 0.3, 0.3),
    ),
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

    for tag, (ifc_class, object_type, name, position, size) in ELEMENTS.items():
        element = ifcopenshell.api.run(
            "root.create_entity", ifc_file, ifc_class=ifc_class,
            predefined_type="USERDEFINED", name=name,
        )
        element.ObjectType = object_type
        ifcopenshell.api.run("spatial.assign_container", ifc_file, relating_structure=storey, products=[element])

        solid = builder.block(position=(0.0, 0.0, 0.0), x_length=size[0], y_length=size[1], z_length=size[2])
        representation = builder.get_representation(body_context, solid)
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
