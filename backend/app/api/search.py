from __future__ import annotations

import asyncio
import json
import math
import sys
import threading
from pathlib import Path
from queue import Empty
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from app.config import get_settings
from app.services.earth.activities import VARIABLES, ActivityError, load_catalog, resolve
from app.services.earth.similarity import parse_criteria, write_shortlist
from app.services import notify
from app.services import search_state
from app.services import scene

router = APIRouter(tags=["search"])
_enrichment_lock = threading.BoundedSemaphore(1)


class EnrichmentPoint(BaseModel):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lon: float = Field(ge=-180, le=180, allow_inf_nan=False)


class EnrichmentRequest(BaseModel):
    candidates: list[EnrichmentPoint] = Field(min_length=1, max_length=50)

AUDIENCES = frozenset({"profesional", "aficionado"})
AUDIENCE_LANGUAGES = frozenset({"es", "en", "fr", "it"})


def audience_path() -> Path:
    return get_settings().paths.shortlist.parent / "audience.json"


def _optional_float(raw: str | None) -> float | None:
    if raw is None or raw == "":
        return None
    return float(raw)


def _request_weights(values: dict[str, str]) -> dict[str, float]:
    weights: dict[str, float] = {}
    for name in VARIABLES:
        raw = values.pop(f"w_{name}", None)
        if raw is None:
            continue
        try:
            weights[name] = float(raw)
        except ValueError as error:
            raise ActivityError("bad_weight", f"peso no numérico en {name}") from error
    unknown = sorted(name for name in values if name.startswith("w_"))
    if unknown:
        raise ActivityError("bad_weight", "peso desconocido: " + ", ".join(unknown))
    return weights


@router.get("/events")
async def events() -> StreamingResponse:
    queue = notify.register_sse_client()

    async def stream():
        try:
            yield ": ok\n\n"
            idle = 0.0
            while True:
                try:
                    message = queue.get_nowait()
                except Empty:
                    await asyncio.sleep(0.5)
                    idle += 0.5
                    if idle >= 25:
                        idle = 0.0
                        yield ": ping\n\n"
                    continue
                idle = 0.0
                yield message
        finally:
            notify.unregister_sse_client(queue)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/activities")
def activities() -> JSONResponse:
    try:
        catalog = load_catalog()
    except (OSError, ValueError) as error:
        return JSONResponse({"error": str(error)}, status_code=500)
    return JSONResponse({"activities": catalog})


@router.post("/enrich")
def enrich(request: EnrichmentRequest) -> JSONResponse:
    """Add contextual data after ranking, for at most 50 requested candidates."""
    if not _enrichment_lock.acquire(blocking=False):
        return JSONResponse({"error": "enrichment_busy"}, status_code=429)
    try:
        root = get_settings().paths.repo_root
        processing = str(root / "backend" / "processing")
        if processing not in sys.path:
            sys.path.insert(0, processing)
        try:
            from earth_data.enrich import enrich_candidates
        except ImportError:
            return JSONResponse({"error": "earth_extras_not_installed"}, status_code=503)
        path = get_settings().paths.raw_data / "earth"
        result = enrich_candidates(
            [point.model_dump() for point in request.candidates],
            path / "modis" / "MOD11C3.A2025001.061.2025035172114.hdf",
            "2025-01-01", "2025-01-31", path, limit=50,
        )
        # The complete hourly series remains in the cache; it need not be sent
        # to the page for every candidate.
        for candidate in result['candidates']:
            soil = candidate['additional_measurements']['soil_temperature_0_to_7cm']
            soil.pop('raw_hourly', None)
        result['period'] = {'start': '2025-01-01', 'end': '2025-01-31', 'purpose': 'reproducible_example_not_climatology'}
        return JSONResponse(result)
    finally:
        _enrichment_lock.release()
@router.put("/audience")
async def put_audience(request: Request) -> JSONResponse:
    try:
        body = json.loads((await request.body()).decode() or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "body must be a JSON object"}, status_code=400)
    audience = body.get("audience")
    language = body.get("language")
    if audience not in AUDIENCES or language not in AUDIENCE_LANGUAGES:
        return JSONResponse({"error": "bad_audience"}, status_code=400)
    path = audience_path()
    path.write_text(json.dumps({"audience": audience, "language": language}))
    return JSONResponse({"audience": audience, "language": language})


