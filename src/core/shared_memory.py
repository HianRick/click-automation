import ctypes
import mmap


AC_DRAG = 6


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
        return None  # jogo provavelmente nÃ£o estÃ¡ aberto

graphics_map = None
static_map = None

#True para usar dados mockados quando a memÃ³ria compartilhada nÃ£o estiver disponÃ­vel
#False para quando tiver o jogo rodando e quiser os dados reais
USE_MOCK = False
def initialize_shared_memory():
    global graphics_map, static_map
    graphics_map = open_shared_memory("acpmf_graphics", ctypes.sizeof(SPageFileGraphics))
    static_map = open_shared_memory("acpmf_static", ctypes.sizeof(SPageFileStatic))
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


