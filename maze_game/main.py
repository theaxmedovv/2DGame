import pygame
import heapq
import math
import random
import asyncio
import os
import sys 

# ---------------- QIYINCHILIK DARALARI CONFIG ----------------
LEVELS = {
    "Easy": {"ROWS": 15, "COLS": 15, "CELL_SIZE": 800 // 15, "EXTRA_PATHS": 100},
    "Medium": {"ROWS": 25, "COLS": 25, "CELL_SIZE": 800 // 25, "EXTRA_PATHS": 70},
    "Hard": {"ROWS": 40, "COLS": 40, "CELL_SIZE": 800 // 40, "EXTRA_PATHS": 30},
}

# --- GLOBAL O'ZGARUVCHILAR ---
WIDTH, HEIGHT = 800, 800 # Oyna o'lchami
CURRENT_LEVEL = "Medium"
# Boshlang'ich qiymatlar
ROWS = LEVELS[CURRENT_LEVEL]["ROWS"]
COLS = LEVELS[CURRENT_LEVEL]["COLS"]
CELL_SIZE = LEVELS[CURRENT_LEVEL]["CELL_SIZE"]
VISUALIZATION_DELAY_SEC = 0.005

# Colors
WHITE = (255, 255, 255)
GRAY = (200, 200, 200)
BLACK = (30, 30, 30) 
PURPLE = (128, 0, 128)
ORANGE = (255, 165, 0)
GREEN = (0, 200, 0)
PATH_COLOR = (0, 120, 255)

# Gradient uchun ranglar
BG_COLOR_TOP = (150, 200, 255) # Osmonsimon ko'k
BG_COLOR_BOTTOM = (200, 255, 200) # Yashilsimon

# --- GLOBAL PYGAME OBYEKTLARINI E'LON QILISH ---
pygame.init() 
WIN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Dijkstra – Maze Game (SPACE/R/L keys)")
CLOCK = pygame.time.Clock()

# ---------------- LOAD ASSETS ----------------
def load_image(filename, is_wall=False):
    try:
        current_dir = os.path.dirname(os.path.abspath(__file__)) 
        ASSETS_PATH = os.path.join(current_dir, "assets")
        
        target_size = int(CELL_SIZE * 1.1) if is_wall else CELL_SIZE
        
        img = pygame.image.load(os.path.join(ASSETS_PATH, filename))
        return pygame.transform.scale(img, (target_size, target_size))
        
    except Exception:
        surf = pygame.Surface((CELL_SIZE, CELL_SIZE))
        if is_wall:
            surf.fill(BLACK)
            return pygame.transform.scale(surf, (int(CELL_SIZE * 1.1), int(CELL_SIZE * 1.1)))
        elif 'player' in filename:
            surf.fill(YELLOW)
        elif 'finish' in filename:
            surf.fill((255, 0, 0))
        return surf

# Rasmlarni yuklashda doimo yangi CELL_SIZE ga moslash
def load_all_assets():
    global WALL_IMG, PLAYER_BASE_IMG, FINISH_BASE_IMG
    WALL_IMG = load_image("wall.png", is_wall=True)
    PLAYER_BASE_IMG = load_image("player.png")
    FINISH_BASE_IMG = load_image("finish.png")

load_all_assets() # Boshlang'ich yuklash


# ---------------- UTILS ----------------

def draw_gradient(win, color1, color2):
    """Vertikal gradient fonni chizadi."""
    height = win.get_height()
    for y in range(height):
        r = color1[0] + (color2[0] - color1[0]) * y // height
        g = color1[1] + (color2[1] - color1[1]) * y // height
        b = color1[2] + (color2[2] - color1[2]) * y // height
        pygame.draw.line(win, (r, g, b), (0, y), (WIDTH, y))

# ---------------- UI CLASS ----------------
class Button:
    def __init__(self, x, y, w, h, text, color, action=None):
        self.rect = pygame.Rect(x, y, w, h)
        self.text = text
        self.color = color
        self.action = action
        self.font = pygame.font.Font(None, 30)

    def draw(self, win):
        pygame.draw.rect(win, self.color, self.rect, border_radius=5)
        text_surf = self.font.render(self.text, True, BLACK)
        text_rect = text_surf.get_rect(center=self.rect.center)
        win.blit(text_surf, text_rect)

    def is_clicked(self, pos):
        return self.rect.collidepoint(pos)

# ---------------- CAMERA CLASS ----------------
class Camera:
    def __init__(self, width, height, map_width, map_height):
        self.width = width
        self.height = height
        self.map_width = map_width
        self.map_height = map_height
        self.offset_x = 0
        self.offset_y = 0
        self.speed = 0.05 

    def update(self, target_rect):
        target_x = target_rect.centerx
        target_y = target_rect.centery

        target_offset_x = target_x - self.width // 2
        target_offset_y = target_y - self.height // 2

        self.offset_x += (target_offset_x - self.offset_x) * self.speed
        self.offset_y += (target_offset_y - self.offset_y) * self.speed
        
        self.offset_x = max(0, min(self.offset_x, self.map_width - self.width))
        self.offset_y = max(0, min(self.offset_y, self.map_height - self.height))

    def apply(self, node):
        return (node.x - int(self.offset_x), node.y - int(self.offset_y))
    
    def apply_rect(self, rect):
        return rect.move(-int(self.offset_x), -int(self.offset_y))

# ---------------- NODE ----------------
class Node:
    def __init__(self, row, col):
        self.row = row
        self.col = col
        self.x = col * CELL_SIZE
        self.y = row * CELL_SIZE
        self.wall = False
        self.start = False
        self.finish = False
        self.distance = float('inf')
        self.prev = None
        self.in_queue = False
        self.processed = False
        self.is_path = False
        self.is_current = False 

    def __lt__(self, other):
        return self.distance < other.distance

    def draw(self, win, offset_x, offset_y):
        screen_x = self.x - offset_x
        screen_y = self.y - offset_y

        color = WHITE
        if self.is_path: color = PATH_COLOR
        elif self.processed: color = PURPLE
        elif self.in_queue: color = ORANGE
        elif self.is_current: color = GREEN
        
        pygame.draw.rect(win, color, (screen_x, screen_y, CELL_SIZE, CELL_SIZE))

        if self.wall:
            wall_size = int(CELL_SIZE * 1.1)
            offset = (wall_size - CELL_SIZE) // 2
            win.blit(WALL_IMG, (screen_x - offset, screen_y - offset)) 
        elif self.finish:
            t = pygame.time.get_ticks()
            pulse_factor = 1 + 0.5 * abs(math.sin(t * 0.005))
            pulse_size = int(CELL_SIZE * pulse_factor)
            pulse_offset = (pulse_size - CELL_SIZE) // 2
            
            finish_img = pygame.transform.scale(FINISH_BASE_IMG, (pulse_size, pulse_size)) 
            win.blit(finish_img, (screen_x - pulse_offset, screen_y - pulse_offset))

        pygame.draw.rect(win, GRAY, (screen_x, screen_y, CELL_SIZE, CELL_SIZE), 1)

    def reset_search(self):
        self.distance = float('inf')
        self.prev = None
        self.in_queue = False
        self.processed = False
        self.is_path = False
        self.is_current = False

# ---------------- PLAYER ----------------
class Player:
    def __init__(self, start_node):
        self.current_node = start_node
        self.x = start_node.x + CELL_SIZE // 2
        self.y = start_node.y + CELL_SIZE // 2
        self.path = []
        self.index = 0
        self.speed = 15
        self.moving = False

    def start(self, path):
        self.path = path
        self.index = 1
        self.moving = True

    def update(self):
        if not self.moving or self.index >= len(self.path):
            self.moving = False
            return
        
        target = self.path[self.index]
        tx = target.x + CELL_SIZE // 2
        ty = target.y + CELL_SIZE // 2
        
        dx = tx - self.x
        dy = ty - self.y
        dist = math.hypot(dx, dy)
        
        if dist < self.speed:
            self.x, self.y = tx, ty
            self.current_node = target
            self.index += 1
        else:
            self.x += dx / dist * self.speed
            self.y += dy / dist * self.speed
            
    def get_rect(self):
        return pygame.Rect(self.x - CELL_SIZE // 2, self.y - CELL_SIZE // 2, CELL_SIZE, CELL_SIZE)

    def draw(self, win, offset_x, offset_y):
        screen_x = int(self.x - offset_x)
        screen_y = int(self.y - offset_y)
        
        player_scaled_img = pygame.transform.scale(PLAYER_BASE_IMG, (CELL_SIZE, CELL_SIZE))
        player_rect = player_scaled_img.get_rect(center=(screen_x, screen_y))
        win.blit(player_scaled_img, player_rect)


# ---------------- GRID & HELPERS ----------------
def create_grid():
    global ROWS, COLS
    return [[Node(r, c) for c in range(COLS)] for r in range(ROWS)]

def get_neighbors(node, grid):
    global ROWS, COLS
    res = []
    for dr, dc in [(1,0), (-1,0), (0,1), (0,-1)]:
        r, c = node.row + dr, node.col + dc
        if 0 <= r < ROWS and 0 <= c < COLS and not grid[r][c].wall:
            res.append(grid[r][c])
    return res

def reconstruct_path(end):
    path = []
    cur = end
    while cur:
        path.append(cur)
        cur = cur.prev
    return path[::-1]

def get_node_from_pos(pos, grid):
    """Sichqoncha pozitsiyasi bo'yicha tugunni qaytaradi."""
    global CELL_SIZE, ROWS, COLS
    col = pos[0] // CELL_SIZE
    row = pos[1] // CELL_SIZE
    if 0 <= row < ROWS and 0 <= col < COLS:
        return grid[row][col]
    return None

def random_finish(grid, start):
    global ROWS, COLS
    valid_nodes = []
    for r in range(ROWS):
        for c in range(COLS):
            node = grid[r][c]
            if not node.wall and node != start and r > 1 and r < ROWS - 2 and c > 1 and c < COLS - 2:
                 dist = (node.row - start.row)**2 + (node.col - start.col)**2
                 valid_nodes.append((dist, node))
                 
    valid_nodes.sort(key=lambda x: x[0], reverse=True)
    if valid_nodes:
        return random.choice(valid_nodes[:min(10, len(valid_nodes))])[1]
    
    return grid[ROWS-2][COLS-2]

def clear_old_finish(grid):
    for row in grid:
        for node in row:
            if node.finish:
                node.finish = False
                node.reset_search()
                return node
    return None
    
# ---------------- MAZE GENERATION ----------------
def generate_maze(grid, start, finish):
    global ROWS, COLS
    for r in range(ROWS):
        for c in range(COLS):
            grid[r][c].wall = True

    stack = [start]
    start.wall = False
    visited = {start}

    while stack:
        cur = stack[-1]
        neighbors = []
        for dr, dc in [(2,0), (-2,0), (0,2), (0,-2)]:
            r, c = cur.row + dr, cur.col + dc
            if 0 <= r < ROWS and 0 <= c < COLS and grid[r][c] not in visited:
                neighbors.append(grid[r][c])
        if neighbors:
            nxt = random.choice(neighbors)
            wall_r = cur.row + (nxt.row - cur.row)//2
            wall_c = cur.col + (nxt.col - cur.col)//2
            grid[wall_r][wall_c].wall = False
            nxt.wall = False
            visited.add(nxt)
            stack.append(nxt)
        else:
            stack.pop()
    
    start.wall = False
    finish.wall = False

def add_extra_paths(grid, count):
    global ROWS, COLS
    added = 0
    tries = 0
    while added < count and tries < count * 5:
        r = random.randint(1, ROWS-2)
        c = random.randint(1, COLS-2)
        node = grid[r][c]
        
        if node.wall:
            open_n = 0
            for dr, dc in [(1,0), (-1,0), (0,1), (0,-1)]:
                if 0 <= r+dr < ROWS and 0 <= c+dc < COLS and not grid[r+dr][c+dc].wall:
                    open_n += 1
            
            if open_n == 1:
                 node.wall = False
                 added += 1
            elif open_n == 0:
                 node.wall = False 
                 added += 1
            elif open_n >= 2 and random.random() < 0.2:
                 node.wall = False
                 added += 1
                 
        tries += 1
        
# ---------------- DIJKSTRA ----------------
async def dijkstra(start, finish, grid, draw):
    for row in grid:
        for node in row:
            node.reset_search()

    pq = []
    start.distance = 0
    heapq.heappush(pq, (0, start))
    visited = {start}

    while pq:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        _, cur = heapq.heappop(pq)
        
        cur.is_current = True 
        draw()
        await asyncio.sleep(VISUALIZATION_DELAY_SEC)
        cur.is_current = False

        if cur.processed:
            continue
            
        cur.processed = True

        if cur == finish:
            return reconstruct_path(finish)

        for nb in get_neighbors(cur, grid):
            if nb.processed:
                continue
                
            nd = cur.distance + 1
            if nd < nb.distance:
                nb.distance = nd
                nb.prev = cur
                heapq.heappush(pq, (nb.distance, nb))
                nb.in_queue = True

        draw()
        await asyncio.sleep(VISUALIZATION_DELAY_SEC)

    return None

# ---------------- DRAW ----------------
def draw_all(win, grid, player, camera, buttons, path=None):
    draw_gradient(win, BG_COLOR_TOP, BG_COLOR_BOTTOM)
    
    for row in grid:
        for node in row:
            node.is_path = False
            
    if path:
        for node in path:
            if not node.start and not node.finish:
                node.is_path = True
            
    for row in grid:
        for node in row:
            node.draw(win, int(camera.offset_x), int(camera.offset_y))
            
    if player:
        player.draw(win, int(camera.offset_x), int(camera.offset_y))
    
    # Faqat level tugmalarini chizamiz (agar ko'rsatilgan bo'lsa)
    for button in buttons:
        button.draw(win)
        
    pygame.display.update()

# ---------------- MAIN ----------------
def update_global_level(level_name):
    global ROWS, COLS, CELL_SIZE, CURRENT_LEVEL
    
    if level_name not in LEVELS:
        level_name = "Medium"
        
    CURRENT_LEVEL = level_name
    ROWS = LEVELS[level_name]["ROWS"]
    COLS = LEVELS[level_name]["COLS"]
    CELL_SIZE = LEVELS[level_name]["CELL_SIZE"]
    
    load_all_assets()


async def main():
    global ROWS, COLS, CELL_SIZE, CURRENT_LEVEL

    # START, RESET, CHANGE MAP tugmalari butunlay olib tashlandi.
    
    # --- Level o'zgartirish UI elementlari ---
    level_buttons = []
    level_y = HEIGHT - 50
    level_x = 10
    
    # Level tanlash tugmasini bosish uchun ishlatiladigan ichki funksiya
    def set_level_action(level_name):
        return ('set_level', level_name)
    
    for i, (name, config) in enumerate(LEVELS.items()):
        # Level tugmalarini yaratish
        level_buttons.append(Button(level_x, level_y, 100, 30, name, GRAY, lambda n=name: set_level_action(n)))
        level_x += 110

    # Boshqaruv holati
    show_level_buttons = True
    
    # --- Boshlang'ich Level Sozlamalari ---
    update_global_level(CURRENT_LEVEL)
    
    grid = create_grid()
    start = grid[1][1]
    
    MAP_WIDTH = COLS * CELL_SIZE
    MAP_HEIGHT = ROWS * CELL_SIZE
    camera = Camera(WIDTH, HEIGHT, MAP_WIDTH, MAP_HEIGHT)

    def reset_level(random_finish_flag=True):
        nonlocal finish, player, started, grid, MAP_WIDTH, MAP_HEIGHT, camera
        
        grid = create_grid() 
        start = grid[1][1] 
        
        for r in range(ROWS):
            for c in range(COLS):
                grid[r][c].start = False
                grid[r][c].finish = False
                grid[r][c].reset_search()
                grid[r][c].is_path = False
        
        generate_maze(grid, start, start)
        add_extra_paths(grid, LEVELS[CURRENT_LEVEL]["EXTRA_PATHS"]) 
        
        start.start = True
        
        if random_finish_flag:
            new_finish = random_finish(grid, start)
            new_finish.finish = True
            finish = new_finish
        
        MAP_WIDTH = COLS * CELL_SIZE
        MAP_HEIGHT = ROWS * CELL_SIZE
        camera = Camera(WIDTH, HEIGHT, MAP_WIDTH, MAP_HEIGHT)
        player = Player(start)
        started = False
        return finish
        
    finish = reset_level(random_finish_flag=True)
    player = Player(start)
    started = False
    running = True
    
    # draw_callback faqat level_buttons ko'rsatish/yashirishni boshqaradi
    draw_callback = lambda p=None, path=None: draw_all(WIN, grid, player, camera, level_buttons if show_level_buttons else [], path)

    # --- Asosiy O'yin Tsikli ---
    while running:
        
        camera.update(player.get_rect())
        
        if player.moving:
            player.update()
            
        current_path = player.path if not player.moving and player.index > 0 else None
        
        draw_callback(path=current_path)

        # Sichqoncha orqali devor chizish/o'chirish
        mouse_buttons = pygame.mouse.get_pressed()
        if mouse_buttons[0] or mouse_buttons[2]:
            pos = pygame.mouse.get_pos()
            
            # Agar sichqoncha Level tugmalari ustida bo'lmasa, devor chizishga ruxsat berish
            is_over_ui = any(btn.rect.collidepoint(pos) for btn in level_buttons)
            
            if not is_over_ui:
                map_pos = (pos[0] + int(camera.offset_x), pos[1] + int(camera.offset_y))
                node = get_node_from_pos(map_pos, grid)

                if node and not node.start and not node.finish:
                    if mouse_buttons[0]: 
                        node.wall = True
                        node.is_path = False
                    elif mouse_buttons[2]:
                        node.wall = False

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            # --- Sichqoncha bosilishi (Faqat Level tanlash va Finish belgilash uchun) ---
            if event.type == pygame.MOUSEBUTTONDOWN:
                pos = event.pos
                action = None
                
                # 1. Level tugmalarini tekshirish (faqat ko'ringan bo'lsa)
                if show_level_buttons:
                    for btn in level_buttons:
                        if btn.is_clicked(pos):
                            action = btn.action()
                            break

                # 2. LEVEL Harakatlarini Bajarish
                if isinstance(action, tuple) and action[0] == 'set_level':
                    level_name = action[1]
                    update_global_level(level_name)
                    finish = reset_level(random_finish_flag=True)
                
                # 3. Finishni qo'lda belgilash mantiqi (Faqat UI tugmasi bosilmagan bo'lsa)
                elif not action:
                    
                    map_pos = (pos[0] + int(camera.offset_x), pos[1] + int(camera.offset_y))
                    clicked_node = get_node_from_pos(map_pos, grid)
                    
                    if clicked_node and not clicked_node.start and not clicked_node.wall:
                        clear_old_finish(grid)
                        clicked_node.finish = True
                        finish = clicked_node 
                        started = False
                        player = Player(start) 
                        
            # --- Klaviatura hodisalari (Yangi boshqaruv) ---
            if event.type == pygame.KEYDOWN:
                
                # START: SPACE (Probel)
                if event.key == pygame.K_SPACE and not started:
                    if not finish or finish.wall:
                        print("Iltimos, avval Finish nuqtasini belgilang (sichqoncha chap tugmasi).")
                        continue
                        
                    print("START: Dijkstra algoritmi ishga tushirildi.")
                    
                    for row in grid:
                        for node in row:
                            node.reset_search()
                            node.is_path = False
                            
                    path = await dijkstra(start, finish, grid, draw_callback)
                    if path:
                        player.start(path)
                        started = True
                
                # RESET: R
                elif event.key == pygame.K_r:
                    print("RESET: Yangi labirint yaratildi.")
                    finish = reset_level(random_finish_flag=True)
                    started = False 
                    
                # CHANGE MAP/LEVEL: L (Level tugmalarini ko'rsatish/yashirish)
                elif event.key == pygame.K_l:
                    show_level_buttons = not show_level_buttons
                    print(f"LEVEL TANLASH: {'Ko\'rsatildi' if show_level_buttons else 'Yashirildi'}.")


        CLOCK.tick(60) 
        await asyncio.sleep(0)

    pygame.quit()
    sys.exit() 

# ---------------- RUN ----------------
if __name__ == '__main__':
    try:
        asyncio.run(main()) 
    except SystemExit:
        pass