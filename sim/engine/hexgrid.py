# -*- coding: utf-8 -*-
"""헥스 그리드 8열 × 7행 (가로 보드). odd-q 오프셋 좌표(홀수 열이 반 칸 아래로 밀림) ↔ 큐브 좌표.
odd-q 레이아웃은 180° 회전(col→7-col, row→6-row)에 대해 대칭이므로 양 팀이 동일한 기하를 본다(TFT 보드를 90° 돌린 것과 동일)."""
COLS, ROWS = 8, 7


def offset_to_cube(col, row):
    x = col
    z = row - (col - (col & 1)) // 2
    y = -x - z
    return (x, y, z)


_CUBE = {(c, r): offset_to_cube(c, r) for c in range(COLS) for r in range(ROWS)}


def dist(a, b):
    ax, ay, az = _CUBE[a]
    bx, by, bz = _CUBE[b]
    return max(abs(ax - bx), abs(ay - by), abs(az - bz))


_NEIGH_EVEN = [(1, 0), (1, -1), (0, -1), (-1, -1), (-1, 0), (0, 1)]
_NEIGH_ODD = [(1, 1), (1, 0), (0, -1), (-1, 0), (-1, 1), (0, 1)]


def neighbors(cell):
    c, r = cell
    out = []
    for dc, dr in (_NEIGH_ODD if c & 1 else _NEIGH_EVEN):
        nc, nr = c + dc, r + dr
        if 0 <= nc < COLS and 0 <= nr < ROWS:
            out.append((nc, nr))
    return out


_NEIGHBORS = {(c, r): neighbors((c, r)) for c in range(COLS) for r in range(ROWS)}
ALL_CELLS = [(c, r) for c in range(COLS) for r in range(ROWS)]
_DIST = {(a, b): dist(a, b) for a in ALL_CELLS for b in ALL_CELLS}


def hdist(a, b):
    return _DIST[(a, b)]


def hneighbors(cell):
    return _NEIGHBORS[cell]


def cells_within(cell, radius):
    return [c for c in ALL_CELLS if _DIST[(cell, c)] <= radius]
