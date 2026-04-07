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
import sys
import random
import subprocess
import threading
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
PROFILE_GUI_STARTED = False
PROFILE_UPDATE_LOCK = threading.Lock()
RACE_INI_PATH = Path.home() / "Documents" / "Assetto Corsa" / "cfg" / "race.ini"
AC_DRAG = 6
TRACK_CONFIG_TO_DISPLAY = {
    "drag500": "500 metros",
    "drag1000": "1000 metros",
    "drag2000": "2000 metros",
}
TRACK_DISPLAY_TO_CONFIG = {value: key for key, value in TRACK_CONFIG_TO_DISPLAY.items()}
RACE_MONITOR_STATE = {
    "game_started": False,
    "restart_triggered": False,
}
ENABLE_AUTO_RESTART = os.getenv("ENABLE_AUTO_RESTART", "1").strip().lower() in {"1", "true", "yes", "on"}
ENABLE_APP_RESTART = os.getenv("ENABLE_APP_RESTART", "0").strip().lower() in {"1", "true", "yes", "on"}


def normalize_track_value(value: str) -> str:
    normalized = (value or "").strip().lower().replace("m", "").replace("metros", "").strip()
    if normalized in {"500", "1000", "2000"}:
        return f"drag{normalized}"
    if value in TRACK_DISPLAY_TO_CONFIG:
        return TRACK_DISPLAY_TO_CONFIG[value]
    if value in TRACK_CONFIG_TO_DISPLAY:
        return value
    return ""


def to_track_display(track_config: str) -> str:
    return TRACK_CONFIG_TO_DISPLAY.get(track_config, TRACK_CONFIG_TO_DISPLAY["drag2000"])


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


def launch_assetto_corsa_game() -> tuple[bool, str]:
    # Prioriza o caminho informado e tenta nomes comuns de executável.
    preferred_base = Path("C:/Program Files (x86)/Steam/steamapps/common/assettocorsa")
    base_candidates = [preferred_base]

    discovered_base = find_assetto_base_path()
    if discovered_base and discovered_base not in base_candidates:
        base_candidates.append(discovered_base)

    executable_names = ["acs.exe", "AssettoCorsa.exe"]

    for base_path in base_candidates:
        for executable_name in executable_names:
            executable_path = base_path / executable_name
            if not executable_path.is_file():
                continue

            try:
                subprocess.Popen([str(executable_path)], cwd=str(base_path))
                return True, f"Jogo iniciado: {executable_path}"
            except Exception as exc:
                return False, f"Falha ao iniciar o jogo em {executable_path}: {exc}"

    return False, "Não foi encontrado acs.exe/AssettoCorsa.exe no diretório do Assetto Corsa."


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


