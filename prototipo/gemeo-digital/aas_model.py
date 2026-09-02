"""
Modelo de Casca Administrativa de Ativo (Asset Administration Shell - AAS)
Implementa a representação padronizada do Gêmeo Digital no padrão da Indústria 4.0 / Eclipse BaSyx
e em conformidade com as normas ISO/IEC 30173 e ISO 23247.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import json
from typing import Dict, Any, List, Optional


class AssetAdministrationShell:
    """
    Representação oficial do AAS (Asset Administration Shell) para a esteira Sorting by Height.
    Organizado em submodelos padronizados.
    """

    def __init__(self, asset_id: str = "urn:ufrj:lps:digitaltwin:sorting_by_height:001"):
        self.id_short = "AAS_SortingByHeight_Conveyor"
        self.asset_id = asset_id
        self.asset_kind = "Type" # ou "Instance"
        self.description = "Gêmeo Digital de Controle Supervisório e Diagnóstico da Esteira de Separação de Caixas - LPS/UFRJ"

        # ---------------------------------------------------------------------
        # Submodelo 1: Identificação e Dados Técnicos (Identification / TechnicalData)
        # ---------------------------------------------------------------------
        self.submodel_identification = {
            "idShort": "TechnicalIdentification",
            "semanticId": "https://admin-shell.io/sandbox/id/TechnicalData/1/0",
            "elements": {
                "Manufacturer": "Factory I/O RealGames & CODESYS GmbH",
                "ProductDesignation": "Sorting by Height Chain Transfer Line",
                "SerialNumber": "FIO-SBH-2026-X64",
                "GoverningStandard": "ISO/IEC 30173:2025 (Digital Twin Governance) & ISO 23247",
                "ControllerRuntime": "CODESYS Control Win V3 x64 (v3.5.22.10)",
                "Protocol": "OPC UA (IEC 62541)",
                "EndpointUrl": "opc.tcp://127.0.0.1:4840"
            }
        }

        # ---------------------------------------------------------------------
        # Submodelo 2: Dados Operacionais em Tempo Real (OperationalData)
        # ---------------------------------------------------------------------
        self.submodel_operational_data = {
            "idShort": "OperationalData",
            "semanticId": "https://admin-shell.io/sandbox/id/OperationalData/1/0",
            "elements": {
                "ConveyorEntry_Active": False,
                "ConveyorLeft_Active": False,
                "ConveyorRight_Active": False,
                "TransferLeft_Active": False,
                "TransferRight_Active": False,
                "PalletSensor_State": False,
                "HighSensor_State": False,
                "Loaded_State": False,
                "BoxesSortedTotal": 0,
                "LastUpdateTimestamp": datetime.now(timezone.utc).isoformat()
            }
        }

        # ---------------------------------------------------------------------
        # Submodelo 3: Monitoramento de Saúde e Diagnóstico (HealthMonitoring)
        # ---------------------------------------------------------------------
        self.submodel_health_monitoring = {
            "idShort": "HealthAndDiagnostics",
            "semanticId": "https://admin-shell.io/sandbox/id/ConditionMonitoring/1/0",
            "elements": {
                "OverallHealthStatus": "HEALTHY", # "HEALTHY", "DEGRADED", "CRITICAL_FAULT"
                "PetriNetActivePlaces": ["p1"],
                "ActiveAnomaliesCount": 0,
                "ActiveAnomaliesList": [],
                "EmergencyStopEngaged": False,
                "LastIncidentTimestamp": None
            }
        }

    def update_from_telemetry(self, tags: Dict[str, Any], petri_status: Dict[str, Any]):
        """Atualiza os submodelos do AAS com dados da telemetria e da Rede de Petri."""
        now_iso = datetime.now(timezone.utc).isoformat()

        # Atualiza Dados Operacionais
        op = self.submodel_operational_data["elements"]
        op["ConveyorEntry_Active"] = bool(tags.get("conveyorEntry", False))
        op["ConveyorLeft_Active"] = bool(tags.get("conveyorLeft", False))
        op["ConveyorRight_Active"] = bool(tags.get("conveyorRight", False))
        op["TransferLeft_Active"] = bool(tags.get("transferLeft", False))
        op["TransferRight_Active"] = bool(tags.get("transferRight", False))
        op["PalletSensor_State"] = bool(tags.get("palletSensor", False))
        op["HighSensor_State"] = bool(tags.get("highSensor", False))
        op["Loaded_State"] = bool(tags.get("loaded", False))
        op["BoxesSortedTotal"] = int(tags.get("contador", 0))
        op["LastUpdateTimestamp"] = now_iso

        # Atualiza Monitoramento de Saúde
        health = self.submodel_health_monitoring["elements"]
        health["OverallHealthStatus"] = petri_status.get("health_status", "HEALTHY")
        health["PetriNetActivePlaces"] = petri_status.get("active_places", ["p1"])
        active_anom = petri_status.get("active_anomalies", [])
        health["ActiveAnomaliesCount"] = len(active_anom)
        health["ActiveAnomaliesList"] = active_anom
        health["EmergencyStopEngaged"] = (health["OverallHealthStatus"] == "CRITICAL_FAULT")

        if active_anom and not health["LastIncidentTimestamp"]:
            health["LastIncidentTimestamp"] = now_iso
        elif not active_anom:
            health["LastIncidentTimestamp"] = None

    def to_basyx_dict(self) -> Dict[str, Any]:
        """Serializa o AAS no formato padrão JSON do Eclipse BaSyx."""
        return {
            "idShort": self.id_short,
            "identification": {
                "id": self.asset_id,
                "idType": "IRI"
            },
            "assetInformation": {
                "assetKind": self.asset_kind,
                "globalAssetId": self.asset_id
            },
            "submodels": [
                self.submodel_identification,
                self.submodel_operational_data,
                self.submodel_health_monitoring
            ]
        }

    def to_json_string(self, indent: int = 2) -> str:
        """Gera o arquivo JSON padronizado do AAS."""
        return json.dumps(self.to_basyx_dict(), indent=indent, ensure_ascii=False)
