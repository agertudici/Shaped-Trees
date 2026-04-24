# Iteration 5: Ground-Up Refactor for Systematic Space-Filling Fractal Tree
# This version implements a Segment class, SpatialGrid for collision,
# and a new growth orchestration for systematic subdivision and "baby fractal" filling.

import pygame
import math
import random
import sys

# --- Parameters (Adjustable) ---
W, H = 800, 800

# Boundary shape: 'circle', 'heart', or 'custom'
BOUNDARY_SHAPE = 'circle'
SHOW_BOUNDARY = False  # Set to True to see the outline, False to hide it
CIRCLE_CENTER = (W / 2, H * 0.5)
CIRCLE_RADIUS = H * 0.4

TRUNK_COUNT = 1
TRUNK_LENGTH = 220
TRUNK_SPREAD = math.pi / 12 # Spread for multiple trunks

# Main Branching Parameters (Skeleton)
SKELETON_ANGLE_BASE = math.pi / 5
SKELETON_ANGLE_JITTER = math.pi / 25
SKELETON_LENGTH_FACTOR = 0.78
SKELETON_LENGTH_JITTER = 0.1
SKELETON_DEPTH_MAX = 10 # Pushes skeleton to the top boundary before subdivision

INITIAL_BRANCH_COUNT = 3 # Number of main limbs to sprout from the trunk(s)

# Filling/Subdivision Parameters
# Ratios for subdividing parent segments (e.g., 0.5 for halfway, 0.25/0.75 for quarters)
SUBDIVISION_RATIOS = [0.5, 0.25, 0.75, 0.125, 0.375, 0.625, 0.875]
MINI_FRACTAL_DEPTH = 5 # Increased depth for much better density in the canopy
MINI_FRACTAL_ANGLE_BASE = math.pi / 4 # More aggressive branching for fill
MINI_FRACTAL_ANGLE_JITTER = math.pi / 15
MINI_FRACTAL_LENGTH_FACTOR = 0.6 # Smaller length factor for baby fractals

# Collision Parameters
R_MIN = 10      # Minimum clearance between branches (main branches)
R_MIN_FILL_FACTOR = 0.5 # Slightly lowered to allow tighter packing in the top
L_MIN = 4.0          # Minimum branch length
SHRINK_STEPS = 10    # More precision for collision shortening

# Drawing Parameters
BRANCH_COLOR = (60, 45, 35) # Single color as coloration is not needed
MAX_INITIAL_WIDTH = 9
EXPORT_BUTTON_RECT = pygame.Rect(W - 130, H - 40, 120, 30)
REROLL_BUTTON_RECT = pygame.Rect(10, H - 40, 120, 30) # Bottom-left corner

# Spatial Grid Parameters
GRID_CELL_SIZE = R_MIN * 2 # Cell size for spatial partitioning

# --- Global Data Structures ---
segments = []  # List of Segment objects, indexed by their ID
segment_id_counter = 0

# --- Helper Functions ---
def dist(p1, p2):
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

def almost_equal(p1, p2, eps=1e-4):
    return abs(p1[0] - p2[0]) < eps and abs(p1[1] - p2[1]) < eps

# --- Segment Class ---
class Segment:
    def __init__(self, p1, p2, angle, length, depth, parent_id=None):
        global segment_id_counter
        self.id = segment_id_counter
        segment_id_counter += 1
        self.p1 = p1
        self.p2 = p2
        self.angle = angle
        self.length = length
        self.depth = depth
        self.parent_id = parent_id
        self.bbox = self._calculate_bbox()

    def _calculate_bbox(self):
        min_x = min(self.p1[0], self.p2[0])
        max_x = max(self.p1[0], self.p2[0])
        min_y = min(self.p1[1], self.p2[1])
        max_y = max(self.p1[1], self.p2[1])
        return (min_x, min_y, max_x, max_y)

    def get_bbox_expanded(self, r):
        min_x, min_y, max_x, max_y = self.bbox
        return (min_x - r, min_y - r, max_x + r, max_y + r)

    def __repr__(self):
        return f"Segment(id={self.id}, p1={self.p1}, p2={self.p2}, depth={self.depth})"

