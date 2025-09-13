# app.py
# Single-file Streamlit maze runner game

import streamlit as st
from random import randrange, choice, shuffle, randint
from typing import List, Tuple, Dict

st.set_page_config(page_title="Maze Runner", layout="wide", initial_sidebar_state="expanded")

# --- Constants / Palette ---
BG = "#E3F2FD"
WALL_COLOR = "#000000"
FLOOR = "#CFE6FF"
GOLD_COLOR = "#FFD54F"
PLAYER_COLOR = "#26A69A"
EXIT_COLOR = "#66BB6A"
MONSTER_COLOR = "#EF5350"

# --- Session state keys initialization ---
if "level" not in st.session_state:
    st.session_state["level"] = 1
if "win_all" not in st.session_state:
    st.session_state["win_all"] = False
if "game_over" not in st.session_state:
    st.session_state["game_over"] = False

# Level-specific
for k in ("maze", "px", "py", "steps_left", "gold_needed", "gold_collected", "exit_xy", "monsters"):
    if k not in st.session_state:
        st.session_state[k] = None

# Controls
if "auto_run" not in st.session_state:
    st.session_state["auto_run"] = False
if "speed" not in st.session_state:
    st.session_state["speed"] = 1
if "last_dir" not in st.session_state:
    st.session_state["last_dir"] = (0, 0)
if "rounded" not in st.session_state:
    st.session_state["rounded"] = True
if "last_key" not in st.session_state:
    st.session_state["last_key"] = ""
if "cell_px" not in st.session_state:
    st.session_state["cell_px"] = 28

# --- Utility / Game functions ---


def clamp(v: int, a: int, b: int) -> int:
    return max(a, min(b, v))


def neighbors4(x: int, y: int) -> List[Tuple[int, int]]:
    return [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]


def is_inside(maze: List[List[str]], x: int, y: int) -> bool:
    return 0 <= y < len(maze) and 0 <= x < len(maze[0])


def is_floor(maze: List[List[str]], x: int, y: int) -> bool:
    return is_inside(maze, x, y) and maze[y][x] != "#"


def find_all_floor(maze: List[List[str]]) -> List[Tuple[int, int]]:
    floors = []
    for y in range(len(maze)):
        for x in range(len(maze[0])):
            if maze[y][x] != "#":
                floors.append((x, y))
    return floors


def manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def ensure_odd(n: int) -> int:
    return n if n % 2 == 1 else n - 1 if n > 1 else 1


