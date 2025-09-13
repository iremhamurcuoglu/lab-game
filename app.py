# app.py
import streamlit as st

st.set_page_config(page_title="Labirent Altın Oyunu", layout="wide")

# Constants for colors
BG = "#0B1021"
FLOOR = "#121826"
WALL = "#263238"
GOLD = "#FFD54F"
PLAYER = "#26A69A"

# ------------------------------------------------------------------
# Helpers and required functions
# ------------------------------------------------------------------

def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))

class SimpleRNG:
    """A tiny deterministic LCG RNG (no external imports)."""
    def __init__(self, seed: int | None = None):
        if seed is None:
            # Try to get a varying seed using the object's id/hash
            seed = abs(hash(str(id(object())))) & 0xFFFFFFFF
        self.state = int(seed) & 0xFFFFFFFF
    def rand(self) -> int:
        # LCG parameters
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        return self.state
    def randrange(self, n: int) -> int:
        if n <= 0:
            return 0
        return self.rand() % n
    def choice(self, seq):
        return seq[self.randrange(len(seq))]

def in_bounds(w: int, h: int, x: int, y: int) -> bool:
    """Return True if (x,y) is within grid bounds."""
    return 0 <= x < w and 0 <= y < h

def empty_cells(maze: list[list[str]]) -> list[tuple[int,int]]:
    """Return list of coordinates of floor cells (not walls)."""
    res = []
    h = len(maze)
    w = len(maze[0]) if h else 0
    for y in range(h):
        for x in range(w):
            if maze[y][x] == ' ':
                res.append((x,y))
    return res

def place_items(maze: list[list[str]], cells: list[tuple[int,int]], rng: SimpleRNG, item: str, count: int):
    """Place `item` into `count` random distinct cells from `cells`."""
    if not cells or count <= 0:
        return
    available = cells[:]
    placed = 0
    while placed < count and available:
        idx = rng.randrange(len(available))
        x,y = available.pop(idx)
        # avoid placing on already placed or non-floor
        if maze[y][x] == ' ':
            maze[y][x] = item
            placed += 1

