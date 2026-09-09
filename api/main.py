import asyncio
import io
import uuid
import zipfile
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from agents.orchestrator import execute_plan


app = FastAPI(
    title="DevMate API",
    version="1.0.0",
)


# =========================
# CORS
# =========================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================
# PATHS
# =========================

GENERATED_PROJECTS_DIR = Path("generated_projects")


# =========================
# GENERATION JOBS
# =========================

generation_jobs = {}


def _update_generation(job_id, progress):
    job = generation_jobs.get(job_id)
    if not job:
        return

    job["step"] = progress.get("step")
    job["step_state"] = progress.get("state", "running")
    job["message"] = progress.get("message", "")

    history = job.setdefault("history", [])
    history.append(
        {
            "step": progress.get("step"),
            "state": progress.get("state", "running"),
            "message": progress.get("message", ""),
        }
    )


def _run_generation(job_id: str, user_request: str):
    try:
        # execute_plan is async, while its LLM/execution work is mostly
        # synchronous. Run a dedicated event loop in this worker thread
        # so the frontend can keep polling the API during generation.
        result = asyncio.run(
            execute_plan(
                user_request,
                progress_callback=lambda progress: _update_generation(
                    job_id, progress
                ),
            )
        )

        if result["success"]:
            generation_jobs[job_id].update(
                {
                    "status": "completed",
                    "message": "Project generated successfully",
                    "project_path": result["project_path"],
                    "execution": result.get("execution"),
                }
            )
        else:
            generation_jobs[job_id].update(
                {
                    "status": "failed",
                    "message": "Project generation failed",
                    "project_path": result.get("project_path"),
                    "execution": result.get("execution"),
                }
            )

    except Exception as error:
        generation_jobs[job_id].update(
            {
                "status": "failed",
                "message": str(error) or "Project generation failed.",
                "project_path": None,
            }
        )


# =========================
# REQUEST MODELS
# =========================


class GenerateRequest(BaseModel):
    request: str


# =========================
# HEALTH
# =========================


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "DevMate API",
    }


# =========================
# GENERATE PROJECT
# =========================


@app.post("/generate")
async def generate_project(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
):
    if not request.request.strip():
        raise HTTPException(
            status_code=400,
            detail="Project request cannot be empty.",
        )

    job_id = str(uuid.uuid4())

    generation_jobs[job_id] = {
        "status": "generating",
        "step": "planner",
        "step_state": "running",
        "message": "Starting DevMate pipeline...",
        "project_path": None,
        "execution": None,
        "history": [
            {
                "step": "planner",
                "state": "running",
                "message": "Starting DevMate pipeline...",
            }
        ],
    }

    background_tasks.add_task(
        _run_generation,
        job_id,
        request.request.strip(),
    )

    return {
        "status": "generating",
        "generation_id": job_id,
        "message": "Generation started.",
    }


# =========================
# GENERATION STATUS
# =========================


@app.get("/generate/{generation_id}")
async def generation_status(generation_id: str):
    job = generation_jobs.get(generation_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Generation job not found.",
        )

    return {
        "generation_id": generation_id,
        **job,
    }


# =========================
# LIST PROJECT FILES
# =========================


@app.get("/projects/{project_name}/files")
async def list_project_files(project_name: str):
    project_path = (
        GENERATED_PROJECTS_DIR / project_name
    ).resolve()

    base_path = GENERATED_PROJECTS_DIR.resolve()

    if base_path not in project_path.parents:
        raise HTTPException(
            status_code=400,
            detail="Invalid project path.",
        )

    if not project_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Project not found.",
        )

    if not project_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail="Project path is not a directory.",
        )

    files = []

    for path in sorted(project_path.rglob("*")):
        if not path.is_file():
            continue

        relative_path = path.relative_to(project_path)

        if "__pycache__" in relative_path.parts:
            continue

        if path.suffix == ".pyc":
            continue

        relative_path_posix = relative_path.as_posix()

        files.append(
            {
                "path": relative_path_posix,
                "name": path.name,
                "type": "file",
            }
        )

    return {
        "project": project_name,
        "files": files,
        "count": len(files),
    }


# =========================
# READ PROJECT FILE
# =========================


@app.get(
    "/projects/{project_name}/files/{file_path:path}",
    response_class=PlainTextResponse,
)
async def read_project_file(
    project_name: str,
    file_path: str,
):
    project_path = (
        GENERATED_PROJECTS_DIR / project_name
    ).resolve()

    base_path = GENERATED_PROJECTS_DIR.resolve()

    if base_path not in project_path.parents:
        raise HTTPException(
            status_code=400,
            detail="Invalid project path.",
        )

    if not project_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Project not found.",
        )

    target_file = (
        project_path / file_path
    ).resolve()

    if project_path not in target_file.parents:
        raise HTTPException(
            status_code=400,
            detail="Invalid file path.",
        )

    if not target_file.exists():
        raise HTTPException(
            status_code=404,
            detail="File not found.",
        )

    if not target_file.is_file():
        raise HTTPException(
            status_code=400,
            detail="Requested path is not a file.",
        )

    try:
        return target_file.read_text(
            encoding="utf-8"
        )
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=415,
            detail="This file is not a UTF-8 text file.",
        )


# =========================
# DOWNLOAD PROJECT
# =========================


@app.get("/projects/{project_name}/download")
async def download_project(project_name: str):
    project_path = (
        GENERATED_PROJECTS_DIR / project_name
    ).resolve()

    base_path = GENERATED_PROJECTS_DIR.resolve()

    if base_path not in project_path.parents:
        raise HTTPException(
            status_code=400,
            detail="Invalid project path.",
        )

    if not project_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Project not found.",
        )

    if not project_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail="Project path is not a directory.",
        )

    buffer = io.BytesIO()

    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as zip_file:
        for file_path in project_path.rglob("*"):
            if not file_path.is_file():
                continue

            relative_path = file_path.relative_to(
                project_path
            )

            if "__pycache__" in relative_path.parts:
                continue

            if file_path.suffix == ".pyc":
                continue

            zip_file.write(
                file_path,
                arcname=relative_path.as_posix(),
            )

    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{project_name}.zip"'
            )
        },
    )
