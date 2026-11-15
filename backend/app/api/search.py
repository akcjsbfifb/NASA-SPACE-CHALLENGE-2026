from __future__ import annotations

import asyncio
import json
from queue import Empty
from typing import Annotated

from fastapi import APIRouter, Header, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from app.services.earth.activities import VARIABLES, ActivityError, load_catalog, resolve
from app.services.earth.similarity import parse_criteria, write_shortlist
from app.services import notify
from app.services import search_state
from app.services import scene

router = APIRouter(tags=["search"])


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


@router.get("/search")
def search(request: Request) -> JSONResponse:
    query = request.query_params
    try:
        index = search_state.earth_index()
        values = {name: query[name] for name in query if query[name] != ""}
        activity_id = values.pop("activity", None)
        weights = _request_weights(values)
        targets, resolved_weights, preset = resolve(
            activity_id,
            parse_criteria(index.contract, values),
            weights,
        )
        result = index.search(
            targets,
            precision=float(values.get("precision", 0.7)),
            min_worst=_optional_float(query.get("min_worst")),
            weights=resolved_weights,
            activity={"id": preset["id"]} if preset else None,
        )
    except ActivityError as error:
        return JSONResponse({"error": error.code, "message": error.message}, status_code=400)
    except (KeyError, ValueError) as error:
        return JSONResponse({"error": str(error)}, status_code=400)
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
    x_gurvich_notify_token: Annotated[str | None, Header()] = None,
) -> JSONResponse:
    length = int(request.headers.get("content-length", "0") or "0")
    if length > notify.MAX_NOTIFY_BODY:
        return JSONResponse({"error": "payload too large"}, status_code=413)
    token = x_gurvich_notify_token or ""
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