def collect_user_profile_gui(keep_open: bool = False, on_submit_profile=None) -> Optional[dict]:
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
    track_options = list(TRACK_DISPLAY_TO_CONFIG.keys())
    cars = list_assetto_dirs(assetto_base, "cars")

    root = tk.Tk()
    root.title("Identificação do Piloto")
    
    # Tela cheia (sem barras superior/inferior)
    root.attributes('-fullscreen', True)
        
    root.bind("<Escape>", lambda e: root.attributes("-fullscreen", False))

    # Estilo de Corrida (Dark Theme com tons chamativos)
    BG_COLOR = "#121212"
    FG_COLOR = "#FFFFFF"
    ACCENT_COLOR = "#E53935"
    INPUT_BG = "#2C2C2C"
    
    root.configure(bg=BG_COLOR)
    
    style = ttk.Style()
    style.theme_use('clam')
    style.configure(
        "Race.TCombobox",
        fieldbackground=INPUT_BG,
        background=INPUT_BG,
        foreground=FG_COLOR,
        borderwidth=0,
        arrowsize=16,
    )
    style.map(
        "Race.TCombobox",
        fieldbackground=[("readonly", INPUT_BG)],
        foreground=[("readonly", FG_COLOR)],
        selectbackground=[("readonly", INPUT_BG)],
        selectforeground=[("readonly", FG_COLOR)],
    )
    style.configure("Vertical.TScrollbar", background=INPUT_BG, troughcolor=BG_COLOR)
    root.option_add("*TCombobox*Listbox*Background", INPUT_BG)
    root.option_add("*TCombobox*Listbox*Foreground", FG_COLOR)
    root.option_add("*TCombobox*Listbox*selectBackground", "#3A3A3A")
    root.option_add("*TCombobox*Listbox*selectForeground", FG_COLOR)

    # Logo no topo
    logo_path = Path("logo.png")
    if logo_path.exists():
        try:
            logo_img = Image.open(logo_path)
            # Redimensiona mantendo aspecto
            logo_img.thumbnail((400, 150))
            logo_tk = ImageTk.PhotoImage(logo_img)
            logo_label = tk.Label(root, image=logo_tk, bg=BG_COLOR)
            logo_label.image = logo_tk  # Previne GC
            logo_label.pack(pady=(20, 10))
        except Exception:
            pass

    container = tk.Frame(root, padx=20, pady=10, bg=BG_COLOR)
    container.pack(fill="both", expand=True)

    tk.Label(container, text="PREPARE-SE PARA A CORRIDA", font=("Impact", 18, "italic"), bg=BG_COLOR, fg=ACCENT_COLOR).pack(anchor="n", pady=(0, 20))

    # Limitar largura dos formulários centralizados
    form_center = tk.Frame(container, bg=BG_COLOR)
    form_center.pack(anchor="n", pady=5)

    # Estilo customizado para labels e entries
    def ui_label(parent, text):
        return tk.Label(parent, text=text, font=("Segoe UI", 10, "bold"), bg=BG_COLOR, fg=FG_COLOR)
        
    def ui_entry(parent, textvar):
        return tk.Entry(parent, textvariable=textvar, font=("Segoe UI", 11), bg=INPUT_BG, fg=FG_COLOR, insertbackground=FG_COLOR, relief="flat", width=60)

    ui_label(form_center, "NOME DO PILOTO").pack(anchor="w")
    name_var = tk.StringVar()
    name_entry = ui_entry(form_center, name_var)
    name_entry.pack(fill="x", pady=(2, 12), ipady=4)

    ui_label(form_center, "TELEFONE").pack(anchor="w")
    phone_var = tk.StringVar()
    phone_entry = ui_entry(form_center, phone_var)
    phone_entry.pack(fill="x", pady=(2, 16), ipady=4)

    ui_label(form_center, "DISTÂNCIA DE DRAG").pack(anchor="w")
    track_var = tk.StringVar()
    track_combo = ttk.Combobox(form_center, textvariable=track_var, state="readonly", values=track_options, font=("Segoe UI", 11), style="Race.TCombobox")
    track_combo.pack(fill="x", pady=(2, 12), ipady=4)
    track_combo.set(to_track_display(USER_PROFILE.get("track", "drag2000")))

    car_var = tk.StringVar()

    ui_label(form_center, "MÁQUINA (CARRO)").pack(anchor="w")
    car_select_frame = tk.Frame(form_center, bg=BG_COLOR)
    car_select_frame.pack(fill="x", pady=(2, 12))
    selected_car_label = tk.Label(car_select_frame, text="Nenhum carro selecionado", anchor="w", font=("Segoe UI", 11), bg=INPUT_BG, fg="#AAAAAA", padx=8, pady=4)
    selected_car_label.pack(side="left", fill="x", expand=True)

    ui_label(form_center, "VARIAÇÃO (SKIN)").pack(anchor="w")
    skin_var = tk.StringVar()
    skin_combo = ttk.Combobox(form_center, textvariable=skin_var, state="readonly", values=[], font=("Segoe UI", 11), style="Race.TCombobox")
    skin_combo.pack(fill="x", pady=(2, 12), ipady=4)

    footer_frame = tk.Frame(form_center, bg=BG_COLOR)
    footer_frame.pack(fill="x", pady=(10, 0))

    image_frame = tk.LabelFrame(container, text="PREVIEW DA MÁQUINA", padx=8, pady=8, bg=BG_COLOR, fg=ACCENT_COLOR, font=("Segoe UI", 9, "bold"))
    image_frame.pack(fill="both", expand=True, pady=(10, 0))
    preview_label = tk.Label(image_frame, text="Selecione carro e skin para visualizar.", bg=BG_COLOR, fg="#666666")
    preview_label.pack(fill="both", expand=True)

    image_state = {"preview": None}

    def refresh_preview():
        car_name = car_var.get().strip()
        skin_name = skin_var.get().strip()
        preview_path = find_car_preview_image(assetto_base, car_name, skin_name)

        if not preview_path:
            preview_label.configure(text="Imagem preview não encontrada.", image="", bg=BG_COLOR, fg="#666666")
            image_state["preview"] = None
            return

        try:
            image = Image.open(preview_path)
            # Aumentado para preencher melhor a tela cheia
            image.thumbnail((1200, 700))
            image_tk = ImageTk.PhotoImage(image)
            preview_label.configure(image=image_tk, text="", bg=BG_COLOR)
            image_state["preview"] = image_tk
        except Exception:
            preview_label.configure(text=f"Falha ao carregar imagem: {preview_path}", image="", bg=BG_COLOR, fg=ACCENT_COLOR)
            image_state["preview"] = None

    def open_car_selector():
        selector = tk.Toplevel(root)
        selector.title("Garagem - Escolha seu Carro")
        
        # Tela cheia para o seletor também
        try:
            selector.state('zoomed')
        except tk.TclError:
            selector.attributes('-fullscreen', True)
        selector.bind("<Escape>", lambda e: selector.destroy())

        selector.transient(root)
        selector.grab_set()
        selector.configure(bg=BG_COLOR)

        wrapper = tk.Frame(selector, padx=12, pady=12, bg=BG_COLOR)
        wrapper.pack(fill="both", expand=True)

        tk.Label(wrapper, text="GARAGEM", font=("Impact", 16, "italic"), bg=BG_COLOR, fg=ACCENT_COLOR).pack(anchor="w", pady=(0, 8))

        canvas = tk.Canvas(wrapper, highlightthickness=0, bg=BG_COLOR)
        scroll = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        cards = tk.Frame(canvas, bg=BG_COLOR)

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
            selected_car_label.configure(text=car_name.upper(), fg=FG_COLOR)
            refresh_skins()
            selector.destroy()

        if not cars:
            tk.Label(cards, text="Nenhum carro encontrado na instalação do Assetto Corsa.", bg=BG_COLOR, fg=FG_COLOR).pack(anchor="center", pady=20)
            return

        target_size = (360, 202)  # Cards maiores na garagem tela cheia
        columns = 4
        for index, car_name in enumerate(cars):
            row = index // columns
            column = index % columns

            card = tk.Frame(cards, relief="flat", borderwidth=0, padx=6, pady=6, bg=INPUT_BG)
            card.grid(row=row, column=column, padx=8, pady=8, sticky="nsew")

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
            tk.Label(card, text=car_name.upper(), anchor="center", wraplength=target_size[0], bg=INPUT_BG, fg=FG_COLOR, font=("Segoe UI", 9, "bold")).pack(fill="x", pady=(8, 0))

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

    btn_style = {"bg": ACCENT_COLOR, "fg": FG_COLOR, "font": ("Impact", 10), "relief": "flat", "activebackground": "#F44336", "activeforeground": FG_COLOR}
    tk.Button(car_select_frame, text="SELECIONAR", command=open_car_selector, **btn_style, padx=12).pack(side="right", padx=(10, 0))

    if USER_PROFILE.get("car"):
        car_var.set(USER_PROFILE["car"])
        selected_car_label.configure(text=USER_PROFILE["car"].upper(), fg=FG_COLOR)
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

        profile_payload = {
            "name": name,
            "phone": phone,
            "track": normalize_track_value(track_var.get().strip()) or "drag2000",
            "car": car_var.get().strip(),
            "skin": skin_var.get().strip(),
        }

        if keep_open:
            if callable(on_submit_profile):
                on_submit_profile(profile_payload)

            # Limpa os campos para o próximo piloto sem fechar a interface.
            name_var.set("")
            phone_var.set("")
            track_combo.set(to_track_display("drag2000"))
            car_var.set("")
            selected_car_label.configure(text="Nenhum carro selecionado", fg="#AAAAAA")
            skin_combo["values"] = []
            skin_var.set("")
            refresh_preview()
            name_entry.focus_set()
            return

        result["name"] = profile_payload["name"]
        result["phone"] = profile_payload["phone"]
        result["track"] = profile_payload["track"]
        result["car"] = profile_payload["car"]
        result["skin"] = profile_payload["skin"]
        submitted["ok"] = True
        root.destroy()

    def on_close():
        root.destroy()

    start_btn_style = btn_style.copy()
    start_btn_style["font"] = ("Impact", 14)
    tk.Button(footer_frame, text="▶ INICIAR  ", command=on_submit, **start_btn_style, pady=6, padx=16).pack(anchor="e")

    root.protocol("WM_DELETE_WINDOW", on_close)
    name_entry.focus_set()
    try:
        root.mainloop()
    except KeyboardInterrupt:
        # Permite encerrar a tela com Ctrl+C sem traceback.
        try:
            root.destroy()
        except Exception:
            pass
        return None

    if submitted["ok"]:
        return result

    return None


