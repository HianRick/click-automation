"""
API de Automação com Python
Comandos de controle de mouse e teclado
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import time
import asyncio
from typing import Optional
import ctypes
import mmap
import websockets
import json
import os
import re
from pathlib import Path
from contextlib import asynccontextmanager

class SPageFileGraphics(ctypes.Structure):
    _fields_ = [
        ("packetId", ctypes.c_int),
        ("status", ctypes.c_int),
        ("session", ctypes.c_int),
        ("currentTime", ctypes.c_wchar * 15),
        ("lastTime", ctypes.c_wchar * 15),
        ("bestTime", ctypes.c_wchar * 15),
    ]

class SPageFileStatic(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("smVersion", ctypes.c_wchar * 15),
        ("acVersion", ctypes.c_wchar * 15),
        ("numberOfSessions", ctypes.c_int),
        ("numCars", ctypes.c_int),  
        ("carModel", ctypes.c_wchar * 33),
        ("track", ctypes.c_wchar * 33),
    ]

def open_shared_memory(name, size):
    try:
        return mmap.mmap(-1, size, name)
    except Exception:
        return None  # jogo provavelmente não está aberto

graphics_map = None
static_map = None

#True para usar dados mockados quando a memória compartilhada não estiver disponível
#False para quando tiver o jogo rodando e quiser os dados reais
USE_MOCK = False

USER_PROFILE = {
    "name": "Player",
    "phone": "",
    "track": "drag2000",
    "car": "",
    "skin": ""
}
USER_PROFILE_INITIALIZED = False
RACE_INI_PATH = Path.home() / "Documents" / "Assetto Corsa" / "cfg" / "race.ini"


def initialize_shared_memory():
    global graphics_map, static_map
    graphics_map = open_shared_memory("acpmf_graphics", ctypes.sizeof(SPageFileGraphics))
    static_map = open_shared_memory("acpmf_static", ctypes.sizeof(SPageFileStatic))


def find_assetto_base_path() -> Optional[Path]:
    env_candidates = []
    program_files = os.getenv("PROGRAMFILES")
    program_files_x86 = os.getenv("PROGRAMFILES(X86)")

    if program_files:
        env_candidates.append(Path(program_files) / "Steam" / "steamapps" / "common" / "assettocorsa")
    if program_files_x86:
        env_candidates.append(Path(program_files_x86) / "Steam" / "steamapps" / "common" / "assettocorsa")

    fixed_candidates = [
        Path("C:/Program Files/Steam/steamapps/common/assettocorsa"),
        Path("C:/Program Files (x86)/Steam/steamapps/common/assettocorsa"),
    ]

    for candidate in env_candidates + fixed_candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate

    return None


def list_assetto_dirs(base_path: Optional[Path], section: str) -> list[str]:
    if not base_path:
        return []

    section_path = base_path / "content" / section
    if not section_path.exists() or not section_path.is_dir():
        return []

    return sorted(
        [item.name for item in section_path.iterdir() if item.is_dir()],
        key=str.lower,
    )


def list_car_skins(base_path: Optional[Path], car_name: str) -> list[str]:
    if not base_path or not car_name:
        return []

    skins_path = base_path / "content" / "cars" / car_name / "skins"
    if not skins_path.exists() or not skins_path.is_dir():
        return []

    return sorted(
        [item.name for item in skins_path.iterdir() if item.is_dir()],
        key=str.lower,
    )


def find_car_preview_image(base_path: Optional[Path], car_name: str, skin_name: str) -> Optional[Path]:
    if not base_path or not car_name:
        return None

    car_root = base_path / "content" / "cars" / car_name
    if not car_root.exists() or not car_root.is_dir():
        return None

    valid_extensions = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

    def find_preview_in_dir(directory: Path) -> Optional[Path]:
        if not directory.exists() or not directory.is_dir():
            return None

        for item in directory.iterdir():
            if not item.is_file():
                continue
            if item.stem.lower() == "preview" and item.suffix.lower() in valid_extensions:
                return item

        return None

    search_roots = []

    if skin_name:
        search_roots.append(car_root / "skins" / skin_name)

    search_roots.extend(
        [
            car_root,
            car_root / "ui",
        ]
    )

    skins_root = car_root / "skins"
    if skins_root.exists() and skins_root.is_dir():
        for skin_dir in sorted([d for d in skins_root.iterdir() if d.is_dir()], key=lambda p: p.name.lower()):
            search_roots.append(skin_dir)
            search_roots.append(skin_dir / "ui")

    for root in search_roots:
        preview_path = find_preview_in_dir(root)
        if preview_path:
            return preview_path

    return None


def collect_user_profile_gui() -> Optional[dict]:
    try:
        import tkinter as tk
        from tkinter import messagebox
        from tkinter import ttk
        from PIL import Image, ImageOps, ImageTk
    except Exception:
        return None

    result = {
        "name": "",
        "phone": "",
        "track": "",
        "car": "",
        "skin": ""
    }
    submitted = {"ok": False}

    assetto_base = find_assetto_base_path()
    track_options = ["drag1000", "drag2000", "drag500"]
    cars = list_assetto_dirs(assetto_base, "cars")

    root = tk.Tk()
    root.title("Identificação do Piloto")
    root.geometry("760x620")
    root.resizable(False, False)

    container = tk.Frame(root, padx=20, pady=16)
    container.pack(fill="both", expand=True)

    tk.Label(container, text="Informe os dados antes de iniciar", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 12))

    tk.Label(container, text="Nome").pack(anchor="w")
    name_var = tk.StringVar()
    name_entry = tk.Entry(container, textvariable=name_var)
    name_entry.pack(fill="x", pady=(2, 10))

    tk.Label(container, text="Telefone").pack(anchor="w")
    phone_var = tk.StringVar()
    phone_entry = tk.Entry(container, textvariable=phone_var)
    phone_entry.pack(fill="x", pady=(2, 14))

    tk.Label(container, text="Config Track").pack(anchor="w")
    track_var = tk.StringVar()
    track_combo = ttk.Combobox(container, textvariable=track_var, state="readonly", values=track_options)
    track_combo.pack(fill="x", pady=(2, 10))
    track_combo.set(USER_PROFILE.get("track", "drag2000"))

    car_var = tk.StringVar()

    tk.Label(container, text="Carro").pack(anchor="w")
    car_select_frame = tk.Frame(container)
    car_select_frame.pack(fill="x", pady=(2, 10))
    selected_car_label = tk.Label(car_select_frame, text="Nenhum carro selecionado", anchor="w")
    selected_car_label.pack(side="left", fill="x", expand=True)

    tk.Label(container, text="Variação (skin)").pack(anchor="w")
    skin_var = tk.StringVar()
    skin_combo = ttk.Combobox(container, textvariable=skin_var, state="readonly", values=[])
    skin_combo.pack(fill="x", pady=(2, 12))

    footer_frame = tk.Frame(container)
    footer_frame.pack(fill="x", side="bottom")

    image_frame = tk.LabelFrame(container, text="Preview do carro", padx=8, pady=8)
    image_frame.pack(fill="both", expand=True, pady=(0, 12))
    preview_label = tk.Label(image_frame, text="Selecione carro e skin para visualizar.")
    preview_label.pack(fill="both", expand=True)

    image_state = {"preview": None}

    def refresh_preview():
        car_name = car_var.get().strip()
        skin_name = skin_var.get().strip()
        preview_path = find_car_preview_image(assetto_base, car_name, skin_name)

        if not preview_path:
            preview_label.configure(text="Imagem preview não encontrada.", image="")
            image_state["preview"] = None
            return

        try:
            image = Image.open(preview_path)
            image.thumbnail((700, 280))
            image_tk = ImageTk.PhotoImage(image)
            preview_label.configure(image=image_tk, text="")
            image_state["preview"] = image_tk
        except Exception:
            preview_label.configure(text=f"Falha ao carregar imagem: {preview_path}", image="")
            image_state["preview"] = None

    def open_car_selector():
        selector = tk.Toplevel(root)
        selector.title("Selecionar carro")
        selector.geometry("920x620")
        selector.transient(root)
        selector.grab_set()

        wrapper = tk.Frame(selector, padx=12, pady=12)
        wrapper.pack(fill="both", expand=True)

        tk.Label(wrapper, text="Escolha o carro pela imagem", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 8))

        canvas = tk.Canvas(wrapper, highlightthickness=0)
        scroll = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        cards = tk.Frame(canvas)

        cards.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=cards, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        car_images = []

        def choose_car(car_name: str):
            car_var.set(car_name)
            selected_car_label.configure(text=car_name)
            refresh_skins()
            selector.destroy()

        if not cars:
            tk.Label(cards, text="Nenhum carro encontrado na instalação do Assetto Corsa.").pack(anchor="w")
            return

        target_size = (240, 135)
        columns = 3
        for index, car_name in enumerate(cars):
            row = index // columns
            column = index % columns

            card = tk.Frame(cards, relief="groove", borderwidth=1, padx=6, pady=6)
            card.grid(row=row, column=column, padx=6, pady=6, sticky="nsew")

            preview_path = find_car_preview_image(assetto_base, car_name, "")
            if preview_path:
                try:
                    preview_image = Image.open(preview_path).convert("RGB")
                    preview_image = ImageOps.fit(preview_image, target_size, method=Image.Resampling.LANCZOS)
                except Exception:
                    preview_image = Image.new("RGB", target_size, "#2c2c2c")
            else:
                preview_image = Image.new("RGB", target_size, "#2c2c2c")

            preview_photo = ImageTk.PhotoImage(preview_image)
            image_button = tk.Button(
                card,
                image=preview_photo,
                width=target_size[0],
                height=target_size[1],
                command=lambda c=car_name: choose_car(c),
            )
            car_images.append(preview_photo)

            image_button.pack(fill="both", expand=True)
            tk.Label(card, text=car_name, anchor="center", wraplength=target_size[0]).pack(fill="x", pady=(6, 0))

        for col in range(columns):
            cards.grid_columnconfigure(col, weight=1)

        # Mantém as referências das imagens para evitar coleta de lixo do Tkinter.
        selector._car_images = car_images

    def refresh_skins(*_):
        car_name = car_var.get().strip()
        skins = list_car_skins(assetto_base, car_name)
        skin_combo["values"] = skins
        if skins:
            skin_combo.current(0)
        else:
            skin_var.set("")
        refresh_preview()

    skin_combo.bind("<<ComboboxSelected>>", lambda _event: refresh_preview())

    tk.Button(car_select_frame, text="Selecionar por imagem", command=open_car_selector).pack(side="right", padx=(10, 0))

    if USER_PROFILE.get("car"):
        car_var.set(USER_PROFILE["car"])
        selected_car_label.configure(text=USER_PROFILE["car"])
        refresh_skins()

    def on_submit():
        name = name_var.get().strip()
        phone = phone_var.get().strip()

        if not name:
            messagebox.showwarning("Campo obrigatório", "Digite o nome do piloto.")
            return

        if not phone:
            messagebox.showwarning("Campo obrigatório", "Digite o número de telefone.")
            return

        result["name"] = name
        result["phone"] = phone
        result["track"] = track_var.get().strip()
        result["car"] = car_var.get().strip()
        result["skin"] = skin_var.get().strip()
        submitted["ok"] = True
        root.destroy()

    def on_close():
        root.destroy()

    tk.Button(footer_frame, text="Iniciar", command=on_submit).pack(anchor="e")

    root.protocol("WM_DELETE_WINDOW", on_close)
    name_entry.focus_set()
    root.mainloop()

    if submitted["ok"]:
        return result

    return None


def collect_user_profile():
    gui_profile = collect_user_profile_gui()
    if gui_profile:
        return gui_profile

    # Em execução sem terminal interativo, usa variáveis de ambiente ou padrão.
    if not os.isatty(0):
        config_track = os.getenv("CONFIG_TRACK", "drag2000").strip() or "drag2000"
        if config_track not in {"drag1000", "drag2000", "drag500"}:
            config_track = "drag2000"
        return {
            "name": os.getenv("DRIVER_NAME", "Player").strip() or "Player",
            "phone": os.getenv("DRIVER_PHONE", "").strip(),
            "track": config_track,
            "car": os.getenv("DRIVER_CAR", "").strip(),
            "skin": os.getenv("DRIVER_SKIN", "").strip(),
        }

    while True:
        try:
            name = input("Digite seu nome: ").strip()
        except EOFError:
            name = "Player"
        if name:
            break
        print("Nome não pode ficar vazio.")

    while True:
        try:
            phone = input("Digite seu número de telefone: ").strip()
        except EOFError:
            phone = ""
        if phone:
            break
        print("Telefone não pode ficar vazio.")

    while True:
        try:
            track = input("Digite CONFIG_TRACK (drag1000, drag2000, drag500) [drag2000]: ").strip()
        except EOFError:
            track = ""

        track = track or "drag2000"
        if track in {"drag1000", "drag2000", "drag500"}:
            break
        print("Valor inválido para CONFIG_TRACK. Use drag1000, drag2000 ou drag500.")

    try:
        car = input("Digite o carro (opcional): ").strip()
    except EOFError:
        car = ""

    try:
        skin = input("Digite a skin/variação (opcional): ").strip()
    except EOFError:
        skin = ""

    return {
        "name": name,
        "phone": phone,
        "track": track,
        "car": car,
        "skin": skin,
    }


def ensure_user_profile_initialized():
    global USER_PROFILE_INITIALIZED

    if USER_PROFILE_INITIALIZED:
        return

    profile = collect_user_profile()
    USER_PROFILE.update(profile)

    updated_race_file = update_race_config_in_race_file(USER_PROFILE)
    if updated_race_file:
        print(f"Configuração da corrida atualizada em: {updated_race_file}")
    else:
        print("Não foi possível localizar o arquivo race.ini em Documents\\Assetto Corsa\\cfg.")

    USER_PROFILE_INITIALIZED = True


def _upsert_ini_section_values(text: str, section_name: str, values: dict[str, str]) -> str:
    if not values:
        return text

    line_break = "\r\n" if "\r\n" in text else "\n"
    section_regex = re.compile(
        rf"(?ms)^\[{re.escape(section_name)}\]\s*$.*?(?=^\[|\Z)"
    )
    section_match = section_regex.search(text)

    if section_match:
        section_text = section_match.group(0)
        for key, value in values.items():
            key_regex = re.compile(rf"(?m)^\s*{re.escape(key)}\s*=.*$")
            new_line = f"{key}={value}"
            if key_regex.search(section_text):
                section_text = key_regex.sub(new_line, section_text, count=1)
            else:
                section_text = f"{section_text.rstrip()}{line_break}{new_line}{line_break}"

        return f"{text[:section_match.start()]}{section_text}{text[section_match.end():]}"

    section_lines = [f"[{section_name}]"]
    for key, value in values.items():
        section_lines.append(f"{key}={value}")

    appended_section = line_break.join(section_lines) + line_break
    if text.strip():
        return f"{text.rstrip()}{line_break}{line_break}{appended_section}"

    return appended_section


def update_race_config_in_race_file(profile: dict[str, str]) -> Optional[Path]:
    if RACE_INI_PATH.is_file():
        candidate_paths = [RACE_INI_PATH]
    else:
        candidate_paths = []

    base_path = Path.home() / "Documents" / "Assetto Corsa"
    candidate_dirs = [
        base_path / "cng",
        base_path / "cfg",
        base_path,
    ]
    candidate_files = ["race", "race.ini"]

    for directory in candidate_dirs:
        for file_name in candidate_files:
            race_file = directory / file_name
            if race_file not in candidate_paths:
                candidate_paths.append(race_file)

    for race_file in candidate_paths:
        if not race_file.is_file():
            continue

        text = None
        encoding_used = "utf-8"
        for enc in ("utf-8", "latin-1"):
            try:
                text = race_file.read_text(encoding=enc)
                encoding_used = enc
                break
            except Exception:
                continue

        if text is None:
            continue

        race_updates = {}
        if profile.get("track", "").strip():
            race_updates["CONFIG_TRACK"] = profile["track"].strip()
        if profile.get("car", "").strip():
            race_updates["MODEL"] = profile["car"].strip()
        if profile.get("skin", "").strip():
            race_updates["SKIN"] = profile["skin"].strip()

        car_0_updates = {
            "DRIVER_NAME": profile.get("name", "").strip() or "Player",
        }
        if profile.get("car", "").strip():
            car_0_updates["MODEL"] = profile["car"].strip()
        if profile.get("skin", "").strip():
            car_0_updates["SKIN"] = profile["skin"].strip()

        remote_updates = {}
        if profile.get("name", "").strip():
            remote_updates["NAME"] = profile["name"].strip()
        if profile.get("car", "").strip():
            remote_updates["REQUESTED_CAR"] = profile["car"].strip()

        updated_text = text
        if race_updates:
            updated_text = _upsert_ini_section_values(updated_text, "RACE", race_updates)
        updated_text = _upsert_ini_section_values(updated_text, "CAR_0", car_0_updates)
        if remote_updates:
            updated_text = _upsert_ini_section_values(updated_text, "REMOTE", remote_updates)

        race_file.write_text(updated_text, encoding=encoding_used)
        return race_file

    return None


def get_race_info():
    if USE_MOCK:
        return {
            "carro": "porsche_911_gt3",
            "pista": "monza",
            "ultima_volta": "01:42:321",
            "melhor_volta": "01:41:999",
            "tempo_atual": "00:15:200"
        }

    if not graphics_map or not static_map:
        return None

    try:
        graphics = SPageFileGraphics.from_buffer_copy(graphics_map)
        static = SPageFileStatic.from_buffer_copy(static_map)

        return {
            "carro": static.carModel.strip(),
            "pista": static.track.strip(),
            "ultima_volta": graphics.lastTime.strip(),
            "melhor_volta": graphics.bestTime.strip(),
            "tempo_atual": graphics.currentTime.strip()
        }
    except Exception:
        return None
    
def convert_time_to_ms(time_str): ##gogo dada
    try:
        if not time_str or time_str == "":
            return 0

        parts = time_str.split(":")
        minutes = int(parts[0])
        seconds = int(parts[1])
        millis = int(parts[2])

        return (minutes * 60 * 1000) + (seconds * 1000) + millis
    except:
        return 0

WS_URL = "ws://181.214.95.75:7080/input"

async def send_to_websocket():
    while True:
        data = get_race_info()

        if data:
            selected_car = USER_PROFILE.get("car") or data["carro"]
            selected_track = USER_PROFILE.get("track") or data.get("pista") or "Unknown"
            payload = {
                "type": "simulator-update",
                "data": {
                    "simNum": 1,
                    "pilot-name": USER_PROFILE["name"],
                    "pilot-phone": USER_PROFILE["phone"],
                    "car": selected_car,
                    "track": selected_track,
                    "skin": USER_PROFILE.get("skin") or "",
                    "lapData": {
                        "lapTime": convert_time_to_ms(data["ultima_volta"]),
                        "isValid": True
                    },
                    "bestLap": convert_time_to_ms(data["melhor_volta"])
                }
            }

            try:
                async with websockets.connect(WS_URL) as websocket:
                    print("Enviado:", payload)
                    await websocket.send(json.dumps(payload))

            except Exception as e:
                print("Erro ao enviar websocket:", e)

        await asyncio.sleep(1)  # envia a cada 1 segundo


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_user_profile_initialized()
    initialize_shared_memory()
    # Cria a task no loop ativo do FastAPI/Uvicorn.
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
    """Lazy import do pyautogui para evitar erros de display ao iniciar"""
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
    """
    Busca um botão igual à imagem button.png, clica nele e move o mouse para x:1000 y:0
    """
    if request.code != "aa22":
        raise HTTPException(status_code=401, detail="Invalid code")
    
    try:
        pyautogui = get_pyautogui()
        
        # Busca a imagem button.png na tela
        button_location = pyautogui.locateOnScreen('button.png', confidence=0.8)
        
        if button_location is None:
            return {
                "success": False,
                "message": "Button not found on screen",
                "error": "Could not locate button.png on the screen"
            }
        
        # Obtém o centro do botão encontrado
        button_center = pyautogui.center(button_location)
        
        # Clica no botão
        pyautogui.click(button_center.x, button_center.y)
        
        # Aguarda um momento
        time.sleep(0.3)
        
        # Move o mouse para a posição especificada
        pyautogui.moveTo(1000, 0, duration=0.5)
        
        return {
            "success": True,
            "message": "Click processed successfully",
            "data": {
                "buttonFound": True,
                "buttonPosition": {"x": button_center.x, "y": button_center.y},
                "finalPosition": {"x": 1000, "y": 0},
                "message": "Button clicked and mouse moved to target position"
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": "Error processing click",
            "error": str(e)
        }


@app.post("/run-auto")
async def run_auto(request: CommandRequest):
    """
    Executa o comando Ctrl+C
    """
    if request.code != "aa22":
        raise HTTPException(status_code=401, detail="Invalid code")
    
    try:
        pyautogui = get_pyautogui()
        
        # Executa Ctrl+C
        pyautogui.hotkey('ctrl', 'c')
        
        return {
            "success": True,
            "message": "Run-auto command executed successfully",
            "data": {
                "command": "Ctrl+C",
                "message": "Copy command executed"
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": "Error executing run-auto command",
            "error": str(e)
        }


@app.post("/kill")
async def kill_process(request: CommandRequest):
    """
    Aperta ESC, aguarda 3 segundos e executa Alt+F4
    """
    if request.code != "aa22":
        raise HTTPException(status_code=401, detail="Invalid code")
    
    try:
        pyautogui = get_pyautogui()
        
        # Aperta ESC
        pyautogui.press('esc')
        
        # Aguarda 3 segundos
        time.sleep(3)
        
        # Executa Alt+F4
        pyautogui.hotkey('alt', 'F4')
        
        return {
            "success": True,
            "message": "Kill command executed successfully",
            "data": {
                "commands": ["ESC", "Wait 3s", "Alt+F4"],
                "message": "Kill sequence completed successfully"
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": "Error executing kill command",
            "error": str(e)
        }


@app.get("/")
async def root():
    """
    Endpoint de status da API
    """
    return {
        "status": "online",
        "api": "Python Automation API",
        "version": "1.0.0",
        "endpoints": {
            "/click": "Busca botão, clica e move mouse para x:1000 y:0",
            "/run-auto": "Executa Ctrl+C",
            "/kill": "Executa ESC, aguarda 3s e Alt+F4"
        }
    }


@app.get("/race-info")
async def race_info():
    """
    Retorna informações da corrida do Assetto Corsa
    """
    data = get_race_info()

    if data is None:
        raise HTTPException(
            status_code=500,
            detail="Assetto Corsa não está rodando ou memória indisponível"
        )

    return {
        "success": True,
        "data": {
            "piloto": USER_PROFILE["name"],  # não vem da shared memory
            "telefone": USER_PROFILE["phone"],
            "pista_selecionada": USER_PROFILE.get("track") or "",
            "carro_selecionado": USER_PROFILE.get("car") or "",
            "skin_selecionada": USER_PROFILE.get("skin") or "",
            **data
        }
    }


if __name__ == "__main__":
    import uvicorn

    ensure_user_profile_initialized()

    uvicorn.run(app, host="0.0.0.0", port=5001)