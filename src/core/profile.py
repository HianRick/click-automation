from typing import Optional
import os
import re
import sys
import random
import subprocess
import threading
from pathlib import Path


USER_PROFILE = {
    "name": "Player",
    "phone": "",
    "track": "drag2000",
    "car": "",
    "skin": "",
    "auto_shifter": "1",
}
USER_PROFILE_INITIALIZED = False
PROFILE_GUI_STARTED = False
PROFILE_UPDATE_LOCK = threading.Lock()
RACE_INI_PATH = Path.home() / "Documents" / "Assetto Corsa" / "cfg" / "race.ini"
ASSISTS_INI_PATH = Path.home() / "Documents" / "Assetto Corsa" / "cfg" / "assists.ini"
AC_DRAG = 6
TRACK_CONFIG_TO_DISPLAY = {
    "drag500": "500 metros",
    "drag1000": "1000 metros",
    "drag2000": "2000 metros",
    "livre": "livre",
}
TRACK_DISPLAY_TO_CONFIG = {value: key for key, value in TRACK_CONFIG_TO_DISPLAY.items()}
SHIFTER_MODE_TO_DISPLAY = {
    "0": "manual",
    "1": "automatico",
}
SHIFTER_DISPLAY_TO_MODE = {value: key for key, value in SHIFTER_MODE_TO_DISPLAY.items()}
RACE_MONITOR_STATE = {
    "game_started": False,
    "restart_triggered": False,
}
ENABLE_AUTO_RESTART = os.getenv("ENABLE_AUTO_RESTART", "1").strip().lower() in {"1", "true", "yes", "on"}
ENABLE_APP_RESTART = os.getenv("ENABLE_APP_RESTART", "0").strip().lower() in {"1", "true", "yes", "on"}
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def get_resource_path(relative_path: str) -> Path:
    base_dir = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
    return base_dir / relative_path


def normalize_track_value(value: str) -> str:
    normalized = (value or "").strip().lower().replace("m", "").replace("metros", "").strip()
    if normalized in {"500", "1000", "2000"}:
        return f"drag{normalized}"
    if normalized in {"livre", "free"}:
        return "livre"
    if value in TRACK_DISPLAY_TO_CONFIG:
        return TRACK_DISPLAY_TO_CONFIG[value]
    if value in TRACK_CONFIG_TO_DISPLAY:
        return value
    return ""


def to_track_display(track_config: str) -> str:
    return TRACK_CONFIG_TO_DISPLAY.get(track_config, TRACK_CONFIG_TO_DISPLAY["drag2000"])


def normalize_auto_shifter_value(value: str) -> str:
    normalized = (value or "").strip().lower()
    if normalized in {"0", "manual"}:
        return "0"
    if normalized in {"1", "automatico", "automÃ¡tico", "auto", "automatic"}:
        return "1"
    if value in SHIFTER_DISPLAY_TO_MODE:
        return SHIFTER_DISPLAY_TO_MODE[value]
    if value in SHIFTER_MODE_TO_DISPLAY:
        return value
    return "1"