def collect_user_profile():
    gui_profile = collect_user_profile_gui()
    if gui_profile:
        return gui_profile

    def has_interactive_stdin() -> bool:
        stdin = sys.stdin
        if stdin is None:
            return False
        if getattr(stdin, "closed", False):
            return False
        try:
            return bool(stdin.isatty())
        except Exception:
            return False

    def read_input(prompt: str, default: str = "") -> str:
        try:
            return input(prompt).strip()
        except (EOFError, OSError, ValueError):
            # Alguns ambientes do VS Code podem expor stdin fechado/indisponível.
            return default

    # Em execução sem terminal interativo, usa variáveis de ambiente ou padrão.
    if not has_interactive_stdin():
        config_track = normalize_track_value(os.getenv("CONFIG_TRACK", "drag2000")) or "drag2000"
        return {
            "name": os.getenv("DRIVER_NAME", "Player").strip() or "Player",
            "phone": os.getenv("DRIVER_PHONE", "").strip(),
            "track": config_track,
            "car": os.getenv("DRIVER_CAR", "").strip(),
            "skin": os.getenv("DRIVER_SKIN", "").strip(),
        }

    name = ""
    for _ in range(3):
        name = read_input("Digite seu nome: ", default="")
        if name:
            break
        print("Nome não pode ficar vazio.")
    if not name:
        name = "Player"

    phone = ""
    for _ in range(3):
        phone = read_input("Digite seu número de telefone: ", default="")
        if phone:
            break
        print("Telefone não pode ficar vazio.")

    track = ""
    while True:
        track = read_input("Digite distância da corrida (500, 1000, 2000) [2000]: ", default="")

        track = track or "2000"
        normalized_track = normalize_track_value(track)
        if normalized_track:
            track = normalized_track
            break
        print("Valor inválido para distância. Use 500, 1000 ou 2000 metros.")

    car = read_input("Digite o carro (opcional): ", default="")

    skin = read_input("Digite a skin/variação (opcional): ", default="")

    return {
        "name": name,
        "phone": phone,
        "track": track,
        "car": car,
        "skin": skin,
    }


