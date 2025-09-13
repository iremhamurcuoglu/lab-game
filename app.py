# app.py
import streamlit as st
st.set_page_config(page_title="Labirent Koşusu", layout="wide")
import random

# --- Session state defaults ---
if "level" not in st.session_state:
    st.session_state.level = 1
if "win_all" not in st.session_state:
    st.session_state.win_all = False
if "game_over" not in st.session_state:
    st.session_state.game_over = False
if "game_over_final" not in st.session_state:
    st.session_state.game_over_final = False
# Level state placeholders
for k in ("maze", "px", "py", "steps_left", "gold_needed", "gold_collected", "exit_xy", "monsters"):
    if k not in st.session_state:
        st.session_state[k] = None
# Controls
if "speed" not in st.session_state:
    st.session_state.speed = 1
if "rounded" not in st.session_state:
    st.session_state.rounded = True
# UI prefs
if "cell_px" not in st.session_state:
    st.session_state.cell_px = 28
# internal flag for showing level message once
if "level_msg_shown" not in st.session_state:
    st.session_state.level_msg_shown = False

# --------------------------
# Maze & game utility funcs
# --------------------------
def compute_level_params(level: int) -> dict:
    """Compute parameters for a given level (w,h,steps,gold_needed,gold_total,monster_count)."""
    base_w, base_h = 19, 11
    # Every 3 levels increase both w and h by 2
    increments = (level - 1) // 3
    w = base_w + increments * 2
    h = base_h + increments * 2
    # Ensure odd dimensions
    if w % 2 == 0:
        w += 1
    if h % 2 == 0:
        h += 1
    # Steps: start 150, reduce ~4 per level
    steps = max(30, 150 - (level - 1) * 4)
    # Gold needed: start 3, +1 each level
    gold_needed = 3 + (level - 1)
    # Occasionally bump by +1 every 5 levels for extra difficulty
    gold_needed += (level - 1) // 5
    # Total gold on map at least needed + 2
    gold_total = gold_needed + 2
    # Monster count by ranges
    if level <= 2:
        mc = 0
    elif level <= 7:
        mc = 1
    elif level <= 14:
        mc = 2
    else:
        mc = 3
    return {"w": w, "h": h, "steps": steps, "gold_needed": gold_needed, "gold_total": gold_total, "monster_count": mc}

