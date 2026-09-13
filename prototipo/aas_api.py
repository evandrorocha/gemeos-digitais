import asyncio
import base64
import threading
from contextlib import asynccontextmanager
from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import uvicorn


BASE_DIR = Path(__file__).resolve().parent
GEMEO_DIGITAL_DIR = BASE_DIR / "gemeo-digital"
if str(GEMEO_DIGITAL_DIR) not in sys.path:
    sys.path.insert(0, str(GEMEO_DIGITAL_DIR))

from opc_connector import DigitalTwinConnector  # type: ignore[import-not-found]


class DigitalTwinService:
    """Keeps the OPC UA connector and its event loop alive for the API."""

    def __init__(self):
        self.connector = DigitalTwinConnector()
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.connector.connect_and_subscribe())
        except Exception:
            # The AAS can still be served with its last/default values when the
            # physical OPC UA server is offline; the connector retries itself.
            self.connector.is_connected = False
            self.connector._monitor_task = self.loop.create_task(
                self.connector._periodic_monitor_loop()
            )
        self.loop.run_forever()

    def stop(self):
        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.digital_twin = DigitalTwinService()
    yield
    app.state.digital_twin.stop()

app = FastAPI(
    title="Sorting Line Digital Twin AAS API",
    description="Live AAS v3 REST Endpoints compliant with Eclipse BaSyx",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for cross-origin enterprise dashboards
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

def _connector() -> DigitalTwinConnector:
    return app.state.digital_twin.connector


@app.get("/", summary="List API entry points")
def api_root():
    """Provides a discoverable landing response for the API host."""
    return {
        "service": app.title,
        "status": "/health",
        "openapi": "/docs",
        "aas_environment": "/api/v3/aas",
        "shells": "/api/v3/shells",
        "submodels": "/api/v3/submodels",
        "aasx": "/api/v3/aasx",
    }


@app.get("/health", summary="Check API and OPC UA status")
def health():
    connector = _connector()
    return {"status": "ok", "opcua_connected": connector.is_connected}


@app.get("/api/v3/aas", summary="Fetch full live AAS JSON model")
def get_live_aas():
    """Returns the complete AAS Environment (shell and submodels)."""
    return _connector().aas.to_basyx_dict()


@app.get("/api/v3/description", summary="Describe the AAS API")
def api_description():
    """Minimal service description accepted by BaSyx infrastructure checks."""
    return {
        "profiles": [
            "https://industrialdigitaltwin.org/aas/API/aasx/v3",
            "https://industrialdigitaltwin.org/aas/API/aas/v3",
        ]
    }


def _environment():
    return _connector().aas.to_basyx_dict()


def _paged(items):
    """Build the paged response envelope used by BaSyx REST API v3."""
    return {"result": items, "paging_metadata": {}}


def _decode_identifier(identifier: str) -> str:
    """Accept raw IDs and the URL-safe base64 IDs used by the BaSyx GUI."""
    try:
        padding = "=" * (-len(identifier) % 4)
        decoded = base64.urlsafe_b64decode(identifier + padding).decode("utf-8")
        if decoded.startswith(("urn:", "http://", "https://")):
            return decoded
    except (ValueError, UnicodeDecodeError):
        pass
    return identifier


def _find_shell(aas_id: str):
    aas_id = _decode_identifier(aas_id)
    for shell in _environment().get("assetAdministrationShells", []):
        if shell.get("id") == aas_id:
            return shell
    raise HTTPException(status_code=404, detail="AAS shell not found")


def _find_submodel(submodel_id: str):
    submodel_id = _decode_identifier(submodel_id)
    for submodel in _environment().get("submodels", []):
        if submodel.get("id") == submodel_id:
            return submodel
    raise HTTPException(status_code=404, detail="Submodel not found")


@app.get("/api/v3/shells", summary="List AAS shells")
def list_shells():
    """AAS Repository API v3 compatible shell collection."""
    return _paged(_environment().get("assetAdministrationShells", []))


@app.get("/api/v3/shell-descriptors", summary="List AAS shell descriptors")
def list_shell_descriptors(request: Request):
    """AAS Registry-compatible descriptors for the live shell."""
    environment = _environment()
    api_base = str(request.base_url).rstrip("/")
    descriptors = []
    for shell in environment.get("assetAdministrationShells", []):
        descriptors.append({
            "id": shell["id"],
            "idShort": shell.get("idShort"),
            "globalAssetId": shell.get("assetInformation", {}).get("globalAssetId"),
            "endpoints": [{
                "interface": "AAS-3.0",
                "protocolInformation": {
                    "href": f"{api_base}/api/v3/shells/{shell['id']}"
                },
            }],
        })
    return _paged(descriptors)


@app.get("/api/v3/shell-descriptors/{aas_id}", summary="Fetch one AAS shell descriptor")
def get_shell_descriptor(aas_id: str, request: Request):
    """Returns one registry descriptor for the requested AAS."""
    shell = _find_shell(aas_id)
    api_base = str(request.base_url).rstrip("/")
    return {
        "id": shell["id"],
        "idShort": shell.get("idShort"),
        "globalAssetId": shell.get("assetInformation", {}).get("globalAssetId"),
        "endpoints": [{
            "interface": "AAS-3.0",
            "protocolInformation": {
                "href": f"{api_base}/api/v3/shells/{shell['id']}"
            },
        }],
    }


@app.get("/api/v3/submodel-descriptors", summary="List submodel descriptors")
def list_submodel_descriptors(request: Request):
    """Submodel Registry-compatible descriptors for the live submodels."""
    api_base = str(request.base_url).rstrip("/")
    descriptors = []
    for submodel in _environment().get("submodels", []):
        descriptors.append({
            "id": submodel["id"],
            "idShort": submodel.get("idShort"),
            "endpoints": [{
                "interface": "SUBMODEL-3.0",
                "protocolInformation": {
                    "href": f"{api_base}/api/v3/submodels/{submodel['id']}"
                },
            }],
        })
    return _paged(descriptors)


@app.get("/api/v3/submodel-descriptors/{submodel_id}", summary="Fetch one submodel descriptor")
def get_submodel_descriptor(submodel_id: str, request: Request):
    """Returns one registry descriptor for the requested submodel."""
    submodel = _find_submodel(submodel_id)
    api_base = str(request.base_url).rstrip("/")
    return {
        "id": submodel["id"],
        "idShort": submodel.get("idShort"),
        "endpoints": [{
            "interface": "SUBMODEL-3.0",
            "protocolInformation": {
                "href": f"{api_base}/api/v3/submodels/{submodel['id']}"
            },
        }],
    }


@app.get("/api/v3/lookup/shells", summary="Discover AAS shells")
def lookup_shells():
    """AAS Discovery-compatible lookup response."""
    shells = _environment().get("assetAdministrationShells", [])
    return [{"keys": [{"type": "AssetAdministrationShell", "value": shell["id"]}]} for shell in shells]


@app.get("/api/v3/companies", summary="List companies")
def list_companies():
    """Empty company lookup response; this project has no company directory."""
    return []


@app.get("/api/v3/concept-descriptions", summary="List concept descriptions")
def list_concept_descriptions():
    """Empty concept-description response; the AAS uses external semantic IDs."""
    return []


@app.get("/api/v3/shells/{aas_id}", summary="Fetch one AAS shell")
def get_shell(aas_id: str):
    environment = _connector().aas.to_basyx_dict()
    return _find_shell(aas_id)


@app.get("/api/v3/shells/{aas_id}/submodel-refs", summary="List shell submodel references")
def get_shell_submodel_refs(aas_id: str):
    """Returns the references used by BaSyx clients to discover submodels."""
    shell = _find_shell(aas_id)
    return shell.get("submodels", [])


@app.get("/api/v3/shells/{aas_id}/asset-information", summary="Fetch AAS asset information")
def get_asset_information(aas_id: str):
    """Returns the asset information portion of an AAS shell."""
    return _find_shell(aas_id).get("assetInformation", {})


@app.get("/api/v3/submodels", summary="List submodels")
def list_submodels():
    """AAS Submodel Repository API v3 compatible submodel collection."""
    return _paged(_environment().get("submodels", []))


@app.get("/api/v3/submodels/{submodel_id}", summary="Fetch one submodel")
def get_submodel(submodel_id: str):
    return _find_submodel(submodel_id)


def _find_submodel_element(submodel_id: str, id_short_path: str):
    submodel = _find_submodel(submodel_id)
    elements = submodel.get("submodelElements", [])
    current = elements
    for segment in id_short_path.split("/"):
        element = next(
            (candidate for candidate in current if candidate.get("idShort") == segment),
            None,
        )
        if element is None:
            raise HTTPException(status_code=404, detail="Submodel element not found")
        current = element.get("value", []) if element.get("modelType") in {
            "SubmodelElementCollection",
            "SubmodelElementList",
        } else []
    return element


@app.get("/api/v3/submodels/{submodel_id}/submodel-elements", summary="List submodel elements")
def list_submodel_elements(submodel_id: str):
    """Returns the elements of a submodel in BaSyx v3 format."""
    return _paged(_find_submodel(submodel_id).get("submodelElements", []))


@app.get(
    "/api/v3/submodels/{submodel_id}/submodel-elements/{id_short_path:path}",
    summary="Fetch one submodel element",
)
def get_submodel_element(submodel_id: str, id_short_path: str):
    """Returns a property or nested element selected by its idShort path."""
    return _find_submodel_element(submodel_id, id_short_path)


@app.get("/api/v3/aasx", summary="Download the live AASX package")
def download_aasx():
    return Response(
        content=_connector().aas.to_aasx_bytes(),
        media_type="application/asset-administration-shell-package+xml",
        headers={"Content-Disposition": 'attachment; filename="SortingByHeight_AAS.aasx"'},
    )

if __name__ == "__main__":
    uvicorn.run("aas_api:app", host="0.0.0.0", port=8000, reload=True)