def apply_profile_updates(profile: dict[str, str]) -> None:
    with PROFILE_UPDATE_LOCK:
        USER_PROFILE.update(profile)

    updated_race_file = update_race_config_in_race_file(USER_PROFILE)
    if updated_race_file:
        print(f"Configuração da corrida atualizada em: {updated_race_file}")
    else:
        print("Não foi possível localizar o arquivo race.ini em Documents\\Assetto Corsa\\cfg.")


def start_persistent_profile_gui() -> None:
    global PROFILE_GUI_STARTED

    if PROFILE_GUI_STARTED:
        return

    def _run_gui():
        try:
            collect_user_profile_gui(keep_open=True, on_submit_profile=apply_profile_updates)
        except Exception as exc:
            print(f"Falha ao iniciar interface contínua de cadastro: {exc}")

    gui_thread = threading.Thread(target=_run_gui, name="profile-gui", daemon=True)
    gui_thread.start()
    PROFILE_GUI_STARTED = True


def ensure_user_profile_initialized():
    global USER_PROFILE_INITIALIZED

    if USER_PROFILE_INITIALIZED:
        return

    profile = collect_user_profile()
    apply_profile_updates(profile)

    started_game, game_message = launch_assetto_corsa_game()
    print(game_message)
    if not started_game:
        print("Dica: verifique se o executável existe em C:/Program Files (x86)/Steam/steamapps/common/assettocorsa")

    start_persistent_profile_gui()

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
                section_text = key_regex.sub(lambda _m: new_line, section_text, count=1)
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
        car_1_updates = {}
        if profile.get("car", "").strip():
            car_0_updates["MODEL"] = profile["car"].strip()
            car_1_updates["MODEL"] = profile["car"].strip()
        if profile.get("skin", "").strip():
            car_0_updates["SKIN"] = profile["skin"].strip()

        if car_1_updates.get("MODEL"):
            assetto_base = find_assetto_base_path()
            available_bot_skins = list_car_skins(assetto_base, car_1_updates["MODEL"])
            if available_bot_skins:
                car_1_updates["SKIN"] = random.choice(available_bot_skins)
            elif profile.get("skin", "").strip():
                # Fallback para evitar CAR_1 sem skin quando não houver lista disponível.
                car_1_updates["SKIN"] = profile["skin"].strip()

        remote_updates = {}
        if profile.get("name", "").strip():
            remote_updates["NAME"] = profile["name"].strip()
        if profile.get("car", "").strip():
            remote_updates["REQUESTED_CAR"] = profile["car"].strip()

        updated_text = text
        if race_updates:
            updated_text = _upsert_ini_section_values(updated_text, "RACE", race_updates)
        updated_text = _upsert_ini_section_values(updated_text, "CAR_0", car_0_updates)
        if car_1_updates:
            updated_text = _upsert_ini_section_values(updated_text, "CAR_1", car_1_updates)
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
            "tempo_atual": "00:15:200",
            "session": AC_DRAG,
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
            "tempo_atual": graphics.currentTime.strip(),
            "session": graphics.session,
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


