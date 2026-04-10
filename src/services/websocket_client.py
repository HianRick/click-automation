import asyncio
import json
import websockets

from src.core.profile import USER_PROFILE, normalize_auto_shifter_value, to_shifter_display
from src.core.shared_memory import get_race_info, convert_time_to_ms
from src.core.restart import (
    ENABLE_AUTO_RESTART,
    ENABLE_APP_RESTART,
    RACE_MONITOR_STATE,
    should_close_and_restart,
    close_game_with_alt_f4,
    restart_current_program,
)


WS_URL = "ws://181.214.95.75:7080/input"

async def send_to_websocket():
    while True:
        try:
            data = get_race_info()

            if data:
                selected_car = USER_PROFILE.get("car") or data["carro"]
                selected_track = USER_PROFILE.get("track") or data.get("pista") or "Unknown"
                selected_shifter_mode = normalize_auto_shifter_value(USER_PROFILE.get("auto_shifter", "1"))
                selected_shifter_type = to_shifter_display(selected_shifter_mode)
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
                        "phone": USER_PROFILE["phone"],
                        "car": selected_car,
                        "track": selected_track,
                        "skin": USER_PROFILE.get("skin") or "",
                        "shifter": selected_shifter_type,
                        "autoShifter": selected_shifter_mode,
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
                        "CondiÃ§Ã£o atingida (AC_DRAG): currentTime menor que bestTime apÃ³s iniciar o jogo. "
                        f"session={session_type} currentTime={current_time_ms}ms bestTime={best_time_ms}ms"
                    )
                    print(f"Aguardando {delay_seconds:.1f}s antes de fechar o jogo...")
                    await asyncio.sleep(delay_seconds)
                    close_game_with_alt_f4()
                    if ENABLE_APP_RESTART:
                        restart_current_program()
                    else:
                        print("Jogo fechado. Aguardando novo preenchimento do formulÃ¡rio para iniciar novamente.")
                        RACE_MONITOR_STATE["game_started"] = False
                        RACE_MONITOR_STATE["restart_triggered"] = False
        except Exception as exc:
            # Garante que falhas pontuais nÃ£o derrubem a task em execuÃ§Ã£o contÃ­nua.
            print(f"Erro inesperado no loop websocket: {exc}")

        await asyncio.sleep(1)  # envia a cada 1 segundo


