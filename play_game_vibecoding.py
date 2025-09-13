# app.py
# Streamlit Labirent Altın Oyunu — Renkli Grid (yalnızca "streamlit" gerekir)
# Çalıştır: streamlit run app.py

import random
from typing import List, Tuple
import streamlit as st

# =========================
# Varsayılan Oyun Ayarları
# =========================
DEFAULT_W, DEFAULT_H = 25, 15
DEFAULT_GOLD = 18
DEFAULT_STEPS = 250
SEED = None  # aynı labirent için sayı ver (örn. 42)

# Mantık Sembolleri
WALL  = '#'
FLOOR = ' '
GOLD  = 'G'    # iç mantıkta 'G' (görselde altın ikonu/renkli hücreye dönüşüyor)
PLAYER= 'P'

# -------------------------
# Labirent Oluşturma
# -------------------------
def in_bounds(x, y, w, h):
    return 0 <= x < w and 0 <= y < h

def neighbors_cells(x, y):
    # 2 hücre atlayarak (maze carving için)
    return [(x, y-2), (x, y+2), (x-2, y), (x+2, y)]

def carve_passage(maze: List[List[str]], start: Tuple[int,int]):
    stack = [start]
    w, h = len(maze[0]), len(maze)
    while stack:
        x, y = stack[-1]
        maze[y][x] = FLOOR
        nbrs = neighbors_cells(x, y)
        random.shuffle(nbrs)
        moved = False
        for nx, ny in nbrs:
            if in_bounds(nx, ny, w, h) and maze[ny][nx] == WALL:
                wx, wy = (x + nx)//2, (y + ny)//2
                maze[wy][wx] = FLOOR
                maze[ny][nx] = FLOOR
                stack.append((nx, ny))
                moved = True
                break
        if not moved:
            stack.pop()

def make_maze(w: int, h: int) -> List[List[str]]:
    # tek sayıya indir (koridor yapısı için ideal)
    if w % 2 == 0: w -= 1
    if h % 2 == 0: h -= 1
    m = [[WALL for _ in range(w)] for _ in range(h)]
    carve_passage(m, (1, 1))
    return m

def empty_cells(maze):
    cells = []
    for y, row in enumerate(maze):
        for x, ch in enumerate(row):
            if ch == FLOOR:
                cells.append((x, y))
    return cells

def place_items(maze, symbol, count, forbid=set()):
    cells = [c for c in empty_cells(maze) if c not in forbid]
    random.shuffle(cells)
    placed = []
    for i in range(min(count, len(cells))):
        x, y = cells[i]
        maze[y][x] = symbol
        placed.append((x, y))
    return placed

def count_gold(maze):
    return sum(ch == GOLD for row in maze for ch in row)

def move_if_possible(maze, px, py, dx, dy):
    nx, ny = px + dx, py + dy
    w, h = len(maze[0]), len(maze)
    if not in_bounds(nx, ny, w, h):
        return px, py, 0
    if maze[ny][nx] == WALL:
        return px, py, 0
    gain = 0
    if maze[ny][nx] == GOLD:
        gain = 10
        maze[ny][nx] = FLOOR
    return nx, ny, gain

# -------------------------
# HTML/CSS Grid Renderer
# -------------------------
def render_grid_html(maze, px, py, cell_px=28, rounded=True, show_coords=False):
    """
    Renkli karelerle labirenti çizer (CSS grid).
    """
    h = len(maze)
    w = len(maze[0])
    r = 8 if rounded else 2

    # Renk paleti
    COLOR_BG   = "#0b1021"   # panel arkası
    COLOR_WALL = "#263238"   # duvar (koyu gri-mavi)
    COLOR_FLOOR= "#121826"   # zemin (daha koyu)
    COLOR_GOLD = "#FFD54F"   # altın (sarı)
    COLOR_PLAYER = "#26A69A" # oyuncu (turkuaz)

    # Tek bir hücre için stil fonksiyonu
    def cell_style(bg, border="#0e142b"):
        return (
            f"width:{cell_px}px;height:{cell_px}px;"
            f"background:{bg};border:1px solid {border};"
            f"border-radius:{r}px;display:flex;align-items:center;justify-content:center;"
            f"font-weight:600;color:#0b1021;"
        )

    # Izgara kapsayıcısı
    html = [
        f"""
        <div style="background:{COLOR_BG}; padding:12px; border-radius:14px; overflow:auto;">
          <div style="
            display:grid;
            grid-template-columns: repeat({w}, {cell_px}px);
            grid-auto-rows: {cell_px}px;
            gap:4px;
          ">
        """
    ]

    # Hücreleri çiz
    for y in range(h):
        for x in range(w):
            if (x, y) == (px, py):
                html.append(f'<div title="Player" style="{cell_style(COLOR_PLAYER)}">🏃</div>')
            else:
                ch = maze[y][x]
                if ch == WALL:
                    html.append(f'<div title="Wall" style="{cell_style(COLOR_WALL)}"></div>')
                elif ch == GOLD:
                    # Parlak altın
                    html.append(
                        f'<div title="Gold" style="{cell_style(COLOR_GOLD, border="#f1c644")}">★</div>'
                    )
                else:  # FLOOR
                    if show_coords:
                        html.append(f'<div style="{cell_style(COLOR_FLOOR)}"><span style="font-size:10px;opacity:.5">{x},{y}</span></div>')
                    else:
                        html.append(f'<div title="Floor" style="{cell_style(COLOR_FLOOR)}"></div>')

    html.append("</div></div>")
    return "\n".join(html)

