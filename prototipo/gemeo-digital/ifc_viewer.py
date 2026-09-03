"""
Visualizador 3D do Gemeo Digital baseado no modelo BIM/IFC (models/sorting_by_height.ifc).
Le a geometria real dos elementos via ifcopenshell (uma unica vez, com cache) e monta uma
cena Plotly (Mesh3d) que reage ao estado ao vivo da planta: cada elemento fisico eh colorido
de acordo com sua tag OPC UA sanitizada e com as anomalias ativas na Rede de Petri.
"""

import json
import os
from functools import lru_cache
from typing import Any, Dict, List

try:
    import ifcopenshell
    import ifcopenshell.geom
    HAS_IFCOPENSHELL = True
except ImportError:
    HAS_IFCOPENSHELL = False

import numpy as np
import plotly.graph_objects as go

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
IFC_PATH = os.path.join(MODELS_DIR, "sorting_by_height.ifc")
MAP_PATH = os.path.join(MODELS_DIR, "ifc_element_map.json")

COLOR_IDLE = "#4b5563"    # cinza -- parado / sem deteccao
COLOR_ACTIVE = "#10b981"  # verde -- esteira em movimento / sensor detectando
COLOR_ALERT = "#ef4444"   # vermelho -- componente citado em anomalia ativa
COLOR_STATIC = "#6b7280"  # cinza claro -- elementos sem tag booleana propria (mesa)

# Palavras-chave usadas para casar o campo 'component' de uma AnomalyReport
# (ex: "palletSensor (Sensor de Entrada)") com o elemento IFC correspondente.
ALERT_KEYWORDS: Dict[str, List[str]] = {
    "transferTable": ["transferLeft", "transferRight", "Mesa de Desvio", "Mesa de Transferencia"],
}


def ifc_model_available() -> bool:
    return HAS_IFCOPENSHELL and os.path.isfile(IFC_PATH) and os.path.isfile(MAP_PATH)


def _load_element_map() -> Dict[str, Any]:
    with open(MAP_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_geometry() -> Dict[str, Dict[str, Any]]:
    """Abre o IFC real e triangula cada elemento uma unica vez (a geometria eh
    estatica; apenas a cor muda a cada atualizacao do dashboard)."""
    element_map = _load_element_map()
    guid_to_tag = {v["ifc_global_id"]: tag for tag, v in element_map.items()}

    ifc_file = ifcopenshell.open(IFC_PATH)
    settings = ifcopenshell.geom.settings()

    geometry_by_tag: Dict[str, Dict[str, Any]] = {}
    for element in ifc_file.by_type("IfcElement"):
        tag = guid_to_tag.get(element.GlobalId)
        if not tag:
            continue
        shape = ifcopenshell.geom.create_shape(settings, element)
        verts = np.array(shape.geometry.verts, dtype=float).reshape(-1, 3)
        faces = np.array(shape.geometry.faces, dtype=int).reshape(-1, 3)
        geometry_by_tag[tag] = {
            "x": verts[:, 0], "y": verts[:, 1], "z": verts[:, 2],
            "i": faces[:, 0], "j": faces[:, 1], "k": faces[:, 2],
            "name": element_map[tag]["name"],
        }
    return geometry_by_tag


def _color_for_tag(tag: str, tags_state: Dict[str, Any], alert_components: List[str]) -> str:
    keywords = ALERT_KEYWORDS.get(tag, [tag])
    if any(kw in comp for kw in keywords for comp in alert_components):
        return COLOR_ALERT
    if tag == "transferTable":
        active = bool(tags_state.get("transferLeft")) or bool(tags_state.get("transferRight"))
        return COLOR_ACTIVE if active else COLOR_IDLE
    if tag in tags_state:
        return COLOR_ACTIVE if tags_state.get(tag) else COLOR_IDLE
    return COLOR_STATIC


def build_3d_figure(tags_state: Dict[str, Any], petri_status: Dict[str, Any]) -> go.Figure:
    """Monta a cena 3D do Gemeo Digital a partir da geometria IFC real, colorindo
    cada elemento fisico de acordo com o estado ao vivo da planta."""
    geometry_by_tag = _load_geometry()
    alert_components = [a.get("component", "") for a in petri_status.get("active_anomalies", [])]

    meshes = []
    for tag, geo in geometry_by_tag.items():
        color = _color_for_tag(tag, tags_state, alert_components)
        meshes.append(go.Mesh3d(
            x=geo["x"], y=geo["y"], z=geo["z"],
            i=geo["i"], j=geo["j"], k=geo["k"],
            color=color, opacity=1.0, flatshading=True,
            name=geo["name"], hovertext=geo["name"], hoverinfo="text",
            lighting=dict(ambient=0.55, diffuse=0.6, specular=0.15, roughness=0.9),
            lightposition=dict(x=2, y=2, z=4),
        ))

    fig = go.Figure(data=meshes)
    fig.update_layout(
        scene=dict(
            xaxis=dict(title="X (m)", backgroundcolor="#0e1117", gridcolor="#374151", color="#9ca3af"),
            yaxis=dict(title="Y (m)", backgroundcolor="#0e1117", gridcolor="#374151", color="#9ca3af"),
            zaxis=dict(title="Z (m)", backgroundcolor="#0e1117", gridcolor="#374151", color="#9ca3af"),
            aspectmode="data",
            camera=dict(eye=dict(x=1.6, y=-1.6, z=1.2)),
        ),
        paper_bgcolor="#0e1117",
        margin=dict(l=0, r=0, t=30, b=0),
        showlegend=False,
        height=520,
    )
    return fig
