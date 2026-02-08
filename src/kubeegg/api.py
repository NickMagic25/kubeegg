from __future__ import annotations

import dataclasses

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .egg import parse_egg
from .fetch import load_egg_json

app = FastAPI(title="kubeegg")


class RequirementsRequest(BaseModel):
    source: str


class VariableResponse(BaseModel):
    name: str
    env_variable: str | None
    description: str | None
    default_value: str | None
    required: bool


class RequirementsResponse(BaseModel):
    name: str | None
    description: str | None
    startup: str | None
    docker_images: dict[str, str]
    variables: list[VariableResponse]
    ports: list[int]
    install_script: str | None
    install_image: str | None
    install_entrypoint: str | None


@app.post("/requirements", response_model=RequirementsResponse)
def get_requirements(req: RequirementsRequest) -> RequirementsResponse:
    try:
        result = load_egg_json(req.source)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        egg = parse_egg(result.data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse egg: {exc}") from exc

    return RequirementsResponse(**dataclasses.asdict(egg))


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
