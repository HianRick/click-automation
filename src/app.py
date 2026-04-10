"""API de Automação com módulos separados."""

import asyncio
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.core.profile import (
    USER_PROFILE,
    ensure_user_profile_initialized,
    get_resource_path,
)
from src.core.shared_memory import get_race_info, initialize_shared_memory
from src.services.websocket_client import send_to_websocket


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_user_profile_initialized()
    initialize_shared_memory()
    app.state.websocket_task = asyncio.create_task(send_to_websocket())
    try:
        yield
    finally:
        task = getattr(app.state, "websocket_task", None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="API de Automação", version="1.0.0", lifespan=lifespan)


def get_pyautogui():
    """Lazy import do pyautogui para evitar erros de display ao iniciar."""
    import pyautogui

    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.5
    return pyautogui


class CommandRequest(BaseModel):
    code: str


class ClickRequest(BaseModel):
    code: str


@app.post("/click")
async def click_automation(request: ClickRequest):
    if request.code != "aa22":
        raise HTTPException(status_code=401, detail="Invalid code")

    try:
        pyautogui = get_pyautogui()
        button_image = str(get_resource_path("assets/button.png"))
        button_location = pyautogui.locateOnScreen(button_image, confidence=0.8)

        if button_location is None:
            return {
                "success": False,
                "message": "Button not found on screen",
                "error": "Could not locate assets/button.png on the screen",
            }

        button_center = pyautogui.center(button_location)
        pyautogui.click(button_center.x, button_center.y)
        time.sleep(0.3)
        pyautogui.moveTo(1000, 0, duration=0.5)

        return {
            "success": True,
            "message": "Click processed successfully",
            "data": {
                "buttonFound": True,
                "buttonPosition": {"x": button_center.x, "y": button_center.y},
                "finalPosition": {"x": 1000, "y": 0},
                "message": "Button clicked and mouse moved to target position",
            },
        }
    except Exception as e:
        return {
            "success": False,
            "message": "Error processing click",
            "error": str(e),
        }


@app.post("/run-auto")
async def run_auto(request: CommandRequest):
    if request.code != "aa22":
        raise HTTPException(status_code=401, detail="Invalid code")

    try:
        pyautogui = get_pyautogui()
        pyautogui.hotkey("ctrl", "c")
        return {
            "success": True,
            "message": "Run-auto command executed successfully",
            "data": {
                "command": "Ctrl+C",
                "message": "Copy command executed",
            },
        }
    except Exception as e:
        return {
            "success": False,
            "message": "Error executing run-auto command",
            "error": str(e),
        }


@app.post("/kill")
async def kill_process(request: CommandRequest):
    if request.code != "aa22":
        raise HTTPException(status_code=401, detail="Invalid code")

    try:
        pyautogui = get_pyautogui()
        pyautogui.press("esc")
        time.sleep(3)
        pyautogui.hotkey("alt", "F4")

        return {
            "success": True,
            "message": "Kill command executed successfully",
            "data": {
                "commands": ["ESC", "Wait 3s", "Alt+F4"],
                "message": "Kill sequence completed successfully",
            },
        }
    except Exception as e:
        return {
            "success": False,
            "message": "Error executing kill command",
            "error": str(e),
        }


@app.get("/")
async def root():
    return {
        "status": "online",
        "api": "Python Automation API",
        "version": "1.0.0",
        "endpoints": {
            "/click": "Busca botão, clica e move mouse para x:1000 y:0",
            "/run-auto": "Executa Ctrl+C",
            "/kill": "Executa ESC, aguarda 3s e Alt+F4",
        },
    }


@app.get("/race-info")
async def race_info():
    data = get_race_info()

    if data is None:
        raise HTTPException(
            status_code=500,
            detail="Assetto Corsa não está rodando ou memória indisponível",
        )

    return {
        "success": True,
        "data": {
            "piloto": USER_PROFILE["name"],
            "telefone": USER_PROFILE["phone"],
            "pista_selecionada": USER_PROFILE.get("track") or "",
            "carro_selecionado": USER_PROFILE.get("car") or "",
            "skin_selecionada": USER_PROFILE.get("skin") or "",
            **data,
        },
    }


if __name__ == "__main__":
    import uvicorn

    ensure_user_profile_initialized()
    uvicorn.run(app, host="0.0.0.0", port=5001)