def make_maze(w: int, h: int) -> list[list[str]]:
    """
    make_maze(w: int, h: int) -> list[list[str]]
    Create a maze using an iterative recursive backtracker.
    Cells: '#' wall, ' ' floor.
    w,h are expected odd; function will work best with odd sizes.
    """
    # Ensure odd sizes
    if w % 2 == 0:
        w = max(3, w - 1)
    if h % 2 == 0:
        h = max(3, h - 1)

    # Initialize full walls
    maze = [['#' for _ in range(w)] for __ in range(h)]
    rng = SimpleRNG(None)

    # Start at random odd cell
    start_x = 1
    start_y = 1
    maze[start_y][start_x] = ' '
    stack = [(start_x, start_y)]

    while stack:
        x, y = stack[-1]
        # Neighbours two steps away
        neigh = []
        for dx, dy in ((2,0),(-2,0),(0,2),(0,-2)):
            nx, ny = x+dx, y+dy
            if 1 <= nx < w-1 and 1 <= ny < h-1 and maze[ny][nx] == '#':
                neigh.append((nx, ny, dx//2, dy//2))
        if neigh:
            nx, ny, mx, my = rng.choice(neigh)
            # Carve
            maze[y+my][x+mx] = ' '
            maze[ny][nx] = ' '
            stack.append((nx, ny))
        else:
            stack.pop()
    return maze

def count_gold(maze: list[list[str]]) -> int:
    """count_gold(maze: list[list[str]]) -> int: return number of gold cells."""
    return sum(1 for row in maze for c in row if c == 'G')

def move_if_possible(maze: list[list[str]], px: int, py: int, dx: int, dy: int) -> tuple[int,int,int]:
    """
    move_if_possible(maze: list[list[str]], px: int, py: int, dx: int, dy: int) -> tuple[int,int,int]
    Try to move the player by (dx,dy). Returns (new_px, new_py, gained_score).
    If move blocked by wall or out of bounds, returns original pos and 0.
    If moves onto gold, returns gained_score 10 and clears the gold cell.
    """
    w = len(maze[0])
    h = len(maze)
    nx, ny = px + dx, py + dy
    if not in_bounds(w,h,nx,ny):
        return px, py, 0
    if maze[ny][nx] == '#':
        return px, py, 0
    gained = 0
    if maze[ny][nx] == 'G':
        gained = 10
        maze[ny][nx] = ' '
    return nx, ny, gained

def init_game(w: int, h: int, gold_count: int, step_limit: int, seed: int | None = None) -> dict[str, object]:
    """
    init_game(w: int, h: int, gold_count: int, step_limit: int, seed: int | None = None) -> dict[str, object]
    Initialize a new game state dictionary. Ensures required session_state keys are present.
    """
    # sanitize inputs
    try:
        seed_val = int(seed) if seed is not None and str(seed).strip() != '' else None
    except Exception:
        seed_val = None

    w = int(w)
    h = int(h)
    # ensure odd
    if w % 2 == 0:
        w = w - 1 if w > 3 else 3
    if h % 2 == 0:
        h = h - 1 if h > 3 else 3

    step_limit = _clamp(int(step_limit), 1, 100000)
    rng = SimpleRNG(seed_val)

    # create maze
    maze = make_maze(w, h)

    # place gold on empty cells
    empties = empty_cells(maze)
    max_gold = len(empties)
    desired = int(gold_count)
    if desired < 0:
        desired = 0
    desired = min(desired, max_gold)
    place_items(maze, empties, rng, 'G', desired)

    # place player: try (1,1) else first empty
    px, py = 1,1
    if not in_bounds(w,h,px,py) or maze[py][px] == '#':
        empt = empty_cells(maze)
        if empt:
            px,py = empt[0]
        else:
            # fallback: carve start
            px,py = 1,1
            if in_bounds(w,h,px,py):
                maze[py][px] = ' '

    state = {
        "maze": maze,
        "px": int(px),
        "py": int(py),
        "score": 0,
        "steps_left": int(step_limit),
        "game_over": False,
        "win": False,
        "seed_used": seed_val
    }
    return state

def render_grid_html(maze: list[list[str]], px: int, py: int, *, cell_px: int = 28, rounded: bool = True, show_coords: bool = False) -> str:
    """
    render_grid_html(maze: list[list[str]], px: int, py: int, *, cell_px: int = 28, rounded: bool = True, show_coords: bool = False) -> str
    Render the maze as an inline-styled CSS grid and return HTML string.
    """
    h = len(maze)
    w = len(maze[0]) if h else 0
    gap = 4
    radius = f"{max(2, int(cell_px*0.12))}px" if rounded else "2px"
    container_style = (
        f"display:grid; grid-template-columns: repeat({w}, {cell_px}px); "
        f"grid-auto-rows: {cell_px}px; gap:4px; background:{BG}; padding:8px; "
        f"border-radius:8px; width: max-content;"
    )
    cell_html_parts = [f'<div style="{container_style}">']
    for y in range(h):
        for x in range(w):
            ch = maze[y][x]
            title = "Floor"
            bg = FLOOR
            content = "&nbsp;"
            color = "#ffffff"
            if ch == '#':
                bg = WALL
                title = "Wall"
                content = "&nbsp;"
            elif ch == 'G':
                bg = GOLD
                title = "Gold"
                content = "★"
                color = "#2b2b2b"
            else:
                bg = FLOOR
                title = "Floor"
                content = "&nbsp;"
            if x == px and y == py:
                bg = PLAYER
                title = "Player"
                content = "🏃"
                color = "#021"  # not used much; emoji is primary

            aria = title
            style = (
                f"width:{cell_px}px; height:{cell_px}px; background:{bg}; "
                f"border-radius:{radius}; display:flex; align-items:center; justify-content:center; "
                f"font-size:{max(12, int(cell_px*0.6))}px; color:{color}; "
                f"box-shadow: inset 0 0 0 1px rgba(255,255,255,0.02);"
            )
            coord_text = f' data-coord="{x},{y}"' if show_coords else ""
            title_attr = f'title="{title}" aria-label="{aria}"'
            cell_html_parts.append(f'<div {title_attr} {coord_text} style="{style}">{content}</div>')
    cell_html_parts.append("</div>")
    return "".join(cell_html_parts)

# ------------------------------------------------------------------
# UI and game loop (single-interaction per run)
# ------------------------------------------------------------------

# Sidebar settings
st.sidebar.header("Ayarlar")
width = st.sidebar.number_input("Genişlik", min_value=15, max_value=51, value=21, step=2)
height = st.sidebar.number_input("Yükseklik", min_value=9, max_value=31, value=15, step=2)
gold_cnt = st.sidebar.number_input("Altın sayısı", min_value=1, max_value=200, value=15, step=1)
step_limit = st.sidebar.number_input("Adım limiti", min_value=10, max_value=1000, value=300, step=10)
seed_input = st.sidebar.text_input("Seed (opsiyonel int)", value="")
cell_px = st.sidebar.slider("Hücre boyutu", min_value=18, max_value=48, value=28, step=1)
rounded = st.sidebar.checkbox("Rounded hücreler", value=True)
show_coords = st.sidebar.checkbox("Koordinatları göster", value=False)

# clamp and coerce
try:
    seed_val = int(seed_input) if seed_input.strip() != "" else None
except Exception:
    seed_val = None

width = int(width); height = int(height)
# enforce odd sizes
if width % 2 == 0:
    width = max(3, width-1)
if height % 2 == 0:
    height = max(3, height-1)

gold_cnt = _clamp(int(gold_cnt), 0, 10000)
step_limit = _clamp(int(step_limit), 1, 100000)

# Initialize session state defaults
if "maze" not in st.session_state:
    initial = init_game(width, height, gold_cnt, step_limit, seed_val)
    for k,v in initial.items():
        st.session_state[k] = v

# Buttons to start new game or randomize
col_buttons = st.columns([1,1,2])
with col_buttons[0]:
    if st.button("Yeni Oyun (aynı seed)"):
        seed_for = st.session_state.get("seed_used", seed_val)
        new_state = init_game(width, height, gold_cnt, step_limit, seed_for)
        for k,v in new_state.items():
            st.session_state[k] = v
        st.rerun()
with col_buttons[1]:
    if st.button("Rastgele Labirent"):
        new_state = init_game(width, height, gold_cnt, step_limit, None)
        for k,v in new_state.items():
            st.session_state[k] = v
        st.rerun()
with col_buttons[2]:
    st.markdown(f"<div style='color:#ddd'>Seed: {st.session_state.get('seed_used')}</div>", unsafe_allow_html=True)

# Helper to process moves
def process_move(dx:int, dy:int):
    if st.session_state["game_over"]:
        return
    maze = st.session_state["maze"]
    px = st.session_state["px"]
    py = st.session_state["py"]
    new_px, new_py, gained = move_if_possible(maze, px, py, dx, dy)
    moved = not (new_px == px and new_py == py)
    if moved:
        st.session_state["px"] = int(new_px)
        st.session_state["py"] = int(new_py)
        st.session_state["score"] += int(gained)
        st.session_state["steps_left"] = max(0, st.session_state["steps_left"] - 1)
    # Check win/lose
    remaining_gold = count_gold(st.session_state["maze"])
    if remaining_gold <= 0:
        st.session_state["game_over"] = True
        st.session_state["win"] = True
    elif st.session_state["steps_left"] <= 0:
        st.session_state["game_over"] = True
        st.session_state["win"] = False

# Direction buttons
dir_cols = st.columns([1,1,1])
with dir_cols[0]:
    if st.button("⬆️"):
        process_move(0,-1)
        st.rerun()
with dir_cols[1]:
    if st.button("⬅️"):
        process_move(-1,0)
        st.rerun()
with dir_cols[2]:
    if st.button("➡️"):
        process_move(1,0)
        st.rerun()
dir2 = st.columns([1,1,1])
with dir2[0]:
    if st.button("⬇️"):
        process_move(0,1)
        st.rerun()

# Keyboard input via text_input
key = st.text_input("W/A/S/D ile hareket et (Enter sonra temizlenir)", key="key_input")
if key:
    k = key.strip().lower()
    if k:
        mapping = {'w':(0,-1),'a':(-1,0),'s':(0,1),'d':(1,0)}
        if k[0] in mapping:
            dx,dy = mapping[k[0]]
            process_move(dx,dy)
    # Clear input and rerun to maintain single keystroke behaviour
    st.session_state["key_input"] = ""
    st.rerun()

# Display metrics
col1, col2, col3 = st.columns(3)
col1.metric("Skor", st.session_state["score"])
col2.metric("Kalan Adım", st.session_state["steps_left"])
col3.metric("Kalan Altın", count_gold(st.session_state["maze"]))

# Render maze
html = render_grid_html(st.session_state["maze"], st.session_state["px"], st.session_state["py"],
                        cell_px=cell_px, rounded=rounded, show_coords=show_coords)
st.markdown(html, unsafe_allow_html=True)

# End game messages
if st.session_state["game_over"]:
    if st.session_state["win"]:
        st.success(f"Tebrikler! Tüm altınları topladınız. Skor: {st.session_state['score']}")
    else:
        st.error(f"Oyunu kaybettiniz. Adımlar bitti. Kalan altın: {count_gold(st.session_state['maze'])}")

# Footer small instructions
st.markdown("""<div style="color:#aaa">Kontroller: butonlar veya klavye (w/a/s/d). Yeni oyun butonları sidebar ayarlarına göre çalışır.</div>""", unsafe_allow_html=True)