# --- Spatial Grid for Collision Detection ---
class SpatialGrid:
    def __init__(self, cell_size, width, height):
        self.cell_size = cell_size
        self.grid_width = math.ceil(width / cell_size)
        self.grid_height = math.ceil(height / cell_size)
        self.grid = {} # (col, row) -> list of segment IDs

    def _get_cells_for_bbox(self, bbox_expanded):
        min_x, min_y, max_x, max_y = bbox_expanded
        
        start_col = max(0, math.floor(min_x / self.cell_size))
        end_col = min(self.grid_width - 1, math.floor(max_x / self.cell_size))
        start_row = max(0, math.floor(min_y / self.cell_size))
        end_row = min(self.grid_height - 1, math.floor(max_y / self.cell_size))

        cells = []
        for col in range(start_col, end_col + 1):
            for row in range(start_row, end_row + 1):
                cells.append((col, row))
        return cells

    def add_segment(self, segment):
        # Use R_MIN for grid indexing to ensure all potential colliders are in cells
        bbox_expanded = segment.get_bbox_expanded(R_MIN) 
        cells = self._get_cells_for_bbox(bbox_expanded)
        for cell in cells:
            if cell not in self.grid:
                self.grid[cell] = []
            self.grid[cell].append(segment)

    def get_nearby_segments(self, segment, r_check):
        # r_check is the specific radius for the current collision test
        bbox_expanded = segment.get_bbox_expanded(r_check)
        cells = self._get_cells_for_bbox(bbox_expanded)
        
        nearby = set()
        for cell in cells:
            if cell in self.grid:
                nearby.update(self.grid[cell])
        return nearby