@router.get("/search")
def search(request: Request) -> JSONResponse:
    query = request.query_params
    try:
        index = search_state.earth_index()
        values = {name: query[name] for name in query if query[name] != ""}
        thermal_targets = {}
        thermal_weights = {}
        for name in ('tbol_modis', 'treg_era5'):
            raw, raw_weight = values.pop(name, None), values.pop('w_' + name, None)
            if raw is None:
                if raw_weight is not None:
                    raise ValueError('Se recibió peso sin temperatura lunar para ' + name)
                continue
            target, weight = float(raw), float(raw_weight if raw_weight is not None else 1)
            if not math.isfinite(target) or target <= 0 or not math.isfinite(weight) or not 0 <= weight <= 1:
                raise ValueError('Temperatura o peso térmico inválido')
            if weight > 0:
                thermal_targets[name], thermal_weights[name] = target, weight
        raw_min_coverage = values.pop('min_coverage', '1')
        min_coverage = int(raw_min_coverage)
        raw_candidate_limit = values.pop('candidate_limit', None)
        candidate_limit = int(raw_candidate_limit) if raw_candidate_limit is not None else None
        if candidate_limit is not None and not 1 <= candidate_limit <= 50:
            raise ValueError('candidate_limit debe estar entre 1 y 50')
        activity_id = values.pop("activity", None)
        weights = _request_weights(values)
        if thermal_targets and not any(values.get(name) is not None and weights.get(name, 1) > 0
                                       for name in ('slope', 'roughness')):
            return JSONResponse({'error': 'unsupported_candidate_generation',
                'message': 'La búsqueda térmica requiere preselección por pendiente o rugosidad; no es global.'}, status_code=400)
        targets, resolved_weights, preset = resolve(
            activity_id,
            parse_criteria(index.contract, values),
            weights,
        )
        if thermal_targets:
            if any(targets.get(name) is not None for name in ('temperature', 'ice', 'rock')):
                raise ValueError('El filtro térmico sólo admite pendiente y rugosidad como preselección')
            if not any(targets.get(name) is not None and resolved_weights.get(name, 1) not in (None, 0)
                       for name in ('slope', 'roughness')):
                return JSONResponse({'error': 'unsupported_candidate_generation',
                    'message': 'La búsqueda térmica requiere preselección por pendiente o rugosidad; no es global.'}, status_code=400)
        result = index.search(
            targets,
            precision=float(values.get("precision", 0.7)),
            min_worst=_optional_float(query.get("min_worst")),
            weights=resolved_weights,
            activity={"id": preset["id"]} if preset else None,
        )
        if candidate_limit is not None:
            result['points'] = result['points'][:candidate_limit]
            result['returned'] = len(result['points'])
            result['closest'] = max((p['closeness'] for p in result['points']), default=None)
            result['loosest'] = min((p['closeness'] for p in result['points']), default=None)
        if thermal_targets:
            if not _enrichment_lock.acquire(blocking=False):
                return JSONResponse({'error': 'enrichment_busy'}, status_code=429)
            try:
                root = get_settings().paths.repo_root
                processing = str(root / 'backend' / 'processing')
                if processing not in sys.path: sys.path.insert(0, processing)
                from earth_data.enrich import enrich_candidates
                from app.services.earth.multivariable import rank_preselected
                selected = result['points'][:50]
                result['points'] = selected
                paths = get_settings().paths.raw_data / 'earth'
                sources = ({'modis'} if 'tbol_modis' in thermal_targets else set()) | ({'era5'} if 'treg_era5' in thermal_targets else set())
                enriched = enrich_candidates(
                    [point.get('coordinates_original', {'lat': point['lat'], 'lon': point['lon']}) for point in selected],
                    paths / 'modis' / 'MOD11C3.A2025001.061.2025035172114.hdf',
                    '2025-01-01', '2025-01-31', paths, limit=50, sources=sources,
                )['candidates']
                for candidate in enriched:
                    candidate['additional_measurements']['soil_temperature_0_to_7cm'].pop('raw_hourly', None)
                result = rank_preselected(result, enriched, thermal_targets, thermal_weights, min_coverage)
            finally:
                _enrichment_lock.release()
        elif min_coverage != 1:
            selected_count = len(result['variables_used'])
            if not 1 <= min_coverage <= selected_count:
                raise ValueError('Cobertura mínima fuera del rango seleccionado')
            evaluated = len(result['points'])
            result['points'] = [point for point in result['points'] if point['coverage'] >= min_coverage]
            result['returned'] = len(result['points'])
            result['closest'] = max((p['closeness'] for p in result['points']), default=None)
            result['loosest'] = min((p['closeness'] for p in result['points']), default=None)
            result['candidate_generation'] = {'scope': 'coverage_filter_after_shortlist',
                'variables': result['variables'], 'evaluated': evaluated,
                'minimum_coverage': min_coverage,
                'limitation': 'filtrado aplicado sólo a candidatos ya seleccionados'}
    except ActivityError as error:
        body = {"error": error.code, "message": error.message}
        if error.code == 'no_measurement': body['scoring_status'] = 'not_available'
        return JSONResponse(body, status_code=400)
    except (KeyError, ValueError) as error:
        body = {"error": str(error)}
        if 'falta al menos una medici' in str(error): body['scoring_status'] = 'not_available'
        return JSONResponse(body, status_code=400)
    except Exception as error:
        return JSONResponse({"error": str(error)}, status_code=500)
    try:
        write_shortlist(result)
    except OSError as error:
        result = {**result, "shortlist_error": str(error)}
    notify.broadcast_search_event(result)
    return JSONResponse(result)