def make_maze(w: int, h: int) -> List[List[str]]:
    """
    make_maze(w: int, h: int) -> list[list[str]]
    Generate a maze using recursive backtracker. '#' are walls, ' ' are floors.
    """
    w = ensure_odd(w)
    h = ensure_odd(h)
    maze = [["#"] * w for _ in range(h)]
    stack = []
    sx = randrange(1, w, 2)
    sy = randrange(1, h, 2)
    maze[sy][sx] = " "
    stack.append((sx, sy))
    while stack:
        x, y = stack[-1]
        nbrs = []
        for dx, dy in [(2, 0), (-2, 0), (0, 2), (0, -2)]:
            nx, ny = x + dx, y + dy
            if 1 <= nx < w - 1 and 1 <= ny < h - 1 and maze[ny][nx] == "#":
                nbrs.append((nx, ny, dx // 2, dy // 2))
        if nbrs:
            nx, ny, ox, oy = choice(nbrs)
            maze[y + oy][x + ox] = " "
            maze[ny][nx] = " "
            stack.append((nx, ny))
        else:
            stack.pop()
    return maze


def move_if_possible(maze: List[List[str]], px: int, py: int, dx: int, dy: int, *, speed: int = 1) -> Tuple[int, int, int]:
    """
    move_if_possible(maze, px, py, dx, dy, *, speed=1) -> (new_px, new_py, gold_collected_this_move)
    Attempt to move up to 'speed' steps in direction (dx,dy). Stop if hitting a wall. Collect gold if encountered.
    """
    gold = 0
    steps = clamp(speed, 1, 10)
    nx, ny = px, py
    for _ in range(steps):
        tx, ty = nx + dx, ny + dy
        if not is_inside(maze, tx, ty) or maze[ty][tx] == "#":
            break
        nx, ny = tx, ty
        if maze[ny][nx] == "G":
            gold += 1
            maze[ny][nx] = " "
    return nx, ny, gold


def count_gold(maze: List[List[str]]) -> int:
    """count_gold(maze) -> int : count gold pieces 'G' in the maze."""
    c = 0
    for row in maze:
        for ch in row:
            if ch == "G":
                c += 1
    return c


def compute_level_params(level: int) -> Dict[str, int]:
    """
    compute_level_params(level) -> dict with keys: w,h,steps,gold_needed,gold_total,monster_count
    Derive parameters scaling with level.
    """
    base_w, base_h = 19, 11
    # Increase size every 3 levels
    inc = (level - 1) // 3 * 2
    w = base_w + inc
    h = base_h + inc
    w = ensure_odd(w)
    h = ensure_odd(h)
    # Steps: start ~150 reduce 3-5 per level
    steps = max(40, 150 - sum(randint(3, 5) for _ in range(level - 1)))
    # Gold needed: start 3, +1 (sometimes +2)
    gold_needed = 3 + (level - 1)
    # Total gold: at least gold_needed + 2
    gold_total = gold_needed + 2 + (level // 5)
    # Monster count scale
    if level <= 2:
        monster_count = 0
    elif level <= 7:
        monster_count = 1
    elif level <= 14:
        monster_count = 2
    else:
        monster_count = 3
    return {"w": w, "h": h, "steps": steps, "gold_needed": gold_needed, "gold_total": gold_total, "monster_count": monster_count}


def init_level(level: int) -> Dict[str, object]:
    """
    init_level(level) -> dict[str, object]
    Initialize a level: generate maze, place player, exit, golds and monsters. Returns a dict with initial state.
    """
    params = compute_level_params(level)
    attempt = 0
    while True:
        attempt += 1
        maze = make_maze(params["w"], params["h"])
        floors = find_all_floor(maze)
        if len(floors) < 5:
            continue
        start = choice(floors)
        exit_cell = choice(floors)
        if manhattan(start, exit_cell) < params["w"] // 2:
            continue
        # Place gold avoiding start/exit
        available = [c for c in floors if c != start and c != exit_cell]
        shuffle(available)
        gold_positions = available[: params["gold_total"]]
        for gx, gy in gold_positions:
            maze[gy][gx] = "G"
        # Monsters
        monster_positions = []
        available_m = [c for c in available if c not in gold_positions]
        shuffle(available_m)
        for i in range(min(params["monster_count"], len(available_m))):
            monster_positions.append(available_m[i])
        # Assign exit marker (not to collide with gold/monsters)
        ex, ey = exit_cell
        maze[ey][ex] = " "
        # Done
        return {
            "maze": maze,
            "px": start[0],
            "py": start[1],
            "steps_left": params["steps"],
            "gold_needed": params["gold_needed"],
            "gold_collected": 0,
            "exit_xy": (ex, ey),
            "monsters": monster_positions,
        }


def render_grid_html(maze: List[List[str]], px: int, py: int, exit_xy: Tuple[int, int], monsters: List[Tuple[int, int]], *, cell_px: int = 28, rounded: bool = True) -> str:
    """
    render_grid_html(maze, px, py, exit_xy, monsters, *, cell_px=28, rounded=True) -> str
    Render the maze as an HTML string using a CSS grid. Uses the defined color palette and emojis.
    """
    rows = len(maze)
    cols = len(maze[0]) if rows else 0
    border_radius = "8px" if rounded else "2px"
    html = f"""<div style="background:{BG};padding:8px;border-radius:8px;display:inline-block;">
    <div style="display:grid;grid-template-columns:repeat({cols},{cell_px}px);grid-auto-rows:{cell_px}px;gap:4px;">"""
    mon_set = set(monsters)
    ex, ey = exit_xy
    for y in range(rows):
        for x in range(cols):
            ch = maze[y][x]
            style = f"width:{cell_px}px;height:{cell_px}px;display:flex;align-items:center;justify-content:center;border:1px solid rgba(0,0,0,0.08);border-radius:{border_radius};font-size:{int(cell_px*0.6)}px;"
            if (x, y) == (px, py):
                cell_html = f'<div title="You" style="{style}background:{PLAYER_COLOR};color:white;">🏃</div>'
            elif (x, y) == (ex, ey):
                cell_html = f'<div title="EXIT" style="{style}background:{EXIT_COLOR};color:white;">⛳</div>'
            elif (x, y) in mon_set:
                cell_html = f'<div title="Monster" style="{style}background:{MONSTER_COLOR};color:white;">😈</div>'
            elif ch == "#":
                cell_html = f'<div style="{style}background:{WALL_COLOR};"></div>'
            elif ch == "G":
                cell_html = f'<div title="Gold" style="{style}background:{FLOOR};color:{GOLD_COLOR};font-weight:bold;">★</div>'
            else:
                cell_html = f'<div style="{style}background:{FLOOR};"></div>'
            html += cell_html
    html += "</div></div>"
    return html


def step_monsters(maze: List[List[str]], monsters: List[Tuple[int, int]], px: int, py: int) -> Tuple[List[Tuple[int, int]], int]:
    """
    step_monsters(maze, monsters, px, py) -> (new_monsters, penalty)
    Move each monster one random step into adjacent floor cell (no passing walls). If a monster enters the player cell, penalty -1.
    """
    new_positions = []
    occupied = set(monsters)
    penalty = 0
    order = list(range(len(monsters)))
    shuffle(order)
    for i in order:
        mx, my = monsters[i]
        choices = []
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = mx + dx, my + dy
            if is_inside(maze, nx, ny) and maze[ny][nx] != "#" and (nx, ny) not in occupied:
                choices.append((nx, ny))
        if choices:
            nx, ny = choice(choices)
        else:
            nx, ny = mx, my
        occupied.discard((mx, my))
        occupied.add((nx, ny))
        new_positions.append((nx, ny))
        if (nx, ny) == (px, py):
            penalty -= 1
    # ensure penalty doesn't lower below zero externally
    return new_positions, penalty


# --- Initialization / Level handling ---
def load_level(level: int):
    """Load or initialize a level into session_state."""
    lvl_data = init_level(level)
    st.session_state["maze"] = lvl_data["maze"]
    st.session_state["px"] = lvl_data["px"]
    st.session_state["py"] = lvl_data["py"]
    st.session_state["steps_left"] = lvl_data["steps_left"]
    st.session_state["gold_needed"] = lvl_data["gold_needed"]
    st.session_state["gold_collected"] = lvl_data["gold_collected"]
    st.session_state["exit_xy"] = lvl_data["exit_xy"]
    st.session_state["monsters"] = lvl_data["monsters"]
    st.session_state["game_over"] = False
    st.session_state["auto_run"] = False
    st.session_state["last_dir"] = (0, 0)


if st.session_state["maze"] is None:
    load_level(st.session_state["level"])


# --- Keyboard capture via components.html ---
kbd_html = """
<div tabindex="0" id="kbd_div" style="outline:none;"></div>
<script>
const target = document.getElementById("kbd_div");
target.focus();
function sendKey(k){
    // Post message in a structure streamlit might pick up; many Streamlit deployments forward postMessage payloads to the python iframe wrapper.
    window.parent.postMessage({type:'st_keydown', key: k}, "*");
}
window.addEventListener("keydown", (e) => {
    const key = e.key;
    sendKey(key);
});
</script>
"""
# Render invisible component to capture keys
st.components.v1.html(kbd_html, height=0, scrolling=False)


# Attempt to read messages forwarded to session_state via query parameters from the browser (best-effort):
# Some Streamlit frontends forward postMessage payloads to the python side via window.postMessage protocol.
# We'll inspect st.session_state["last_key"] if any component updated it previously.
# To be conservative, we also provide on-screen buttons that always work.

# JS -> Python bridging: We attempt to check for posted messages via a small polling iframe approach.
# Create an HTML component which, when it receives parent postMessage, sets its document.title,
# and the Streamlit backend may capture and return that value; this is a best-effort fallback.
bridge_html = """
<script>
window.addEventListener("message", (e) => {
    if (!e.data) return;
    try {
        if (e.data.type === 'st_keydown' && e.data.key) {
            // expose via document.title so Streamlit frontend can pick it up on rerender cycles
            document.title = 'st_last_key:' + e.data.key + ':' + Date.now();
        }
    } catch (err) {}
}, false);
</script>
"""
st.components.v1.html(bridge_html, height=0)


# Check document.title hack: Some frontends propagate title -> st.experimental_get_query_params is not reliable.
# But we can still read an incoming key from st.session_state if any custom integration set it.
# We'll check st.session_state["last_key"] to see if set by prior runs (component may not set it).
incoming_key = st.session_state.get("last_key", "")

# --- Controls UI ---
with st.sidebar:
    st.markdown(f"<div style='background:{BG};padding:8px;border-radius:8px;'>", unsafe_allow_html=True)
    st.header("Maze Runner")
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("Controls: Arrow keys or W/A/S/D, or use the buttons below.")
    st.session_state["cell_px"] = st.slider("Cell size (px)", 18, 48, st.session_state["cell_px"], step=2)
    st.session_state["rounded"] = st.checkbox("Rounded cells", st.session_state["rounded"])
    st.session_state["speed"] = st.slider("Speed multiplier", 1, 5, st.session_state["speed"])
    st.session_state["auto_run"] = st.checkbox("Auto-Run", st.session_state["auto_run"])
    st.markdown("---")
    if st.button("Restart Level"):
        load_level(st.session_state["level"])
        st.experimental_rerun()
    if st.button("Restart Game (Level 1)"):
        st.session_state["level"] = 1
        load_level(1)
        st.experimental_rerun()
    st.markdown("Tips: Auto-Run will continue moving each rerun. Use stop to halt.")
    st.markdown("Rounded corners, speed and cell size affect visuals.")
    st.markdown("---")
    st.markdown("Goal: Reach EXIT and collect required gold within steps.")
    st.markdown(f"Levels: 1 .. 20 (current: {st.session_state['level']})")


# --- Helper to process a movement action ---
def process_move(dx: int, dy: int):
    if st.session_state["game_over"]:
        return
    maze = st.session_state["maze"]
    px = st.session_state["px"]
    py = st.session_state["py"]
    speed = clamp(int(st.session_state["speed"]), 1, 5)
    nx, ny, gold = move_if_possible(maze, px, py, dx, dy, speed=speed)
    st.session_state["px"], st.session_state["py"] = nx, ny
    st.session_state["gold_collected"] = max(0, st.session_state["gold_collected"] + gold)
    st.session_state["steps_left"] = max(0, st.session_state["steps_left"] - (abs(nx - px) + abs(ny - py) or 1))
    # Monsters move after player
    monsters, penalty = step_monsters(maze, st.session_state["monsters"], st.session_state["px"], st.session_state["py"])
    st.session_state["monsters"] = monsters
    if penalty < 0:
        st.session_state["gold_collected"] = max(0, st.session_state["gold_collected"] + penalty)
    # Auto-run direction
    st.session_state["last_dir"] = (dx, dy)
    # Check for gold on current cell (in case stayed)
    if maze[st.session_state["py"]][st.session_state["px"]] == "G":
        st.session_state["gold_collected"] += 1
        maze[st.session_state["py"]][st.session_state["px"]] = " "
    # Check for level completion
    ex, ey = st.session_state["exit_xy"]
    if (st.session_state["px"], st.session_state["py"]) == (ex, ey) and st.session_state["gold_collected"] >= st.session_state["gold_needed"]:
        # Advance level or win
        if st.session_state["level"] >= 20:
            st.session_state["win_all"] = True
            st.session_state["game_over"] = True
        else:
            st.session_state["level"] += 1
            load_level(st.session_state["level"])
    # Check steps out
    if st.session_state["steps_left"] <= 0:
        if st.session_state["gold_collected"] >= st.session_state["gold_needed"] and (st.session_state["px"], st.session_state["py"]) == (ex, ey):
            # already handled
            pass
        else:
            st.session_state["game_over"] = True


# Movement buttons handlers
def move_up():
    process_move(0, -1)


def move_down():
    process_move(0, 1)


def move_left():
    process_move(-1, 0)


def move_right():
    process_move(1, 0)


# --- Top metrics / Game rendering ---
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    st.metric("Level", f"{st.session_state['level']}/20")
with col2:
    st.markdown(
        f"<div style='background:{BG};padding:8px;border-radius:8px;display:flex;gap:12px;justify-content:center;'>"
        f"<div>Steps Left: <b>{st.session_state['steps_left']}</b></div>"
        f"<div>Gold: <b>{st.session_state['gold_collected']}</b> / {st.session_state['gold_needed']}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
with col3:
    st.checkbox("Auto-Run (start/stop)", value=st.session_state["auto_run"], key="auto_run_sidebar")

# Main area: grid and controls
maze = st.session_state["maze"]
px = st.session_state["px"]
py = st.session_state["py"]
exit_xy = st.session_state["exit_xy"]
monsters = st.session_state["monsters"]

grid_html = render_grid_html(maze, px, py, exit_xy, monsters, cell_px=st.session_state["cell_px"], rounded=st.session_state["rounded"])
st.markdown(grid_html, unsafe_allow_html=True)

# Controls row
c1, c2, c3 = st.columns([1, 2, 1])
with c2:
    col_up, col_middle, col_down = st.columns(3)
    with col_up:
        if st.button("⬆️") or (incoming_key in ("ArrowUp", "w", "W")):
            process_move(0, -1)
    with col_middle:
        left_col, mid_col, right_col = st.columns(3)
        with left_col:
            if st.button("⬅️") or (incoming_key in ("ArrowLeft", "a", "A")):
                process_move(-1, 0)
        with mid_col:
            if st.button("⏹ Stop"):
                st.session_state["auto_run"] = False
                st.session_state["last_dir"] = (0, 0)
        with right_col:
            if st.button("➡️") or (incoming_key in ("ArrowRight", "d", "D")):
                process_move(1, 0)
    with col_down:
        if st.button("⬇️") or (incoming_key in ("ArrowDown", "s", "S")):
            process_move(0, 1)

# If incoming_key present, map to actions
key = incoming_key
if key:
    k = key
    if k in ("ArrowUp", "w", "W"):
        process_move(0, -1)
    elif k in ("ArrowDown", "s", "S"):
        process_move(0, 1)
    elif k in ("ArrowLeft", "a", "A"):
        process_move(-1, 0)
    elif k in ("ArrowRight", "d", "D"):
        process_move(1, 0)
    # clear to avoid repeated unintended moves
    st.session_state["last_key"] = ""

# Auto-run handling: continue moving in last_dir each rerun
if st.session_state["auto_run"]:
    dx, dy = st.session_state.get("last_dir", (0, 0))
    if dx == 0 and dy == 0:
        # need a direction; default to right
        dx, dy = (1, 0)
        st.session_state["last_dir"] = (dx, dy)
    # perform a move, then request rerun to continue looping
    process_move(dx, dy)
    # small guard: stop auto-run if game over or steps exhausted
    if st.session_state["game_over"] or st.session_state["win_all"]:
        st.session_state["auto_run"] = False
    else:
        # rerun to continue auto-run loop
        st.rerun()

# Game over / level fail handling and messages
if st.session_state["win_all"]:
    st.success("Congratulations! You completed all 20 levels! 🎉")
    if st.button("Play Again"):
        st.session_state["level"] = 1
        load_level(1)
        st.experimental_rerun()
elif st.session_state["game_over"]:
    st.warning("Level Failed! Out of steps or conditions not met.")
    if st.button("Retry Level"):
        load_level(st.session_state["level"])
        st.experimental_rerun()
    if st.button("Go to Next Level (force)"):
        if st.session_state["level"] < 20:
            st.session_state["level"] += 1
            load_level(st.session_state["level"])
            st.experimental_rerun()

# Footer: show some diagnostics
st.markdown("---")
st.markdown(
    f"<div style='font-size:12px;color:#333;'>Monsters: {len(st.session_state['monsters'])} | Total gold left in maze: {count_gold(st.session_state['maze'])}</div>",
    unsafe_allow_html=True,
)

# Ensure gold_collected never negative
st.session_state["gold_collected"] = max(0, int(st.session_state["gold_collected"]))