def make_maze(w: int, h: int) -> list:
    """Generate a maze using recursive backtracker. Returns grid as list of list[str] with '#' walls and ' ' floors."""
    # Ensure odd dims
    if w % 2 == 0:
        w += 1
    if h % 2 == 0:
        h += 1
    grid = [['#' for _ in range(w)] for _ in range(h)]
    # Cell coordinates are odd indexes
    def neighbors(cx, cy):
        dirs = [(2,0),(-2,0),(0,2),(0,-2)]
        random.shuffle(dirs)
        for dx, dy in dirs:
            nx, ny = cx+dx, cy+dy
            if 1 <= nx < w-1 and 1 <= ny < h-1 and grid[ny][nx] == '#':
                yield nx, ny, dx, dy
    # start at random odd cell
    start_x = random.randrange(1, w, 2)
    start_y = random.randrange(1, h, 2)
    stack = [(start_x, start_y)]
    grid[start_y][start_x] = ' '
    while stack:
        cx, cy = stack[-1]
        found = False
        for nx, ny, dx, dy in neighbors(cx, cy):
            if grid[ny][nx] == '#':
                # carve
                grid[cy + dy//2][cx + dx//2] = ' '
                grid[ny][nx] = ' '
                stack.append((nx, ny))
                found = True
                break
        if not found:
            stack.pop()
    return grid

def count_gold(maze: list) -> int:
    """Count gold pieces ('G') in the maze."""
    return sum(row.count('G') for row in maze)

def move_if_possible(maze: list, px: int, py: int, dx: int, dy: int, *, speed: int = 1) -> tuple:
    """Attempt to move the player up to 'speed' steps in direction (dx,dy). Stops at walls. Returns (new_px,new_py,gold_collected)."""
    w = len(maze[0])
    h = len(maze)
    gc = 0
    steps = max(1, int(speed))
    for _ in range(steps):
        nx = px + dx
        ny = py + dy
        if not (0 <= nx < w and 0 <= ny < h):
            break
        if maze[ny][nx] == '#':
            break
        px, py = nx, ny
        if maze[py][px] == 'G':
            gc += 1
            maze[py][px] = ' '
    return px, py, gc

def init_level(level: int) -> dict:
    """Initialize and return a fresh level state dict (maze, px,py,steps_left,gold_needed,gold_collected,exit_xy,monsters)."""
    params = compute_level_params(level)
    w = params["w"]
    h = params["h"]
    # Generate maze
    maze = make_maze(w, h)
    # find a starting cell (floor)
    floor_cells = [(x,y) for y in range(h) for x in range(w) if maze[y][x] == ' ']
    if not floor_cells:
        maze = make_maze(w, h)
        floor_cells = [(x,y) for y in range(h) for x in range(w) if maze[y][x] == ' ']
    px, py = random.choice(floor_cells)
    # Place EXIT ensuring Manhattan distance
    min_dist = max(1, w // 2)
    exit_xy = None
    attempts = 0
    while attempts < 2000:
        ex, ey = random.choice(floor_cells)
        if abs(ex - px) + abs(ey - py) >= min_dist and (ex,ey) != (px,py):
            exit_xy = (ex, ey)
            break
        attempts += 1
    if exit_xy is None:
        # fallback: pick farthest
        ex, ey = max(floor_cells, key=lambda t: abs(t[0]-px)+abs(t[1]-py))
        exit_xy = (ex, ey)
    # Place gold_total gold pieces on distinct floor cells not overlapping player/exit
    gold_total = params["gold_total"]
    candidates = [c for c in floor_cells if c != (px,py) and c != exit_xy]
    random.shuffle(candidates)
    placed = 0
    for cx, cy in candidates:
        if placed >= gold_total:
            break
        # avoid placing adjacent to exit exclusively? no need
        maze[cy][cx] = 'G'
        placed += 1
    # Place monsters on floor cells not overlapping player/exit/gold
    monster_count = params["monster_count"]
    monster_candidates = [c for c in floor_cells if c != (px,py) and c != exit_xy and maze[c[1]][c[0]] == ' ']
    random.shuffle(monster_candidates)
    monsters = monster_candidates[:monster_count]
    # assemble state
    state = {
        "maze": maze,
        "px": px,
        "py": py,
        "steps_left": params["steps"],
        "gold_needed": params["gold_needed"],
        "gold_collected": 0,
        "exit_xy": exit_xy,
        "monsters": monsters,
    }
    # reset level message flag
    st.session_state.level_msg_shown = False
    return state

def render_grid_html(maze: list, px: int, py: int, exit_xy: tuple, monsters: list, *, cell_px: int = 28, rounded: bool = True) -> str:
    """Render the maze as an HTML/CSS grid string with themed colors and emojis."""
    h = len(maze)
    w = len(maze[0]) if h else 0
    # color theme
    bg_page = "#E3F2FD"
    wall = "#0D47A1"
    floor = "#CFE6FF"
    gold_color = "#FFD54F"
    player_color = "#26A69A"
    exit_color = "#66BB6A"
    monster_color = "#EF5350"
    radius = "6px" if rounded else "0px"
    # Build cells
    cell_html = []
    monster_set = { (mx,my) for mx,my in monsters }
    for y in range(h):
        for x in range(w):
            ch = maze[y][x]
            is_wall = (ch == '#')
            is_gold = (ch == 'G')
            is_exit = (x,y) == exit_xy
            is_player = (x,y) == (px,py)
            is_mon = (x,y) in monster_set
            # base bg
            if is_wall:
                bg = wall
                content = ""
                fg = "#fff"
            else:
                bg = floor
                content = ""
                fg = "#000"
            style = (
                f"display:flex;align-items:center;justify-content:center;"
                f"width:{cell_px}px;height:{cell_px}px;"
                f"background:{bg};border:1px solid rgba(13,71,161,0.12);box-sizing:border-box;"
                f"border-radius:{radius};font-size:{cell_px - 8}px;"
            )
            inner = ""
            # draw layering: exit, gold, monster, player (player highest)
            if is_exit:
                style = style.replace(f"background:{bg};", f"background:{exit_color};")
                inner = "⛳"
            if is_gold:
                # gold overlay if not exit/player/monster
                inner = "★"
                style = style.replace(f"background:{bg};", f"background:{gold_color};")
            if is_mon:
                style = style.replace(f"background:{bg};", f"background:{monster_color};")
                inner = "😈"
            if is_player:
                style = style.replace(f"background:{bg};", f"background:{player_color};")
                inner = "🏃"
            # ensure text contrast
            html = f'<div style="{style}">{inner}</div>'
            cell_html.append(html)
    # container
    grid_style = (
        f"display:grid;grid-template-columns:repeat({w},{cell_px}px);"
        f"grid-gap:4px;padding:8px;background:{bg_page};border-radius:8px;"
    )
    html = f'<div style="{grid_style}">{"".join(cell_html)}</div>'
    return html

def step_monsters(maze, monsters, px, py):
    """Move monsters one step randomly on passable floors. Returns (new_monsters, penalty) where penalty is 1 if any monster lands on player."""
    h = len(maze)
    w = len(maze[0]) if h else 0
    new_monsters = []
    positions = set(monsters)
    for (mx, my) in monsters:
        candidates = []
        for dx, dy in [(0,1),(0,-1),(1,0),(-1,0)]:
            nx, ny = mx+dx, my+dy
            if 0 <= nx < w and 0 <= ny < h and maze[ny][nx] != '#' :
                candidates.append((nx, ny))
        if candidates:
            # choose random valid; bias to stay sometimes
            if random.random() < 0.25:
                nx, ny = mx, my
            else:
                nx, ny = random.choice(candidates)
        else:
            nx, ny = mx, my
        new_monsters.append((nx, ny))
    penalty = 0
    for m in new_monsters:
        if m == (px, py):
            penalty = 1
            break
    return new_monsters, penalty

# --------------------------
# Game control helpers
# --------------------------
def reset_game():
    """Reset the whole game to level 1."""
    st.session_state.level = 1
    st.session_state.win_all = False
    st.session_state.game_over = False
    st.session_state.game_over_final = False
    lvl_state = init_level(1)
    for k, v in lvl_state.items():
        st.session_state[k] = v
    st.rerun()

def reset_level():
    """Reset current level."""
    lvl = st.session_state.level
    lvl_state = init_level(lvl)
    for k, v in lvl_state.items():
        st.session_state[k] = v
    st.rerun()

# Initialize first time or when keys missing
if st.session_state.maze is None or st.session_state.exit_xy is None:
    lvl_state = init_level(st.session_state.level)
    for k, v in lvl_state.items():
        st.session_state[k] = v

# If final game over state, render GAME OVER full screen
if st.session_state.game_over_final:
    st.markdown("<div style='background:#E3F2FD;padding:40px;border-radius:8px;'>", unsafe_allow_html=True)
    st.markdown(f"<h1 style='text-align:center;color:#EF5350;font-size:64px;margin:8px;'>GAME OVER</h1>", unsafe_allow_html=True)
    st.markdown(f"<h3 style='text-align:center;color:#0D47A1;margin:8px;'>Seviye: {st.session_state.level} — Altın: {st.session_state.gold_collected}/{st.session_state.gold_needed} — Kalan Adım: {st.session_state.steps_left}</h3>", unsafe_allow_html=True)
    if st.button("Baştan Başla"):
        reset_game()
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# Sidebar controls
with st.sidebar:
    st.title("Labirent Koşusu")
    st.write(f"Seviye: {st.session_state.level}/20")
    cell_px = st.slider("Hücre boyutu", 18, 48, value=st.session_state.cell_px, step=2)
    st.session_state.cell_px = cell_px
    st.session_state.rounded = st.checkbox("rounded", value=st.session_state.rounded)
    st.session_state.speed = st.slider("Hız çarpanı", 1, 5, value=st.session_state.speed)
    st.markdown("---")
    st.markdown("Kontroller:\n- Ekrandaki oklarla oyna (klavye kapalı).")
    st.markdown("Not: Canavarlar altından −1 götürür.")
    st.markdown("Ayarları değiştirdiğinde Level Sıfırla/Baştan düğmelerini kullan.")

# Top info and metrics
col1, col2, col3 = st.columns([1,2,2])
with col1:
    st.metric("Level", f"{st.session_state.level}/20")
with col2:
    st.metric("Adım Kaldı", st.session_state.steps_left)
with col3:
    st.metric("Altın", f"{st.session_state.gold_collected}/{st.session_state.gold_needed}")

# Show level-start message once
if not st.session_state.level_msg_shown:
    st.info(f"Level {st.session_state.level} — Hedef: en az {st.session_state.gold_needed} altın topla, {st.session_state.steps_left} adım içinde ⛳ EXIT’e ulaş.\n\n😈 Canavarlar aynı hücreye gelirse altınını **−1** düşürür.\n\nKontrol: ekrandaki oklarla oynanır (klavye kapalı).")
    st.session_state.level_msg_shown = True

# Main layout: grid centered and controls
# Render grid HTML
maze_html = render_grid_html(st.session_state.maze, st.session_state.px, st.session_state.py, st.session_state.exit_xy, st.session_state.monsters, cell_px=st.session_state.cell_px, rounded=st.session_state.rounded)
center_col1, center_col2, center_col3 = st.columns([1, 6, 1])
with center_col2:
    st.markdown(maze_html, unsafe_allow_html=True)

# Controls buttons
col_left, col_center, col_right = st.columns([1,2,1])
with col_center:
    up, _, down = st.columns([1,0.2,1])
    with up:
        if st.button("⬆️"):
            dx, dy = 0, -1
            nx, ny, got = move_if_possible(st.session_state.maze, st.session_state.px, st.session_state.py, dx, dy, speed=st.session_state.speed)
            moved_steps = abs(nx - st.session_state.px) + abs(ny - st.session_state.py)
            st.session_state.px, st.session_state.py = nx, ny
            st.session_state.gold_collected += got
            st.session_state.gold_collected = max(0, st.session_state.gold_collected)
            st.session_state.steps_left -= moved_steps
            # monsters move
            newmons, penalty = step_monsters(st.session_state.maze, st.session_state.monsters, st.session_state.px, st.session_state.py)
            st.session_state.monsters = newmons
            if penalty:
                st.session_state.gold_collected = max(0, st.session_state.gold_collected - 1)
            st.rerun()
    with down:
        if st.button("⬇️"):
            dx, dy = 0, 1
            nx, ny, got = move_if_possible(st.session_state.maze, st.session_state.px, st.session_state.py, dx, dy, speed=st.session_state.speed)
            moved_steps = abs(nx - st.session_state.px) + abs(ny - st.session_state.py)
            st.session_state.px, st.session_state.py = nx, ny
            st.session_state.gold_collected += got
            st.session_state.gold_collected = max(0, st.session_state.gold_collected)
            st.session_state.steps_left -= moved_steps
            newmons, penalty = step_monsters(st.session_state.maze, st.session_state.monsters, st.session_state.px, st.session_state.py)
            st.session_state.monsters = newmons
            if penalty:
                st.session_state.gold_collected = max(0, st.session_state.gold_collected - 1)
            st.rerun()
    # Left/Right buttons on sides
with col_left:
    if st.button("⬅️"):
        dx, dy = -1, 0
        nx, ny, got = move_if_possible(st.session_state.maze, st.session_state.px, st.session_state.py, dx, dy, speed=st.session_state.speed)
        moved_steps = abs(nx - st.session_state.px) + abs(ny - st.session_state.py)
        st.session_state.px, st.session_state.py = nx, ny
        st.session_state.gold_collected += got
        st.session_state.gold_collected = max(0, st.session_state.gold_collected)
        st.session_state.steps_left -= moved_steps
        newmons, penalty = step_monsters(st.session_state.maze, st.session_state.monsters, st.session_state.px, st.session_state.py)
        st.session_state.monsters = newmons
        if penalty:
            st.session_state.gold_collected = max(0, st.session_state.gold_collected - 1)
        st.rerun()
with col_right:
    if st.button("➡️"):
        dx, dy = 1, 0
        nx, ny, got = move_if_possible(st.session_state.maze, st.session_state.px, st.session_state.py, dx, dy, speed=st.session_state.speed)
        moved_steps = abs(nx - st.session_state.px) + abs(ny - st.session_state.py)
        st.session_state.px, st.session_state.py = nx, ny
        st.session_state.gold_collected += got
        st.session_state.gold_collected = max(0, st.session_state.gold_collected)
        st.session_state.steps_left -= moved_steps
        newmons, penalty = step_monsters(st.session_state.maze, st.session_state.monsters, st.session_state.px, st.session_state.py)
        st.session_state.monsters = newmons
        if penalty:
            st.session_state.gold_collected = max(0, st.session_state.gold_collected - 1)
        st.rerun()

# Action buttons
a1, a2, a3 = st.columns([1,1,1])
with a1:
    if st.button("Leveli Sıfırla"):
        reset_level()
with a2:
    if st.button("Baştan"):
        reset_game()

# After actions, check for exit/gold/steps conditions
# If player on exit:
if (st.session_state.px, st.session_state.py) == st.session_state.exit_xy and st.session_state.gold_collected >= st.session_state.gold_needed:
    # Level complete
    if st.session_state.level >= 20:
        st.session_state.win_all = True
        st.success("🎉 Tebrikler, oyun bitti!")
    else:
        st.success(f"Level {st.session_state.level} tamamlandı! Bir sonraki levele geçiliyor...")
        st.session_state.level += 1
        lvl_state = init_level(st.session_state.level)
        for k, v in lvl_state.items():
            st.session_state[k] = v
        st.rerun()

# Steps exhausted?
if st.session_state.steps_left <= 0:
    # Check if success already satisfied (if on exit and gold ok handled above), otherwise fail
    if st.session_state.gold_collected >= st.session_state.gold_needed and (st.session_state.px, st.session_state.py) == st.session_state.exit_xy:
        # Should be handled above, but safe-check
        if st.session_state.level >= 20:
            st.session_state.win_all = True
            st.success("🎉 Tebrikler, oyun bitti!")
        else:
            st.session_state.level += 1
            lvl_state = init_level(st.session_state.level)
            for k, v in lvl_state.items():
                st.session_state[k] = v
            st.rerun()
    else:
        # Failure
        if st.session_state.level < 20:
            st.warning("Level Failed — Adımlar bitti.")
            if st.button("Tekrar Dene"):
                reset_level()
        else:
            # Level 20 failed -> full screen GAME OVER
            st.session_state.game_over_final = True
            st.rerun()

# Normal info: show remaining gold on map (for debug/aid)
remaining_gold_on_map = count_gold(st.session_state.maze)
st.caption(f"Haritada kalan altın: {remaining_gold_on_map}")

# If level 20 completed successfully, show final message
if st.session_state.win_all:
    st.balloons()
    st.markdown("<div style='padding:20px;background:#E3F2FD;border-radius:8px;'>", unsafe_allow_html=True)
    st.markdown("<h2>🎉 Tebrikler, oyun bitti!</h2>", unsafe_allow_html=True)
    if st.button("Baştan Başla"):
        reset_game()
    st.markdown("</div>", unsafe_allow_html=True)