# --- Boundary Classes and Functions ---
class PolygonMask:
    """Defines a boundary using a list of vertices (Point-in-Polygon)."""
    def __init__(self, points):
        self.points = points

    def __call__(self, x, y):
        """Ray casting algorithm to check if (x, y) is inside the polygon."""
        n = len(self.points)
        inside = False
        p1x, p1y = self.points[0]
        for i in range(n + 1):
            p2x, p2y = self.points[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xints:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

def inside_circle(x, y):
    cx, cy = CIRCLE_CENTER
    return dist((x, y), (cx, cy)) <= CIRCLE_RADIUS

def inside_heart(x, y):
    nx, ny = (x - W / 2) / (W * 0.38), (H * 0.58 - y) / (H * 0.38)
    return (nx**2 + ny**2 - 1)**3 - nx**2 * ny**3 <= 0

# Registry of available shapes
SHAPES = {
    'circle': inside_circle,
    'circle_poly': PolygonMask([(W/2 + CIRCLE_RADIUS * math.cos(a), H*0.5 + CIRCLE_RADIUS * math.sin(a)) 
                                for a in [i * 2 * math.pi / 64 for i in range(64)]]),
    'heart': inside_heart,
    'square': PolygonMask([(W/2 - CIRCLE_RADIUS, H*0.5 - CIRCLE_RADIUS), (W/2 + CIRCLE_RADIUS, H*0.5 - CIRCLE_RADIUS), 
                           (W/2 + CIRCLE_RADIUS, H*0.5 + CIRCLE_RADIUS), (W/2 - CIRCLE_RADIUS, H*0.5 + CIRCLE_RADIUS)]),
    'rectangle': PolygonMask([(W/2 - CIRCLE_RADIUS * 0.8, H*0.5 - CIRCLE_RADIUS * 1.2), 
                              (W/2 + CIRCLE_RADIUS * 0.8, H*0.5 - CIRCLE_RADIUS * 1.2),
                              (W/2 + CIRCLE_RADIUS * 0.8, H*0.5 + CIRCLE_RADIUS * 1.2), 
                              (W/2 - CIRCLE_RADIUS * 0.8, H*0.5 + CIRCLE_RADIUS * 1.2)]),
    'hexagon': PolygonMask([(W/2 + CIRCLE_RADIUS * math.cos(a), H*0.5 + CIRCLE_RADIUS * math.sin(a)) 
                            for a in [-math.pi/2 + i * 2 * math.pi / 6 for i in range(6)]]),
    'star': PolygonMask([(W/2 + (CIRCLE_RADIUS if i % 2 == 0 else CIRCLE_RADIUS * 0.4) * math.cos(-math.pi/2 + i * math.pi / 5), 
                          H*0.5 + (CIRCLE_RADIUS if i % 2 == 0 else CIRCLE_RADIUS * 0.4) * math.sin(-math.pi/2 + i * math.pi / 5)) 
                         for i in range(10)]),
    'custom': PolygonMask([(W*0.2, H*0.8), (W*0.5, H*0.2), (W*0.8, H*0.8)]) # A simple triangle
}

is_inside_boundary = SHAPES.get(BOUNDARY_SHAPE, inside_circle)

# --- Collision Detection ---
def segment_segment_dist(p1, q1, p2, q2):
    # Robust shortest distance between two line segments (from previous iterations)
    ux, uy = q1[0] - p1[0], q1[1] - p1[1]
    vx, vy = q2[0] - p2[0], q2[1] - p2[1]
    wx, wy = p1[0] - p2[0], p1[1] - p2[1]
    a = ux*ux + uy*uy
    b = ux*vx + uy*vy
    c = vx*vx + vy*vy
    d = ux*wx + uy*wy
    e = vx*wx + vy*wy
    D = a*c - b*b
    sc, sN, sD = 0.0, 0.0, D
    tc, tN, tD = 0.0, 0.0, D
    EPS = 1e-8
    if D < EPS:
        sN, sD, tN, tD = 0.0, 1.0, e, c
    else:
        sN, tN = (b*e - c*d), (a*e - b*d)
        if sN < 0.0: sN, tN, tD = 0.0, e, c
        elif sN > sD: sN, tN, tD = sD, e + b, c
    if tN < 0.0:
        tN = 0.0
        if -d < 0.0: sN = 0.0
        elif -d > a: sN = sD
        else: sN, sD = -d, a
    elif tN > tD:
        tN = tD
        if (-d + b) < 0.0: sN = 0.0
        elif (-d + b) > a: sN = sD
        else: sN, sD = (-d + b), a
    sc = 0.0 if abs(sN) < EPS else sN / sD
    tc = 0.0 if abs(tN) < EPS else tN / tD
    dx, dy = wx + (sc * ux) - (tc * vx), wy + (sc * uy) - (tc * vy)
    return math.hypot(dx, dy)

def collides_segment(new_seg, r_check, spatial_grid):
    # Use spatial grid to get potential colliders
    for existing_seg in spatial_grid.get_nearby_segments(new_seg, r_check):
        # Ignore self and immediate parent to allow subdivision sprouts from the middle
        if new_seg.id == existing_seg.id or new_seg.parent_id == existing_seg.id:
            continue

        # Ignore shared endpoints (Option A logic)
        if (almost_equal(new_seg.p1, existing_seg.p1) or almost_equal(new_seg.p1, existing_seg.p2) or
            almost_equal(new_seg.p2, existing_seg.p1) or almost_equal(new_seg.p2, existing_seg.p2)):
            continue
        
        # Check if segments are closer than the sum of their clearance radii
        if segment_segment_dist(new_seg.p1, new_seg.p2, existing_seg.p1, existing_seg.p2) < (2 * r_check):
            return True
    return False

def shorten_until_free(cand_seg, r_check, l_min, steps, spatial_grid):
    if not collides_segment(cand_seg, r_check, spatial_grid):
        return cand_seg
    
    p1 = cand_seg.p1
    p2_orig = cand_seg.p2
    
    lo, hi = 0.0, 1.0
    best_seg = None
    
    for _ in range(steps):
        mid = (lo + hi) / 2.0
        
        # Calculate new end point
        mx = p1[0] + (p2_orig[0] - p1[0]) * mid
        my = p1[1] + (p2_orig[1] - p1[1]) * mid
        
        current_length = dist(p1, (mx, my))
        if current_length < l_min:
            hi = mid # Too short, try shorter
            continue
            
        # Create a temporary segment for collision check (ID doesn't matter for temp)
        temp_seg = Segment(p1, (mx, my), cand_seg.angle, current_length, cand_seg.depth, cand_seg.parent_id)
        
        if not collides_segment(temp_seg, r_check, spatial_grid):
            best_seg = temp_seg
            lo = mid # This length is good, try longer
        else:
            hi = mid # This length collides, try shorter
            
    if best_seg and dist(best_seg.p1, best_seg.p2) >= l_min:
        return best_seg
    return None

# --- Growth Functions ---
def initialize_trunks(spatial_grid, all_segments_list):
    cx, cy = W / 2, H * 0.975 # Lowered to start closer to the bottom boundary edge
    
    initial_frontier = []
    for i in range(TRUNK_COUNT):
        ang = -math.pi/2 + (i - (TRUNK_COUNT-1)/2) * TRUNK_SPREAD
        
        new_seg = Segment((cx, cy), 
                          (cx + TRUNK_LENGTH * math.cos(ang), cy + TRUNK_LENGTH * math.sin(ang)),
                          ang, TRUNK_LENGTH, 0)
        
        all_segments_list.append(new_seg) # Add to global list
        spatial_grid.add_segment(new_seg) # Add to spatial grid
        initial_frontier.append(new_seg)
    return initial_frontier

def grow_main_branches(initial_frontier, spatial_grid, all_segments_list):
    frontier = initial_frontier
    
    for depth in range(1, SKELETON_DEPTH_MAX + 1):
        next_frontier = []
        for parent_seg in frontier:
            base_ang = parent_seg.angle
            
            # Use the customizable count only for the first split off the trunk
            # Subsequent skeleton growth remains binary for a traditional fractal look
            branch_count = INITIAL_BRANCH_COUNT if parent_seg.depth == 0 else 2
            
            for i in range(branch_count):
                if branch_count > 1:
                    # Distribute branches evenly across the spread defined by ANGLE_BASE
                    angle_offset = -SKELETON_ANGLE_BASE + (i * (2 * SKELETON_ANGLE_BASE) / (branch_count - 1))
                else:
                    angle_offset = 0
                
                ang = base_ang + angle_offset + random.uniform(-SKELETON_ANGLE_JITTER, SKELETON_ANGLE_JITTER)
                length = parent_seg.length * (SKELETON_LENGTH_FACTOR * (1 + random.uniform(-SKELETON_LENGTH_JITTER, SKELETON_LENGTH_JITTER)))
                
                cand_seg = Segment(parent_seg.p2, 
                                   (parent_seg.p2[0] + length * math.cos(ang), parent_seg.p2[1] + length * math.sin(ang)),
                                   ang, length, depth, parent_seg.id)
                
                if not is_inside_boundary(cand_seg.p2[0], cand_seg.p2[1]):
                    continue
                
                ok_seg = shorten_until_free(cand_seg, R_MIN, L_MIN, SHRINK_STEPS, spatial_grid)
                
                if ok_seg:
                    all_segments_list.append(ok_seg)
                    spatial_grid.add_segment(ok_seg)
                    next_frontier.append(ok_seg)
        frontier = next_frontier
        if not frontier:
            break
    # No explicit return needed, all_segments_list is modified in place

def grow_mini_fractal(seed_seg, current_mini_depth, r_check_factor, spatial_grid, all_segments_list):
    if current_mini_depth >= MINI_FRACTAL_DEPTH or seed_seg.length < L_MIN:
        return

    p2 = seed_seg.p2
    base_ang = seed_seg.angle
    
    for sign in (1, -1): # Two branches per parent
        ang = base_ang + sign * MINI_FRACTAL_ANGLE_BASE + random.uniform(-MINI_FRACTAL_ANGLE_JITTER, MINI_FRACTAL_ANGLE_JITTER)
        length = seed_seg.length * MINI_FRACTAL_LENGTH_FACTOR * random.uniform(0.8, 1.2) # Some jitter for variety
        
        cand_seg = Segment(p2, 
                           (p2[0] + length * math.cos(ang), p2[1] + length * math.sin(ang)),
                           ang, length, seed_seg.depth + 1, seed_seg.id)
        
        if not is_inside_boundary(cand_seg.p2[0], cand_seg.p2[1]):
            continue
            
        # Use a more relaxed R_MIN for baby fractals
        ok_seg = shorten_until_free(cand_seg, R_MIN * r_check_factor, L_MIN, SHRINK_STEPS, spatial_grid)
        
        if ok_seg:
            all_segments_list.append(ok_seg)
            spatial_grid.add_segment(ok_seg)
            grow_mini_fractal(ok_seg, current_mini_depth + 1, r_check_factor, spatial_grid, all_segments_list)

def subdivide_and_grow_fill(spatial_grid, all_segments_list):
    # Process segments in order of creation (roughly depth-first)
    # This ensures we "crawl back" and subdivide older, larger branches first.
    
    for t_ratio in SUBDIVISION_RATIOS:
        # Create a copy of segments list at the start of each ratio pass
        # to avoid issues with modifying the list while iterating.
        segments_for_this_pass = list(all_segments_list) 
        
        for parent_seg in segments_for_this_pass:
            # Skip the very first trunk segment (id=0) if TRUNK_COUNT is 1
            # This prevents sprouting from the absolute base of the trunk.
            if TRUNK_COUNT == 1 and parent_seg.id == 0:
                continue

            # Find the subdivision point along the parent segment
            px = parent_seg.p1[0] + (parent_seg.p2[0] - parent_seg.p1[0]) * t_ratio
            py = parent_seg.p1[1] + (parent_seg.p2[1] - parent_seg.p1[1]) * t_ratio
            
            # Sprout two side branches from this subdivision point
            for side in [-1, 1]:
                # Angle roughly perpendicular to parent, with jitter
                side_ang = parent_seg.angle + (side * MINI_FRACTAL_ANGLE_BASE) + random.uniform(-MINI_FRACTAL_ANGLE_JITTER, MINI_FRACTAL_ANGLE_JITTER)
                side_len = parent_seg.length * MINI_FRACTAL_LENGTH_FACTOR
                
                if side_len < L_MIN:
                    continue
                
                cand_seg = Segment((px, py), 
                                   (px + side_len * math.cos(side_ang), py + side_len * math.sin(side_ang)),
                                   side_ang, side_len, parent_seg.depth + 1, parent_seg.id)
                
                if not is_inside_boundary(cand_seg.p2[0], cand_seg.p2[1]):
                    continue
                
                # Check collision with a slightly more generous margin for fill branches
                ok_seg = shorten_until_free(cand_seg, R_MIN * R_MIN_FILL_FACTOR, L_MIN, SHRINK_STEPS, spatial_grid)
                
                if ok_seg:
                    all_segments_list.append(ok_seg)
                    spatial_grid.add_segment(ok_seg)
                    # Start recursive baby fractal growth from this new segment
                    grow_mini_fractal(ok_seg, 0, R_MIN_FILL_FACTOR, spatial_grid, all_segments_list)

# --- Main Growth Orchestration ---
def grow_tree():
    global segments, segment_id_counter
    segments = [] # Reset global segments list for a fresh start
    segment_id_counter = 0 # Reset ID counter
    
    spatial_grid = SpatialGrid(GRID_CELL_SIZE, W, H)
    
    # Phase 1: Initialize trunks
    initial_frontier = initialize_trunks(spatial_grid, segments)
    
    # Phase 2: Grow main skeleton branches
    grow_main_branches(initial_frontier, spatial_grid, segments)
    
    # Phase 3: Systematically subdivide and grow baby fractals
    subdivide_and_grow_fill(spatial_grid, segments)

# --- SVG Export ---
def export_to_svg(all_segments_list, filename="fractal_tree.svg"):
    if not all_segments_list:
        return

    # Calculate heights for widths (bottom-up approach to match draw logic)
    heights = {seg.id: 1 for seg in all_segments_list}
    max_h = 1
    for seg in reversed(all_segments_list):
        if seg.parent_id is not None and seg.parent_id in heights:
            heights[seg.parent_id] = max(heights[seg.parent_id], heights[seg.id] + 1)
            max_h = max(max_h, heights[seg.parent_id])

    with open(filename, "w") as f:
        f.write(f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">\n')
        f.write(f'  <rect width="100%" height="100%" fill="#fafafa"/>\n')
        for seg in all_segments_list:
            h = heights[seg.id]
            width = max(1, int(MAX_INITIAL_WIDTH * (h / max_h) ** 0.85))
            color_str = f"rgb({BRANCH_COLOR[0]},{BRANCH_COLOR[1]},{BRANCH_COLOR[2]})"
            f.write(f'  <line x1="{seg.p1[0]}" y1="{seg.p1[1]}" x2="{seg.p2[0]}" y2="{seg.p2[1]}" '
                    f'stroke="{color_str}" stroke-width="{width}" stroke-linecap="round" />\n')
        f.write('</svg>\n')
    print(f"Successfully exported to {filename}")

# --- Drawing ---
def draw(screen, all_segments_list):
    screen.fill((250, 250, 250)) # Light background

    if not all_segments_list:
        pygame.display.flip()
        return

    # 1. Calculate "height" (distance to furthest leaf) for each segment.
    # This ensures that any branch that terminates early (height=1) is thin.
    heights = {seg.id: 1 for seg in all_segments_list}
    max_h = 1
    # Propagate height backwards from children to parents
    for seg in reversed(all_segments_list):
        if seg.parent_id is not None and seg.parent_id in heights:
            heights[seg.parent_id] = max(heights[seg.parent_id], heights[seg.id] + 1)
            max_h = max(max_h, heights[seg.parent_id])

    # Draw boundary for visualization (optional)
    if SHOW_BOUNDARY:
        if BOUNDARY_SHAPE == 'circle':
            pygame.draw.circle(screen, (200, 200, 200), CIRCLE_CENTER, int(CIRCLE_RADIUS), 1)
        elif BOUNDARY_SHAPE == 'heart' or isinstance(is_inside_boundary, PolygonMask):
            # Rough heart outline for visualization
            if BOUNDARY_SHAPE == 'heart':
                points = []
                for i in range(101):
                    t = i * 2 * math.pi / 100
                    nx = 16 * math.sin(t)**3
                    ny = 13 * math.cos(t) - 5 * math.cos(2*t) - 2 * math.cos(3*t) - math.cos(4*t)
                    points.append((W/2 + nx * (W*0.022), H*0.53 - ny * (H*0.022)))
                pygame.draw.lines(screen, (200, 200, 200), True, points, 1)
            else:
                pygame.draw.lines(screen, (200, 200, 200), True, is_inside_boundary.points, 1)

    for seg in all_segments_list:
        # 2. Width is now determined by "height" (distance to tip) instead of depth.
        # This avoids chunky blunt ends by making all leaf segments width 1.
        h = heights[seg.id]
        width = max(1, int(MAX_INITIAL_WIDTH * (h / max_h) ** 0.85))
        
        pygame.draw.line(screen, BRANCH_COLOR, seg.p1, seg.p2, width)

    # Draw Export Button
    pygame.draw.rect(screen, (220, 220, 220), EXPORT_BUTTON_RECT)
    pygame.draw.rect(screen, (100, 100, 100), EXPORT_BUTTON_RECT, 2)
    font = pygame.font.SysFont("Arial", 16)
    text = font.render("Export SVG", True, (50, 50, 50))
    text_rect = text.get_rect(center=EXPORT_BUTTON_RECT.center)
    screen.blit(text, text_rect)

    # Draw Re-roll Button
    pygame.draw.rect(screen, (220, 220, 220), REROLL_BUTTON_RECT)
    pygame.draw.rect(screen, (100, 100, 100), REROLL_BUTTON_RECT, 2)
    font = pygame.font.SysFont("Arial", 16)
    text = font.render("Re-roll", True, (50, 50, 50))
    text_rect = text.get_rect(center=REROLL_BUTTON_RECT.center)
    screen.blit(text, text_rect)


    pygame.display.flip()

# --- Main Loop ---
def main():
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("Fractal Tree Refactor - Iteration 5")
    
    grow_tree()
    draw(screen, segments)
    
    while True:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if ev.type == pygame.MOUSEBUTTONDOWN:
                if REROLL_BUTTON_RECT.collidepoint(ev.pos):
                    grow_tree() # Re-generate the tree
                    draw(screen, segments) # Re-draw with the new tree
                if EXPORT_BUTTON_RECT.collidepoint(ev.pos):
                    export_to_svg(segments)

if __name__ == "__main__":
    main()