@router.post("/notify")
async def notify_endpoint(
    request: Request,
    x_artemis_notify_token: Annotated[str | None, Header()] = None,
) -> JSONResponse:
    length = int(request.headers.get("content-length", "0") or "0")
    if length > notify.MAX_NOTIFY_BODY:
        return JSONResponse({"error": "payload too large"}, status_code=413)
    token = x_artemis_notify_token or ""
    if not notify.NOTIFY_TOKEN or token != notify.NOTIFY_TOKEN:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    try:
        raw = await request.body()
        body = json.loads(raw.decode() or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"error": "body must be a JSON object"}, status_code=400)
    listeners = notify.broadcast_search_event(body)
    return JSONResponse({"listeners": listeners})


@router.get("/cell")
def cell(request: Request) -> JSONResponse:
    query = request.query_params
    try:
        lat, lon = float(query["lat"]), float(query["lon"])
        found = search_state.earth_index().nearest(lat, lon)
    except KeyError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    except Exception as error:
        return JSONResponse({"error": str(error)}, status_code=500)
    if found is None:
        return JSONResponse({"error": "no land cell"}, status_code=404)
    return JSONResponse(found)


@router.get("/moon")
def moon(request: Request) -> JSONResponse:
    query = request.query_params
    site_id = query.get("site") or ""
    if site_id:
        sample = search_state.moon_sites().find(site_id)
        if sample is None:
            return JSONResponse({"error": f"unknown lunar site {site_id}"}, status_code=404)
        return JSONResponse(sample)
    try:
        lat, lon = float(query["lat"]), float(query["lon"])
        sample = search_state.moon_sampler().sample(lat, lon)
    except KeyError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    except Exception as error:
        return JSONResponse({"error": str(error)}, status_code=503)
    return JSONResponse(sample)


@router.get("/scene")
def scene_view(request: Request) -> Response:
    query = request.query_params
    try:
        lat, lon = float(query["lat"]), float(query["lon"])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("coordinates out of range")
        payload, content_type, source = scene.satellite_scene(lat, lon, scene.maps_key())
    except KeyError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    except ValueError as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    except Exception as error:
        return JSONResponse({"error": str(error)}, status_code=502)
    return Response(
        content=payload,
        media_type=content_type.split(";")[0],
        headers={
            "X-Image-Source": source,
            "Access-Control-Expose-Headers": "X-Image-Source",
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "no-store",
        },
    )