def to_shifter_display(shifter_mode: str) -> str:
    normalized_mode = normalize_auto_shifter_value(shifter_mode)
    return SHIFTER_MODE_TO_DISPLAY.get(normalized_mode, "automatico")


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
    # Prioriza o caminho informado e tenta nomes comuns de executÃ¡vel.
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

    return False, "NÃ£o foi encontrado acs.exe/AssettoCorsa.exe no diretÃ³rio do Assetto Corsa."


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
    cars = list_assetto_dirs(assetto_base, "cars")

    root = tk.Tk()
    root.title("IdentificaÃ§Ã£o do Piloto")
    
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

    # Logos no topo (logo + logo2 lado a lado, centralizadas)
    logo_frame = tk.Frame(root, bg=BG_COLOR)
    logo_images = []

    def _append_logo(image_path: Path, max_logo_size: tuple[int, int]):
        if not image_path.exists():
            return

        try:
            logo_img = Image.open(image_path)
            # Redimensiona mantendo aspecto, inclusive ampliando quando a arte original e menor.
            original_width, original_height = logo_img.size
            if original_width > 0 and original_height > 0:
                scale = min(
                    max_logo_size[0] / original_width,
                    max_logo_size[1] / original_height,
                )
                new_size = (
                    max(1, int(original_width * scale)),
                    max(1, int(original_height * scale)),
                )
                logo_img = logo_img.resize(new_size, Image.Resampling.LANCZOS)

            logo_tk = ImageTk.PhotoImage(logo_img)
            logo_images.append(logo_tk)
            tk.Label(logo_frame, image=logo_tk, bg=BG_COLOR).pack(side="left", padx=12)
        except Exception:
            pass

    _append_logo(get_resource_path("assets/logo.png"), (520, 220))
    _append_logo(get_resource_path("assets/logo2.png"), (320, 220))

    if logo_images:
        logo_frame.pack(pady=(20, 10))
        logo_frame.logo_images = logo_images  # Previne GC

    container = tk.Frame(root, padx=20, pady=10, bg=BG_COLOR)
    container.pack(fill="both", expand=True, pady=(24, 0))

    tk.Label(container, text="PREPARE-SE PARA A CORRIDA", font=("Impact", 18, "italic"), bg=BG_COLOR, fg=ACCENT_COLOR).pack(anchor="n", pady=(0, 20))

    # Limitar largura dos formulÃ¡rios centralizados
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

    ui_label(form_center, "DISTÃ‚NCIA DE DRAG").pack(anchor="w")
    track_var = tk.StringVar(value=to_track_display(USER_PROFILE.get("track", "drag2000")))
    track_buttons_frame = tk.Frame(form_center, bg=BG_COLOR)
    track_buttons_frame.pack(fill="x", pady=(2, 12))
    track_buttons = {}

    def set_selected_track(track_label: str):
        track_var.set(track_label)
        for option, button in track_buttons.items():
            is_selected = option == track_label
            button.configure(
                bg=ACCENT_COLOR if is_selected else INPUT_BG,
                fg=FG_COLOR,
                activebackground="#F44336" if is_selected else "#3A3A3A",
                relief="flat",
            )

    for option in ("500 metros", "1000 metros", "2000 metros", "livre"):
        button = tk.Button(
            track_buttons_frame,
            text=option,
            command=lambda value=option: set_selected_track(value),
            bg=INPUT_BG,
            fg=FG_COLOR,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=10,
            pady=6,
            activeforeground=FG_COLOR,
        )
        button.pack(side="left", expand=True, fill="x", padx=4)
        track_buttons[option] = button

    set_selected_track(track_var.get())

    ui_label(form_center, "CÃ‚MBIO").pack(anchor="w")
    shifter_var = tk.StringVar(value=to_shifter_display(USER_PROFILE.get("auto_shifter", "1")))
    shifter_buttons_frame = tk.Frame(form_center, bg=BG_COLOR)
    shifter_buttons_frame.pack(fill="x", pady=(2, 12))
    shifter_buttons = {}

    def set_selected_shifter(shifter_label: str):
        shifter_var.set(shifter_label)
        for option, button in shifter_buttons.items():
            is_selected = option == shifter_label
            button.configure(
                bg=ACCENT_COLOR if is_selected else INPUT_BG,
                fg=FG_COLOR,
                activebackground="#F44336" if is_selected else "#3A3A3A",
                relief="flat",
            )

    for option in ("manual", "automatico"):
        button = tk.Button(
            shifter_buttons_frame,
            text=option.upper(),
            command=lambda value=option: set_selected_shifter(value),
            bg=INPUT_BG,
            fg=FG_COLOR,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            padx=10,
            pady=6,
            activeforeground=FG_COLOR,
        )
        button.pack(side="left", expand=True, fill="x", padx=4)
        shifter_buttons[option] = button

    set_selected_shifter(shifter_var.get())

    car_var = tk.StringVar()

    ui_label(form_center, "CARRO").pack(anchor="w")
    car_select_frame = tk.Frame(form_center, bg=BG_COLOR)
    car_select_frame.pack(fill="x", pady=(2, 12))
    selected_car_label = tk.Label(car_select_frame, text="Nenhum carro selecionado", anchor="w", font=("Segoe UI", 11), bg=INPUT_BG, fg="#AAAAAA", padx=8, pady=4)
    selected_car_label.pack(side="left", fill="x", expand=True)

    ui_label(form_center, "VARIAÃ‡ÃƒO (SKIN)").pack(anchor="w")
    skin_var = tk.StringVar()
    skin_combo = ttk.Combobox(form_center, textvariable=skin_var, state="readonly", values=[], font=("Segoe UI", 11), style="Race.TCombobox")
    skin_combo.pack(fill="x", pady=(2, 12), ipady=4)

    footer_frame = tk.Frame(form_center, bg=BG_COLOR)
    footer_frame.pack(fill="x", pady=(10, 0))

    image_frame = tk.LabelFrame(container, text="PREVIEW DA MÃQUINA", padx=8, pady=8, bg=BG_COLOR, fg=ACCENT_COLOR, font=("Segoe UI", 9, "bold"))
    image_frame.pack(fill="x", expand=False, pady=(10, 0))
    image_frame.configure(height=420)
    image_frame.pack_propagate(False)
    preview_label = tk.Label(image_frame, text="Selecione carro e skin para visualizar.", bg=BG_COLOR, fg="#666666")
    preview_label.pack(fill="both", expand=True)

    image_state = {"preview": None}

    def refresh_preview():
        car_name = car_var.get().strip()
        skin_name = skin_var.get().strip()
        preview_path = find_car_preview_image(assetto_base, car_name, skin_name)

        if not preview_path:
            preview_label.configure(text="Imagem preview nÃ£o encontrada.", image="", bg=BG_COLOR, fg="#666666")
            image_state["preview"] = None
            return

        try:
            image = Image.open(preview_path)
            # MantÃ©m preview menor para nÃ£o dominar a primeira tela.
            image.thumbnail((840, 420))
            image_tk = ImageTk.PhotoImage(image)
            preview_label.configure(image=image_tk, text="", bg=BG_COLOR)
            image_state["preview"] = image_tk
        except Exception:
            preview_label.configure(text=f"Falha ao carregar imagem: {preview_path}", image="", bg=BG_COLOR, fg=ACCENT_COLOR)
            image_state["preview"] = None

    def open_car_selector():
        selector = tk.Toplevel(root)
        selector.title("Garagem - Escolha seu Carro")
        
        # Prioriza fullscreen real para manter a mesma experiÃªncia da tela principal.
        try:
            selector.attributes('-fullscreen', True)
        except tk.TclError:
            selector.state('zoomed')
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
        target_size = (360, 202)  # Cards maiores na garagem tela cheia
        columns = 4

        cards.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        cards_window_id = canvas.create_window((0, 0), window=cards, anchor="n")

        def recenter_cards(_event=None):
            total_columns = min(columns, len(cars)) if cars else 1
            card_width = target_size[0] + 16
            total_width = (total_columns * card_width) + (max(total_columns - 1, 0) * 16)
            canvas_width = canvas.winfo_width()
            x = max((canvas_width - total_width) // 2, 0)
            canvas.coords(cards_window_id, x, 0)

        def on_mouse_wheel(event):
            if event.delta:
                canvas.yview_scroll(int(-event.delta / 120), "units")
            elif event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")

        def bind_scroll_events(widget):
            widget.bind("<MouseWheel>", on_mouse_wheel)
            widget.bind("<Button-4>", on_mouse_wheel)
            widget.bind("<Button-5>", on_mouse_wheel)

        canvas.bind("<Configure>", recenter_cards)
        bind_scroll_events(canvas)
        bind_scroll_events(cards)

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
            tk.Label(cards, text="Nenhum carro encontrado na instalaÃ§Ã£o do Assetto Corsa.", bg=BG_COLOR, fg=FG_COLOR).pack(anchor="center", pady=20)
            return

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
            car_title = tk.Label(card, text=car_name.upper(), anchor="center", wraplength=target_size[0], bg=INPUT_BG, fg=FG_COLOR, font=("Segoe UI", 9, "bold"))
            car_title.pack(fill="x", pady=(8, 0))

            bind_scroll_events(card)
            bind_scroll_events(image_button)
            bind_scroll_events(car_title)

        for col in range(columns):
            cards.grid_columnconfigure(col, weight=1)

        recenter_cards()

        # MantÃ©m as referÃªncias das imagens para evitar coleta de lixo do Tkinter.
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
            messagebox.showwarning("Campo obrigatÃ³rio", "Digite o nome do piloto.")
            return

        if not phone:
            messagebox.showwarning("Campo obrigatÃ³rio", "Digite o nÃºmero de telefone.")
            return

        profile_payload = {
            "name": name,
            "phone": phone,
            "track": normalize_track_value(track_var.get().strip()) or "drag2000",
            "car": car_var.get().strip(),
            "skin": skin_var.get().strip(),
            "auto_shifter": normalize_auto_shifter_value(shifter_var.get().strip()),
        }

        if keep_open:
            if callable(on_submit_profile):
                on_submit_profile(profile_payload)

            # Ao clicar em INICIAR, tenta abrir o jogo para o prÃ³ximo piloto.
            started_game, game_message = launch_assetto_corsa_game()
            print(game_message)
            if not started_game:
                print("Dica: verifique se o executÃ¡vel existe em C:/Program Files (x86)/Steam/steamapps/common/assettocorsa")

            # Limpa os campos para o prÃ³ximo piloto sem fechar a interface.
            name_var.set("")
            phone_var.set("")
            set_selected_track(to_track_display("drag2000"))
            set_selected_shifter(to_shifter_display("1"))
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
        result["auto_shifter"] = profile_payload["auto_shifter"]
        submitted["ok"] = True
        root.destroy()

    def on_close():
        root.destroy()

    start_btn_style = btn_style.copy()
    start_btn_style["font"] = ("Impact", 14)
    tk.Button(footer_frame, text="â–¶ INICIAR  ", command=on_submit, **start_btn_style, pady=6, padx=16).pack(anchor="e")

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


def collect_user_profile() -> Optional[dict[str, str]]:
    gui_profile = collect_user_profile_gui()
    if gui_profile:
        return gui_profile

    # Cadastro obrigatÃ³rio para jogar: sem submit, nÃ£o inicia o jogo.
    return None


def apply_profile_updates(profile: dict[str, str]) -> None:
    with PROFILE_UPDATE_LOCK:
        USER_PROFILE.update(profile)

    updated_race_file = update_race_config_in_race_file(USER_PROFILE)
    updated_assists_file = update_assists_config_file(USER_PROFILE)
    if updated_race_file:
        print(f"ConfiguraÃ§Ã£o da corrida atualizada em: {updated_race_file}")
    else:
        print("NÃ£o foi possÃ­vel localizar o arquivo race.ini em Documents\\Assetto Corsa\\cfg.")

    if updated_assists_file:
        print(f"ConfiguraÃ§Ã£o de assists atualizada em: {updated_assists_file}")
    else:
        print("NÃ£o foi possÃ­vel localizar o arquivo assists em Documents\\Assetto Corsa\\cfg.")


def start_persistent_profile_gui() -> None:
    global PROFILE_GUI_STARTED

    if PROFILE_GUI_STARTED:
        return

    def _run_gui():
        try:
            collect_user_profile_gui(keep_open=True, on_submit_profile=apply_profile_updates)
        except Exception as exc:
            print(f"Falha ao iniciar interface contÃ­nua de cadastro: {exc}")

    gui_thread = threading.Thread(target=_run_gui, name="profile-gui", daemon=True)
    gui_thread.start()
    PROFILE_GUI_STARTED = True


def ensure_user_profile_initialized():
    global USER_PROFILE_INITIALIZED

    if USER_PROFILE_INITIALIZED:
        return

    profile = collect_user_profile()
    if not profile:
        print("Cadastro obrigatÃ³rio: preencha o formulÃ¡rio e clique em INICIAR para abrir o jogo.")
        start_persistent_profile_gui()
        USER_PROFILE_INITIALIZED = True
        return

    apply_profile_updates(profile)

    started_game, game_message = launch_assetto_corsa_game()
    print(game_message)
    if not started_game:
        print("Dica: verifique se o executÃ¡vel existe em C:/Program Files (x86)/Steam/steamapps/common/assettocorsa")

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


def _remove_ini_section_keys(text: str, section_name: str, keys: set[str]) -> str:
    if not keys:
        return text

    section_regex = re.compile(rf"(?ms)^\[{re.escape(section_name)}\]\s*$.*?(?=^\[|\Z)")
    section_match = section_regex.search(text)
    if not section_match:
        return text

    section_text = section_match.group(0)
    for key in keys:
        key_regex = re.compile(rf"(?m)^\s*{re.escape(key)}\s*=.*(?:\r?\n)?")
        section_text = key_regex.sub("", section_text)

    return f"{text[:section_match.start()]}{section_text}{text[section_match.end():]}"


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
        selected_track = profile.get("track", "").strip()
        drag_track_configs = {"drag500", "drag1000", "drag2000"}
        session_updates = {}
        session_keys_to_remove = set()
        if selected_track == "livre":
            race_updates["TRACK"] = "vhe_velopark"
            race_updates["CONFIG_TRACK"] = "standard"
            session_updates = {
                "NAME": "Practice",
                "TYPE": "1",
                "DURATION_MINUTES": "0",
                "SPAWN_SET": "PIT",
            }
            session_keys_to_remove = {"MATCHES"}
        elif selected_track:
            race_updates["TRACK"] = "ks_drag"
            race_updates["CONFIG_TRACK"] = selected_track if selected_track in drag_track_configs else "drag2000"
            race_updates["CARS"] = "2"
            session_updates = {
                "NAME": "Drag Race",
                "TYPE": "7",
                "SPAWN_SET": "START",
                "MATCHES": "2",
            }
            session_keys_to_remove = {"DURATION_MINUTES"}
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
                # Fallback para evitar CAR_1 sem skin quando nÃ£o houver lista disponÃ­vel.
                car_1_updates["SKIN"] = profile["skin"].strip()

        remote_updates = {}
        if profile.get("name", "").strip():
            remote_updates["NAME"] = profile["name"].strip()
        if profile.get("car", "").strip():
            remote_updates["REQUESTED_CAR"] = profile["car"].strip()

        updated_text = text
        if race_updates:
            updated_text = _upsert_ini_section_values(updated_text, "RACE", race_updates)
        if session_updates:
            updated_text = _upsert_ini_section_values(updated_text, "SESSION_0", session_updates)
            updated_text = _remove_ini_section_keys(updated_text, "SESSION_0", session_keys_to_remove)
        updated_text = _upsert_ini_section_values(updated_text, "CAR_0", car_0_updates)
        if car_1_updates:
            updated_text = _upsert_ini_section_values(updated_text, "CAR_1", car_1_updates)
        if remote_updates:
            updated_text = _upsert_ini_section_values(updated_text, "REMOTE", remote_updates)

        race_file.write_text(updated_text, encoding=encoding_used)
        return race_file

    return None


def update_assists_config_file(profile: dict[str, str]) -> Optional[Path]:
    if ASSISTS_INI_PATH.is_file():
        candidate_paths = [ASSISTS_INI_PATH]
    else:
        candidate_paths = []

    base_path = Path.home() / "Documents" / "Assetto Corsa"
    candidate_dirs = [
        base_path / "cng",
        base_path / "cfg",
        base_path,
    ]
    candidate_files = ["assists", "assists.ini"]

    for directory in candidate_dirs:
        for file_name in candidate_files:
            assists_file = directory / file_name
            if assists_file not in candidate_paths:
                candidate_paths.append(assists_file)

    auto_shifter_value = normalize_auto_shifter_value(profile.get("auto_shifter", "1"))

    for assists_file in candidate_paths:
        if not assists_file.is_file():
            continue

        text = None
        encoding_used = "utf-8"
        for enc in ("utf-8", "latin-1"):
            try:
                text = assists_file.read_text(encoding=enc)
                encoding_used = enc
                break
            except Exception:
                continue

        if text is None:
            continue

        line_break = "\r\n" if "\r\n" in text else "\n"
        auto_shifter_line = f"AUTO_SHIFTER={auto_shifter_value}"
        auto_shifter_regex = re.compile(r"(?m)^\s*AUTO_SHIFTER\s*=.*$")

        if auto_shifter_regex.search(text):
            updated_text = auto_shifter_regex.sub(auto_shifter_line, text, count=1)
        else:
            updated_text = f"{text.rstrip()}{line_break}{auto_shifter_line}{line_break}" if text.strip() else f"{auto_shifter_line}{line_break}"

        assists_file.write_text(updated_text, encoding=encoding_used)
        return assists_file

    return None