# -------------------------
# Oyun Başlatma / State
# -------------------------
def init_game(w, h, gold_count, step_limit, seed=None):
    if seed is not None:
        random.seed(seed)
    maze = make_maze(w, h)
    start = random.choice(empty_cells(maze))
    px, py = start
    place_items(maze, GOLD, gold_count, forbid={start})

    return {
        "maze": maze,
        "px": px, "py": py,
        "score": 0,
        "steps_left": step_limit,
        "game_over": False,
        "win": False,
    }

# =========================
# Streamlit Arayüz
# =========================
st.set_page_config(page_title="Labirent Altın Oyunu", page_icon="✨", layout="wide")
st.title("✨ Labirent Altın Avı — Renkli Sürüm")
st.caption("W/A/S/D veya yön butonlarıyla hareket et. Altınları topla, adım dolmadan en yüksek skoru yap!")

# Sol panel: Ayarlar
with st.sidebar:
    st.header("⚙️ Ayarlar")
    with st.expander("Labirent Seçenekleri", expanded=True):
        w = st.slider("Genişlik (tek sayı önerilir)", 15, 51, DEFAULT_W, step=2)
        h = st.slider("Yükseklik (tek sayı önerilir)", 9, 31, DEFAULT_H, step=2)
        gold_n = st.slider("Altın Sayısı", 5, 100, DEFAULT_GOLD, step=1)
        steps = st.slider("Adım Limiti", 50, 600, DEFAULT_STEPS, step=10)
        seed_str = st.text_input("Seed (opsiyonel, aynı labirent için)", value=str(SEED) if SEED is not None else "")
    with st.expander("Görsel", expanded=True):
        cell_px = st.slider("Hücre Boyutu (px)", 18, 48, 28, step=2)
        rounded = st.checkbox("Yuvarlak köşeler", value=True)
        show_coords = st.checkbox("Koordinasyon (debug)", value=False)

# İlk yüklemede state kur
if "maze" not in st.session_state:
    st.session_state.update(init_game(w, h, gold_n, steps, None))

# Üst metrikler
col1, col2, col3, col4 = st.columns([1,1,1,1])
col1.metric("Skor", st.session_state["score"])
col2.metric("Kalan Adım", st.session_state["steps_left"])
col3.metric("Kalan Altın", count_gold(st.session_state["maze"]))
col4.write("")  # boşluk

# Grid render
grid_html = render_grid_html(
    st.session_state["maze"],
    st.session_state["px"],
    st.session_state["py"],
    cell_px=cell_px,
    rounded=rounded,
    show_coords=show_coords,
)
st.markdown(grid_html, unsafe_allow_html=True)

# Hareket fonksiyonu
def do_move(dx, dy):
    if st.session_state["game_over"]:
        return
    nx, ny, gain = move_if_possible(
        st.session_state["maze"],
        st.session_state["px"],
        st.session_state["py"],
        dx, dy
    )
    if (nx, ny) != (st.session_state["px"], st.session_state["py"]):
        st.session_state["px"], st.session_state["py"] = nx, ny
        st.session_state["score"] += gain
        st.session_state["steps_left"] -= 1

    # bitiş kontrolü
    if count_gold(st.session_state["maze"]) == 0:
        st.session_state["game_over"] = True
        st.session_state["win"] = True
    elif st.session_state["steps_left"] <= 0:
        st.session_state["game_over"] = True
        st.session_state["win"] = False

# Kontroller
st.subheader("🎮 Kontroller")
k1, k2, k3 = st.columns([1,1,1])
with k2:
    st.button("⬆️ Yukarı (W)", use_container_width=True, on_click=lambda: do_move(0, -1))
r1, r2, r3 = st.columns([1,1,1])
with r1:
    st.button("⬅️ Sol (A)", use_container_width=True, on_click=lambda: do_move(-1, 0))
with r3:
    st.button("➡️ Sağ (D)", use_container_width=True, on_click=lambda: do_move(1, 0))
k4, k5, k6 = st.columns([1,1,1])
with k5:
    st.button("⬇️ Aşağı (S)", use_container_width=True, on_click=lambda: do_move(0, 1))

# Klavye ile (Enter'a bas)
key_in = st.text_input("Klavye ile oyna (w/a/s/d yazıp Enter'a bas):", value="", max_chars=1).strip().lower()
if key_in in ["w", "a", "s", "d"]:
    if key_in == "w": do_move(0, -1)
    if key_in == "s": do_move(0,  1)
    if key_in == "a": do_move(-1, 0)
    if key_in == "d": do_move( 1, 0)
    st.session_state["__tick__"] = st.session_state.get("__tick__", 0) + 1
    st.experimental_rerun()

# Son durum
if st.session_state["game_over"]:
    if st.session_state["win"]:
        st.success(f"🎉 Tüm altınlar toplandı! Final Skorun: {st.session_state['score']}")
    else:
        st.error(f"⏳ Adımlar bitti. Toplanan Altın: {st.session_state['score']//10} | Final Skor: {st.session_state['score']}")

# Yeni Oyun / Yeni Labirent
a, b = st.columns(2)
with a:
    if st.button("🔁 Aynı Ayarlarla Yeni Oyun", use_container_width=True):
        # aynı ayarlarla (seed varsa tekrar kullan)
        s = None
        if seed_str.strip().isdigit():
            s = int(seed_str.strip())
        st.session_state.update(init_game(w, h, gold_n, steps, s))
        st.experimental_rerun()
with b:
    if st.button("🎲 Tümü Rastgele (Yeni Labirent)", use_container_width=True):
        st.session_state.update(init_game(w, h, gold_n, steps, None))
        st.experimental_rerun()

# Küçük efsane
st.caption("İpucu: Hücre boyutunu büyütüp (soldaki ayarlardan) daha net bir görünüm elde edebilirsin.")