def close_game_with_alt_f4() -> None:
    try:
        pyautogui = get_pyautogui()
        pyautogui.hotkey("alt", "f4")
        print("Alt+F4 enviado para fechar o jogo.")
    except Exception as exc:
        print(f"Erro ao enviar Alt+F4: {exc}")


def restart_current_program() -> None:
    should_exit_current_process = False
    try:
        env = os.environ.copy()

        # Evita herdar contexto temporário do PyInstaller onefile (
        # ex.: _MEIxxxx/base_library.zip) ao reiniciar o próprio executável.
        if getattr(sys, "frozen", False):
            env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
            for key in (
                "_MEIPASS2",
                "_PYI_APPLICATION_HOME_DIR",
                "_PYI_PARENT_PROCESS_LEVEL",
                "_PYI_SPLASH_IPC",
            ):
                env.pop(key, None)

        if getattr(sys, "frozen", False):
            command = [sys.executable]
        else:
            command = [sys.executable, *sys.argv]

        subprocess.Popen(command, cwd=os.getcwd(), env=env)
        print("Aplicação reiniciada.")
        should_exit_current_process = True
    except Exception as exc:
        print(f"Erro ao reiniciar aplicação: {exc}")
    finally:
        if should_exit_current_process:
            os._exit(0)


def should_close_and_restart(session_type: int, current_time_ms: int, best_time_ms: int) -> bool:
    if RACE_MONITOR_STATE["restart_triggered"]:
        return False

    if session_type != AC_DRAG:
        RACE_MONITOR_STATE["game_started"] = False
        return False

    if current_time_ms > 0:
        RACE_MONITOR_STATE["game_started"] = True

    if not RACE_MONITOR_STATE["game_started"]:
        return False

    if best_time_ms <= 0:
        return False

    if current_time_ms > 0 and current_time_ms < best_time_ms:
        RACE_MONITOR_STATE["restart_triggered"] = True
        return True

    return False

WS_URL = "ws://181.214.95.75:7080/input"

async def send_to_websocket():
    while True:
        try:
            data = get_race_info()

            if data:
                selected_car = USER_PROFILE.get("car") or data["carro"]
                selected_track = USER_PROFILE.get("track") or data.get("pista") or "Unknown"
                try:
                    session_type = int(data.get("session", -1))
                except (TypeError, ValueError):
                    session_type = -1
                current_time_ms = convert_time_to_ms(data["tempo_atual"])
                lap_time_ms = convert_time_to_ms(data["ultima_volta"])
                best_time_ms = convert_time_to_ms(data["melhor_volta"])
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
                            "lapTime": lap_time_ms,
                            "isValid": True
                        },
                        "bestLap": best_time_ms
                    }
                }

                try:
                    async with websockets.connect(WS_URL) as websocket:
                        print("Enviado:", payload)
                        await websocket.send(json.dumps(payload))

                except Exception as e:
                    print("Erro ao enviar websocket:", e)

                if ENABLE_AUTO_RESTART and should_close_and_restart(session_type, current_time_ms, best_time_ms):
                    delay_seconds = 10
                    print(
                        "Condição atingida (AC_DRAG): currentTime menor que bestTime após iniciar o jogo. "
                        f"session={session_type} currentTime={current_time_ms}ms bestTime={best_time_ms}ms"
                    )
                    print(f"Aguardando {delay_seconds:.1f}s antes de fechar o jogo...")
                    await asyncio.sleep(delay_seconds)
                    close_game_with_alt_f4()
                    if ENABLE_APP_RESTART:
                        restart_current_program()
                    else:
                        print("Reinício completo da aplicação desativado. Mantendo processo atual em execução.")
                        RACE_MONITOR_STATE["game_started"] = False
                        RACE_MONITOR_STATE["restart_triggered"] = False
        except Exception as exc:
            # Garante que falhas pontuais não derrubem a task em execução contínua.
            print(f"Erro inesperado no loop websocket: {exc}")

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