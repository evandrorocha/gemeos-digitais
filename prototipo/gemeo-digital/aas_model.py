"""
Modelo de Casca Administrativa de Ativo (Asset Administration Shell - AAS)
Implementado com o SDK oficial Eclipse BaSyx (basyx-python-sdk) para garantir
serializacao compativel com o metamodelo AAS v3 e com submodel repositories
reais do ecossistema BaSyx, em conformidade com as normas ISO/IEC 30173 e ISO 23247.

Inclui o submodelo SpatialContext, que ancora o ativo a um elemento geometrico
de um modelo BIM/IFC (ISO 16739) por GlobalId, ligando a camada semantica (AAS)
a camada espacial (BIM) do ativo fisico.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List
import os

from basyx.aas import model
from basyx.aas.adapter.json import object_store_to_json
import json

_MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
_IFC_ELEMENT_MAP_PATH = os.path.join(_MODELS_DIR, "ifc_element_map.json")


def _semantic_id(uri: str) -> model.ExternalReference:
    """Cria uma referencia semantica externa (GlobalReference) para um submodelo/elemento."""
    return model.ExternalReference((model.Key(model.KeyTypes.GLOBAL_REFERENCE, uri),))


def _load_ifc_element_map() -> Dict[str, Any]:
    """Le o mapa tag OPC UA -> elemento IFC gerado por models/build_ifc_model.py.
    Retorna {} se o modelo IFC ainda nao foi gerado (o submodelo SpatialContext
    fica com valores vazios em vez de falhar a inicializacao do AAS)."""
    try:
        with open(_IFC_ELEMENT_MAP_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


class AssetAdministrationShell:
    """
    Representacao do AAS (Asset Administration Shell) da esteira Sorting by Height,
    construida com objetos nativos do basyx-python-sdk (model.AssetAdministrationShell,
    model.Submodel, model.Property, ...). Mantem a mesma interface publica usada pelo
    restante do Gemeo Digital: update_from_telemetry(), to_basyx_dict(), to_json_string().
    """

    def __init__(self, asset_id: str = "urn:ufrj:lps:digitaltwin:sorting_by_height:001"):
        self.asset_id = asset_id
        self.id_short = "AAS_SortingByHeight_Conveyor"
        self.description = "Gemeo Digital de Controle Supervisorio e Diagnostico da Esteira de Separacao de Caixas - LPS/UFRJ"

        # ---------------------------------------------------------------
        # Submodelo 1: Identificacao e Dados Tecnicos
        # ---------------------------------------------------------------
        self._prop_manufacturer = model.Property("Manufacturer", str, "Factory I/O RealGames & CODESYS GmbH")
        self._prop_designation = model.Property("ProductDesignation", str, "Sorting by Height Chain Transfer Line")
        self._prop_serial = model.Property("SerialNumber", str, "FIO-SBH-2026-X64")
        self._prop_standard = model.Property("GoverningStandard", str, "ISO/IEC 30173:2025, ISO 23247 & ISO 16739 (IFC)")
        self._prop_runtime = model.Property("ControllerRuntime", str, "CODESYS Control Win V3 x64 (v3.5.22.10)")
        self._prop_protocol = model.Property("Protocol", str, "OPC UA (IEC 62541)")
        self._prop_endpoint = model.Property("EndpointUrl", str, "opc.tcp://127.0.0.1:4840")

        self.submodel_identification = model.Submodel(
            id_=f"{asset_id}:sm:technical_identification",
            id_short="TechnicalIdentification",
            semantic_id=_semantic_id("https://admin-shell.io/sandbox/id/TechnicalData/1/0"),
            submodel_element=[
                self._prop_manufacturer, self._prop_designation, self._prop_serial,
                self._prop_standard, self._prop_runtime, self._prop_protocol, self._prop_endpoint,
            ],
        )

        # ---------------------------------------------------------------
        # Submodelo 2: Dados Operacionais em Tempo Real
        # ---------------------------------------------------------------
        self._prop_entry = model.Property("ConveyorEntry_Active", bool, False)
        self._prop_left = model.Property("ConveyorLeft_Active", bool, False)
        self._prop_right = model.Property("ConveyorRight_Active", bool, False)
        self._prop_transfer_l = model.Property("TransferLeft_Active", bool, False)
        self._prop_transfer_r = model.Property("TransferRight_Active", bool, False)
        self._prop_pallet_sensor = model.Property("PalletSensor_State", bool, False)
        self._prop_high_sensor = model.Property("HighSensor_State", bool, False)
        self._prop_loaded = model.Property("Loaded_State", bool, False)
        self._prop_boxes_total = model.Property("BoxesSortedTotal", int, 0)
        self._prop_last_update = model.Property("LastUpdateTimestamp", str, datetime.now(timezone.utc).isoformat())

        self.submodel_operational_data = model.Submodel(
            id_=f"{asset_id}:sm:operational_data",
            id_short="OperationalData",
            semantic_id=_semantic_id("https://admin-shell.io/sandbox/id/OperationalData/1/0"),
            submodel_element=[
                self._prop_entry, self._prop_left, self._prop_right,
                self._prop_transfer_l, self._prop_transfer_r,
                self._prop_pallet_sensor, self._prop_high_sensor, self._prop_loaded,
                self._prop_boxes_total, self._prop_last_update,
            ],
        )

        # ---------------------------------------------------------------
        # Submodelo 3: Monitoramento de Saude e Diagnostico
        # ---------------------------------------------------------------
        self._prop_health_status = model.Property("OverallHealthStatus", str, "HEALTHY")
        self._prop_anomalies_count = model.Property("ActiveAnomaliesCount", int, 0)
        self._prop_estop = model.Property("EmergencyStopEngaged", bool, False)
        self._prop_last_incident = model.Property("LastIncidentTimestamp", str, "")

        self._list_active_places = model.SubmodelElementList(
            id_short="PetriNetActivePlaces",
            type_value_list_element=model.Property,
            value_type_list_element=str,
            value=[model.Property(None, str, "p1")],
        )
        self._list_active_anomalies = model.SubmodelElementList(
            id_short="ActiveAnomaliesList",
            type_value_list_element=model.SubmodelElementCollection,
            value=[],
        )

        self.submodel_health_monitoring = model.Submodel(
            id_=f"{asset_id}:sm:health_and_diagnostics",
            id_short="HealthAndDiagnostics",
            semantic_id=_semantic_id("https://admin-shell.io/sandbox/id/ConditionMonitoring/1/0"),
            submodel_element=[
                self._prop_health_status, self._prop_anomalies_count,
                self._prop_estop, self._prop_last_incident,
                self._list_active_places, self._list_active_anomalies,
            ],
        )

        # ---------------------------------------------------------------
        # Submodelo 4: Contexto Espacial / Vinculo BIM-IFC (ISO 16739)
        # Ancora o ativo a elementos geometricos reais do modelo IFC gerado por
        # models/build_ifc_model.py (models/sorting_by_height.ifc). Os valores
        # abaixo vem do mapa tag->GlobalId gravado junto com o arquivo IFC, e
        # nao sao mais inventados: se o modelo IFC nao existir, os campos ficam
        # vazios em vez de apontar para um GUID que nao existe em lugar nenhum.
        # "conveyorEntry" eh usado como elemento primario/ancora do ativo; os
        # demais elementos ficam listados em IfcElementMap para permitir que um
        # visualizador BIM (ex.: ifc_viewer.py, via Plotly) destaque o elemento
        # certo a partir do estado ao vivo do AAS.
        # ---------------------------------------------------------------
        ifc_map = _load_ifc_element_map()
        primary = ifc_map.get("conveyorEntry", {})

        self._prop_ifc_file = model.Property(
            "IfcFilePath", str, "models/sorting_by_height.ifc" if ifc_map else ""
        )
        self._prop_ifc_schema = model.Property("IfcSchemaVersion", str, "IFC4")
        self._prop_ifc_guid = model.Property("IfcGlobalId", str, primary.get("ifc_global_id", ""))
        self._prop_ifc_element_type = model.Property("IfcElementType", str, primary.get("ifc_class", ""))
        self._prop_building_storey = model.Property("BuildingStorey", str, "Terreo - Celula de Triagem")
        pos = primary.get("position_m", {})
        self._prop_pos_x = model.Property("PositionX_m", float, float(pos.get("x", 0.0)))
        self._prop_pos_y = model.Property("PositionY_m", float, float(pos.get("y", 0.0)))
        self._prop_pos_z = model.Property("PositionZ_m", float, float(pos.get("z", 0.0)))

        self._list_ifc_element_map = model.SubmodelElementList(
            id_short="IfcElementMap",
            type_value_list_element=model.SubmodelElementCollection,
            value=[
                model.SubmodelElementCollection(id_short=None, value=[
                    model.Property("Tag", str, tag),
                    model.Property("IfcGlobalId", str, entry.get("ifc_global_id", "")),
                    model.Property("IfcClass", str, entry.get("ifc_class", "")),
                    model.Property("ObjectType", str, entry.get("object_type", "")),
                    model.Property("Name", str, entry.get("name", "")),
                ])
                for tag, entry in ifc_map.items()
            ],
        )

        self.submodel_spatial_context = model.Submodel(
            id_=f"{asset_id}:sm:spatial_context",
            id_short="SpatialContext",
            semantic_id=_semantic_id("urn:ufrj:lps:digitaltwin:semantic:spatial_context_ifc:1/0"),
            submodel_element=[
                self._prop_ifc_file, self._prop_ifc_schema, self._prop_ifc_guid,
                self._prop_ifc_element_type, self._prop_building_storey,
                self._prop_pos_x, self._prop_pos_y, self._prop_pos_z,
                self._list_ifc_element_map,
            ],
        )

        self._submodels: List[model.Submodel] = [
            self.submodel_identification,
            self.submodel_operational_data,
            self.submodel_health_monitoring,
            self.submodel_spatial_context,
        ]

        self.shell = model.AssetAdministrationShell(
            asset_information=model.AssetInformation(
                asset_kind=model.AssetKind.INSTANCE,
                global_asset_id=asset_id,
            ),
            id_=f"{asset_id}:aas",
            id_short=self.id_short,
            submodel={model.ModelReference.from_referable(sm) for sm in self._submodels},
        )

    def update_from_telemetry(self, tags: Dict[str, Any], petri_status: Dict[str, Any]):
        """Atualiza os submodelos do AAS com dados da telemetria e da Rede de Petri."""
        now_iso = datetime.now(timezone.utc).isoformat()

        self._prop_entry.value = bool(tags.get("conveyorEntry", False))
        self._prop_left.value = bool(tags.get("conveyorLeft", False))
        self._prop_right.value = bool(tags.get("conveyorRight", False))
        self._prop_transfer_l.value = bool(tags.get("transferLeft", False))
        self._prop_transfer_r.value = bool(tags.get("transferRight", False))
        self._prop_pallet_sensor.value = bool(tags.get("palletSensor", False))
        self._prop_high_sensor.value = bool(tags.get("highSensor", False))
        self._prop_loaded.value = bool(tags.get("loaded", False))
        self._prop_boxes_total.value = int(tags.get("contador", 0))
        self._prop_last_update.value = now_iso

        health_status = petri_status.get("health_status", "HEALTHY")
        active_places = petri_status.get("active_places") or ["p1"]
        active_anomalies = petri_status.get("active_anomalies", [])

        self._prop_health_status.value = health_status
        self._prop_anomalies_count.value = len(active_anomalies)
        self._prop_estop.value = (health_status == "CRITICAL_FAULT")

        if active_anomalies and not self._prop_last_incident.value:
            self._prop_last_incident.value = now_iso
        elif not active_anomalies:
            self._prop_last_incident.value = ""

        self._list_active_places.value.clear()
        for place in active_places:
            self._list_active_places.value.add(model.Property(None, str, place))

        self._list_active_anomalies.value.clear()
        for anomaly in active_anomalies:
            self._list_active_anomalies.value.add(model.SubmodelElementCollection(
                id_short=None,
                value=[
                    model.Property("AnomalyId", str, str(anomaly.get("anomaly_id", ""))),
                    model.Property("AnomalyType", str, str(anomaly.get("anomaly_type", ""))),
                    model.Property("Severity", str, str(anomaly.get("severity", ""))),
                    model.Property("Component", str, str(anomaly.get("component", ""))),
                    model.Property("Message", str, str(anomaly.get("message", ""))),
                    model.Property("TimestampIso", str, str(anomaly.get("timestamp_iso", ""))),
                ],
            ))

    def to_basyx_dict(self) -> Dict[str, Any]:
        """Serializa o Environment completo (Shell + Submodelos) no formato oficial
        do metamodelo AAS v3, via serializador do basyx-python-sdk."""
        store = model.DictIdentifiableStore([self.shell, *self._submodels])
        return json.loads(object_store_to_json(store))

    def to_json_string(self, indent: int = 2) -> str:
        """Gera o arquivo JSON padronizado do AAS (compativel com BaSyx Submodel Repository)."""
        return json.dumps(self.to_basyx_dict(), indent=indent, ensure_ascii=False)
