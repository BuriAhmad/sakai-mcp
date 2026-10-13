"""Trusted-token artifact gateway, separate from model-visible MCP results."""

import re

from starlette.requests import Request
from starlette.responses import JSONResponse, StreamingResponse
from starlette.routing import Route

from sakai_mcp.auth import EntraTokenVerifier
from sakai_mcp.sakai_client import ErrorCode, SakaiClient, SakaiError


def artifact_route(client: SakaiClient, verifier: EntraTokenVerifier) -> Route:
    async def download(request: Request):
        header = request.headers.get("authorization", "")
        if not header.startswith("Bearer "):
            return JSONResponse({"error": "UNAUTHENTICATED"}, status_code=401)
        principal = await verifier.verify_token(header[7:])
        if principal is None:
            return JSONResponse({"error": "UNAUTHENTICATED"}, status_code=401)
        try:
            p = request.path_params
            upstream = await client.grading_artifact(
                principal, p["course"], p["assignment"], p["export"], p["artifact"]
            )
        except SakaiError as error:
            status = {
                ErrorCode.UNAUTHENTICATED: 401,
                ErrorCode.FORBIDDEN: 403,
                ErrorCode.NOT_FOUND: 404,
                ErrorCode.VALIDATION_ERROR: 400,
                ErrorCode.UNSUPPORTED_CAPABILITY: 501,
            }.get(error.code, 503)
            return JSONResponse({"error": error.code.value}, status_code=status)
        total = int(upstream.headers["content-length"])
        etag = '"' + upstream.headers["x-content-sha256"] + '"'
        headers = {
            "Cache-Control": "private, no-store",
            "ETag": etag,
            "X-Content-SHA256": upstream.headers["x-content-sha256"],
            "Accept-Ranges": "bytes",
        }
        start, end, status = 0, total - 1, 200
        selected_range = request.headers.get("range")
        if selected_range and request.headers.get("if-range", etag) == etag:
            match = re.fullmatch(r"bytes=([0-9]{0,20})-([0-9]{0,20})", selected_range)
            if match and any(match.groups()) and total:
                left, right = match.groups()
                start = int(left) if left else max(0, total - int(right))
                end = min(total - 1, int(right)) if left and right else total - 1
                if start <= end < total:
                    status = 206
                    headers["Content-Range"] = f"bytes {start}-{end}/{total}"
                else:
                    match = None
            else:
                match = None
            if match is None:
                await upstream.aclose()
                return JSONResponse(
                    {"error": "INVALID_RANGE"},
                    status_code=416,
                    headers={"Content-Range": f"bytes */{total}"},
                )
        headers["Content-Length"] = str(max(0, end - start + 1))

        async def chunks():
            position = 0
            try:
                async for chunk in upstream.aiter_bytes():
                    after = position + len(chunk)
                    if after > total:
                        raise RuntimeError("artifact_size_mismatch")
                    if after > start and position <= end:
                        yield chunk[
                            max(0, start - position) : min(
                                len(chunk), end + 1 - position
                            )
                        ]
                    position = after
                    if position > end:
                        break
                if position <= end:
                    raise RuntimeError("artifact_truncated")
            finally:
                await upstream.aclose()

        return StreamingResponse(
            chunks(),
            status_code=status,
            media_type="application/octet-stream",
            headers=headers,
        )

    return Route(
        "/grading-artifacts/{course}/{assignment}/{export}/{artifact}",
        download,
        methods=["GET"],
    )
