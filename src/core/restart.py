import os
import sys
import subprocess


AC_DRAG = 6
RACE_MONITOR_STATE = {
    "game_started": False,
    "restart_triggered": False,
}
ENABLE_AUTO_RESTART = os.getenv("ENABLE_AUTO_RESTART", "1").strip().lower() in {"1", "true", "yes", "on"}
ENABLE_APP_RESTART = os.getenv("ENABLE_APP_RESTART", "0").strip().lower() in {"1", "true", "yes", "on"}


def close_game_with_alt_f4() -> None:
    try:
        import pyautogui
        pyautogui.hotkey("alt", "f4")
        print("Alt+F4 enviado para fechar o jogo.")
    except Exception as exc:
        print(f"Erro ao enviar Alt+F4: {exc}")


def restart_current_program() -> None:
    should_exit_current_process = False
    try:
        env = os.environ.copy()

        # Evita herdar contexto temporÃ¡rio do PyInstaller onefile (
        # ex.: _MEIxxxx/base_library.zip) ao reiniciar o prÃ³prio executÃ¡vel.
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
        print("AplicaÃ§Ã£o reiniciada.")
        should_exit_current_process = True
    except Exception as exc:
        print(f"Erro ao reiniciar aplicaÃ§Ã£o: {exc}")
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

