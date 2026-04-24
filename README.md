# Shaped Trees

Shaped Trees is a procedural art engine designed to grow fractal trees that fit perfectly inside specific shapes. Unlike standard fractals that just grow outward forever, this system uses a "crawl back" strategy to fill every corner of a boundary (like a heart or a star) without any branches overlapping.

## Examples

| Circle | Heart | Star | Hexagon |
| :---: | :---: | :---: | :---: |
| ![Circle](https://github.com/agertudici/Shaped-Trees/blob/main/examples/circle.png) | ![Heart](https://github.com/agertudici/Shaped-Trees/blob/main/examples/heart.png) | ![Star](https://github.com/agertudici/Shaped-Trees/blob/main/examples/star.png) | ![Hexagon](https://github.com/agertudici/Shaped-Trees/blob/main/examples/hexagon.png) |
| **Square** | **Rectangle** | | |
| ![Square](https://github.com/agertudici/Shaped-Trees/blob/main/examples/square.png) | ![Rectangle](https://github.com/agertudici/Shaped-Trees/blob/main/examples/rectangle.png) | | |

## Key Features

*   **Implicit & Polygon Boundaries**: Supports complex mathematical shapes (Heart curve) and arbitrary polygons (Star, Hexagon, Rectangle) using a Ray Casting Point-in-Polygon algorithm.
*   **Systematic Subdivision ("Crawl Back")**: After the primary skeleton is grown, the algorithm iterates back through the hierarchy to sprout "baby fractals" from subdivision points along existing limbs.
*   **Robust Collision Detection**: Uses a shortest-distance-between-line-segments algorithm combined with a **Spatial Grid** to maintain a minimum clearance ($R_{min}$) between all branches at $O(N)$ performance.
*   **Pipe Model Tapering**: Implements a bottom-up tapering logic where branch thickness is determined by the "height" of the subtree it supports, ensuring that all terminal tips are thin and blunt ends are eliminated.
*   **Vector & Raster Export**: Integrated UI to export designs as clean SVGs (for logo design/plotting) or PNGs.

## Core Architecture

### 1. Growth Phases
1.  **Skeleton Phase**: Establishes the primary trunk and major limbs to reach the edges of the boundary.
2.  **Subdivision Phase**: Crawls back to established segments at specific ratios (0.5, 0.25, etc.) to seed new growth.
3.  **Filling Phase**: Recursive "baby fractals" fill the remaining voids while respecting the global collision grid.

### 2. Collision Logic
To prevent overlapping, every candidate segment is checked against nearby segments in a `SpatialGrid`. A segment is only accepted if its distance to all non-parent segments is greater than $2 \times R_{min}$. If a collision is detected, the segment is binary-searched (`shorten_until_free`) to find the maximum possible length that fits.

## Usage

### Requirements
*   Python 3.10+
*   Pygame-ce (or standard Pygame)

### Running the Generator
Run the main script to open the interactive generator:
```bash
python Generator.py
```

### Interactive Controls
*   **Re-roll**: Generates a new random seed within the current boundary.
*   **Export SVG**: Saves a vector version of the tree to `fractal_tree.svg`.
*   **Export PNG**: Saves a clean snapshot (minus UI buttons) to `fractal_tree.png`.

## Configuration

The most common variables to play with in `Generator.py` are:
*   **`BOUNDARY_SHAPE`**: The silhouette the tree will fill. Available presets: `circle`, `square`, `rectangle` (portrait), `hexagon`, `heart`, `star`, or `custom`.
*   **`R_MIN`**: Controls the clearance between branches. Turn this up for a sparse, clean look, or down for a dense, thicket-like tree.
*   **`MAX_INITIAL_WIDTH`**: Sets the thickness of the main trunk. All branches will naturally taper down to a fine tip regardless of this setting.
*   **`SKELETON_DEPTH_MAX`**: How many times the main branches split before the "filling" logic takes over.

## License

This project is open-source and intended for creative exploration in procedural generation.

Generated with ❤️ and Geometry.
