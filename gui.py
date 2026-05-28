import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from collections import deque
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv()

URI      = os.getenv("NEO4J_URI")
USER     = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")

CARDINAL_DIRECTIONS = ["UP", "DOWN", "LEFT", "RIGHT"]
ALL_DIRECTIONS      = CARDINAL_DIRECTIONS + ["UP_RIGHT", "UP_LEFT", "DOWN_RIGHT", "DOWN_LEFT"]

INVERSE_DIRECTION = {
    "UP": "DOWN", "DOWN": "UP",
    "LEFT": "RIGHT", "RIGHT": "LEFT",
    "UP_RIGHT": "DOWN_LEFT", "DOWN_LEFT": "UP_RIGHT",
    "UP_LEFT": "DOWN_RIGHT", "DOWN_RIGHT": "UP_LEFT",
}

DIR_ES = {
    "UP": "ARRIBA ↑", "DOWN": "ABAJO ↓",
    "LEFT": "IZQUIERDA ←", "RIGHT": "DERECHA →",
    "UP_RIGHT": "ARRIBA-DERECHA ↗", "UP_LEFT": "ARRIBA-IZQUIERDA ↖",
    "DOWN_RIGHT": "ABAJO-DERECHA ↘", "DOWN_LEFT": "ABAJO-IZQUIERDA ↙",
}

OUTWARD_ARC = {         
    "RIGHT": (270, 180),
    "LEFT":  (90,  180), # left-facing half
    "UP":    (0,   180), 
    "DOWN":  (180, 180), # bottom-facing half
}
INWARD_ARC = {          
    "RIGHT": (90,  180),
    "LEFT":  (270, 180),
    "UP":    (180, 180),
    "DOWN":  (0,   180),
}

CELL_W  = 92  
CELL_H  = 78  
MARGIN  = 10   
TAB_R   = 8   
PAD     = 48   

C_UNPLACED = "#CCCCCC"
C_PLACED   = "#7EC8E3"
C_CURRENT  = "#FF9F45"
C_START    = "#FFD700"
C_MISSING  = "#FF6B6B"
C_BG       = "#F0F0F0"
C_OUTLINE  = "#444444"
C_CANVAS   = "#ffffff"


class PuzzleSolverGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Puzzle Solver — Neo4j")
        self.root.configure(bg=C_BG)
        self.driver = GraphDatabase.driver(
            URI, auth=(USER, PASSWORD), notifications_min_severity="OFF"
        )

        self.puzzle_id    = None
        self.shape        = "regular"
        self.pieces: dict = {}          
        self.connectors: dict = {}      
        self.steps: list  = []
        self.current_step = -1
        self.placed: set  = set()
        self.start_id     = None

        self._build_ui()
        self._load_puzzles()

    # Neo4j 
    def _run(self, query, **params):
        with self.driver.session() as s:
            return s.run(query, **params).data()

    # UI
    def _build_ui(self):
        bar = tk.Frame(self.root, bg=C_BG)
        bar.pack(fill=tk.X, padx=12, pady=(10, 4))
        tk.Label(bar, text="Rompecabezas:", bg=C_BG, fg="black", font=("Arial", 11)).pack(side=tk.LEFT)
        self.puzzle_var   = tk.StringVar()
        self.puzzle_combo = ttk.Combobox(bar, textvariable=self.puzzle_var,
                                         state="readonly", width=34)
        self.puzzle_combo.pack(side=tk.LEFT, padx=6)
        self.puzzle_combo.bind("<<ComboboxSelected>>", self._on_puzzle_selected)

        self.canvas = tk.Canvas(self.root, bg=C_CANVAS, width=600, height=400,
                                highlightthickness=1, highlightbackground="#AAAAAA")
        self.canvas.pack(padx=12, pady=6, expand=True, fill=tk.BOTH)

        # Legend
        leg = tk.Frame(self.root, bg=C_BG)
        leg.pack(pady=(0, 4))
        for color, label in [
            (C_START,   "Pieza inicial"),
            (C_CURRENT, "Pieza actual"),
            (C_PLACED,  "Ya colocada"),
            (C_UNPLACED,"Pendiente"),
            (C_MISSING, "Faltante"),
        ]:
            tk.Label(leg, bg=color, width=2, relief="solid", bd=1).pack(side=tk.LEFT, padx=(8, 2))
            tk.Label(leg, text=label, bg=C_BG, fg="black", font=("Arial", 9)).pack(side=tk.LEFT)

        # Connector legend
        conn_leg = tk.Frame(self.root, bg=C_BG)
        conn_leg.pack(pady=(0, 2))
        tk.Label(conn_leg, text="Conectores:", bg=C_BG, fg="black", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=(8, 4))
        tk.Label(conn_leg, text="▶ pestaña (saliente)", bg=C_BG, fg="black", font=("Arial", 9)).pack(side=tk.LEFT, padx=4)
        tk.Label(conn_leg, text="◀ ranura (entrante)", bg=C_BG, fg="black", font=("Arial", 9)).pack(side=tk.LEFT, padx=4)

        self.step_label = tk.Label(self.root, text="Selecciona un rompecabezas para comenzar.",
                                   font=("Arial", 12, "bold"), bg=C_BG, fg="black")
        self.step_label.pack(pady=(6, 2))

        self.desc_label = tk.Label(self.root, text="", font=("Arial", 11), bg=C_BG,
                                   fg="black", wraplength=660, justify="center")
        self.desc_label.pack(pady=(0, 6))

        ctrl = tk.Frame(self.root, bg=C_BG)
        ctrl.pack(pady=(0, 14))
        self.btn_prev = tk.Button(ctrl, text="◀  Anterior", width=13, command=self._prev_step,
                                  state=tk.DISABLED, font=("Arial", 11), bg="#DDDDDD", fg="black")
        self.btn_prev.pack(side=tk.LEFT, padx=6)
        self.btn_start = tk.Button(ctrl, text="Elegir pieza inicial", width=18,
                                   command=self._choose_start, font=("Arial", 11), bg=C_START, fg="black")
        self.btn_start.pack(side=tk.LEFT, padx=6)
        self.btn_next = tk.Button(ctrl, text="Siguiente  ▶", width=13, command=self._next_step,
                                  state=tk.DISABLED, font=("Arial", 11), bg="#DDDDDD", fg="black")
        self.btn_next.pack(side=tk.LEFT, padx=6)

    def _load_puzzles(self):
        puzzles = self._run(
            "MATCH (r:Puzzle) RETURN r.id AS id, r.name AS name, r.shape AS shape ORDER BY r.id"
        )
        self._puzzle_map = {f"[{p['id']}] {p['name']}": p for p in puzzles}
        self.puzzle_combo["values"] = list(self._puzzle_map.keys())

    def _on_puzzle_selected(self, _=None):
        key = self.puzzle_var.get()
        if key not in self._puzzle_map:
            return
        p = self._puzzle_map[key]
        self.puzzle_id = p["id"]
        self.shape     = p["shape"]

        rows = self._run("""
            MATCH (p:Piece {puzzle_id: $pid})
            RETURN p.id AS id, p.x AS x, p.y AS y, p.available AS available
        """, pid=self.puzzle_id)
        self.pieces = {r["id"]: r for r in rows}

        self._load_connectors()

        self.steps = []
        self.current_step = -1
        self.placed = set()
        self.start_id = None

        self._resize_canvas()
        self._redraw_all()
        self.step_label.config(text="Elige una pieza inicial para comenzar.")
        self.desc_label.config(text="")
        self.btn_next.config(state=tk.DISABLED)
        self.btn_prev.config(state=tk.DISABLED)

    def _load_connectors(self):
        dirs    = CARDINAL_DIRECTIONS if self.shape == "regular" else ALL_DIRECTIONS
        dir_str = "|".join(dirs)

        edges = self._run(f"""
            MATCH (a:Piece {{puzzle_id: $pid}})-[r:{dir_str}]->(b:Piece {{puzzle_id: $pid}})
            RETURN a.id AS from_id, type(r) AS direction, b.id AS to_id
        """, pid=self.puzzle_id)

        self.connectors = {pid: {d: "flat" for d in CARDINAL_DIRECTIONS}
                           for pid in self.pieces}

        for row in edges:
            f, t, d = row["from_id"], row["to_id"], row["direction"]
            if d not in CARDINAL_DIRECTIONS:
                continue
            if f in self.connectors:
                self.connectors[f][d] = "out"
            if t in self.connectors:
                self.connectors[t][INVERSE_DIRECTION[d]] = "in"

    def _resize_canvas(self):
        if not self.pieces:
            return
        max_x = max(p["x"] for p in self.pieces.values())
        max_y = max(p["y"] for p in self.pieces.values())
        w = (max_x + 1) * CELL_W + 2 * PAD
        h = (max_y + 1) * CELL_H + 2 * PAD
        self.canvas.config(width=max(w, 420), height=max(h, 320))

    def _cell_center(self, gx, gy):
        return PAD + gx * CELL_W + CELL_W // 2, PAD + gy * CELL_H + CELL_H // 2

    def _draw_piece(self, pid, fill):
        p  = self.pieces[pid]
        cx, cy = self._cell_center(p["x"], p["y"])
        hw = (CELL_W - 2 * MARGIN) // 2   
        hh = (CELL_H - 2 * MARGIN) // 2   
        tag = f"piece_{pid}"
        conns = self.connectors.get(pid, {})

        self.canvas.delete(tag)

        self.canvas.create_rectangle(
            cx - hw, cy - hh, cx + hw, cy + hh,
            fill=fill, outline="", tags=tag
        )

        edge_pos = {
            "RIGHT": (cx + hw, cy),
            "LEFT":  (cx - hw, cy),
            "UP":    (cx,      cy - hh),
            "DOWN":  (cx,      cy + hh),
        }
        r = TAB_R
        for direc, (ex, ey) in edge_pos.items():
            conn = conns.get(direc, "flat")
            bbox = (ex - r, ey - r, ex + r, ey + r)

            if conn == "out":
                s, ext = OUTWARD_ARC[direc]
                self.canvas.create_arc(*bbox, start=s, extent=ext,
                                       fill=fill, outline=C_OUTLINE,
                                       style=tk.CHORD, width=1, tags=tag)

            elif conn == "in":
                s, ext = INWARD_ARC[direc]
                self.canvas.create_arc(*bbox, start=s, extent=ext,
                                       fill=C_CANVAS, outline=C_OUTLINE,
                                       style=tk.CHORD, width=1, tags=tag)

        for direc, (ex, ey) in edge_pos.items():
            conn = conns.get(direc, "flat")
            if direc == "RIGHT":
                x0, y0, x1, y1 = cx + hw, cy - hh, cx + hw, cy + hh
            elif direc == "LEFT":
                x0, y0, x1, y1 = cx - hw, cy - hh, cx - hw, cy + hh
            elif direc == "UP":
                x0, y0, x1, y1 = cx - hw, cy - hh, cx + hw, cy - hh
            else: 
                x0, y0, x1, y1 = cx - hw, cy + hh, cx + hw, cy + hh

            if conn == "flat":
                self.canvas.create_line(x0, y0, x1, y1,
                                        fill=C_OUTLINE, width=2, tags=tag)
            else:
                if direc in ("RIGHT", "LEFT"):
                    self.canvas.create_line(x0, y0, x0, ey - r,
                                            fill=C_OUTLINE, width=2, tags=tag)
                    self.canvas.create_line(x0, ey + r, x1, y1,
                                            fill=C_OUTLINE, width=2, tags=tag)
                else:
                    self.canvas.create_line(x0, y0, ex - r, y0,
                                            fill=C_OUTLINE, width=2, tags=tag)
                    self.canvas.create_line(ex + r, y0, x1, y1,
                                            fill=C_OUTLINE, width=2, tags=tag)

        for cx2, cy2 in [(cx-hw, cy-hh), (cx+hw, cy-hh),
                         (cx-hw, cy+hh), (cx+hw, cy+hh)]:
            self.canvas.create_rectangle(cx2-1, cy2-1, cx2+1, cy2+1,
                                         fill=C_OUTLINE, outline="", tags=tag)

        label = str(pid) if p["available"] else f"{pid}\n(falta)"
        self.canvas.create_text(cx, cy, text=label,
                        font=("Arial", 10, "bold"), fill="black", tags=tag)

    def _draw_arrow(self, from_id, to_id):
        fp = self.pieces[from_id]
        tp = self.pieces[to_id]
        fx, fy = self._cell_center(fp["x"], fp["y"])
        tx, ty = self._cell_center(tp["x"], tp["y"])
        self.canvas.create_line(fx, fy, tx, ty, arrow=tk.LAST, fill="#C03000",
                                width=3, arrowshape=(14, 18, 6), tags="arrow")

    def _redraw_all(self):
        self.canvas.delete("all")
        for pid, p in self.pieces.items():
            self._draw_piece(pid, C_UNPLACED if p["available"] else C_MISSING)

    def _repaint_placed(self):
        for pid in self.placed:
            if pid == self.start_id:
                self._draw_piece(pid, C_START)
            else:
                p = self.pieces[pid]
                self._draw_piece(pid, C_PLACED if p["available"] else C_MISSING)

    def _choose_start(self):
        if not self.pieces:
            messagebox.showwarning("Sin datos", "Primero carga un rompecabezas.")
            return
        ids = sorted(self.pieces.keys())
        start = simpledialog.askinteger(
            "Pieza inicial",
            f"Ingresa el ID de la pieza de inicio\n(disponibles: {ids[0]}–{ids[-1]}):",
            parent=self.root, minvalue=ids[0], maxvalue=ids[-1]
        )
        if start is None or start not in self.pieces:
            return
        self.start_id = start
        self._compute_steps()

    def _compute_steps(self):
        dirs    = CARDINAL_DIRECTIONS if self.shape == "regular" else ALL_DIRECTIONS
        dir_str = "|".join(dirs)

        raw = self._run(f"""
            MATCH (a:Piece {{puzzle_id: $pid}})-[r:{dir_str}]->(b:Piece {{puzzle_id: $pid}})
            RETURN a.id AS from_id, a.available AS from_avail,
                   type(r) AS direction,
                   b.id AS to_id, b.available AS to_avail
        """, pid=self.puzzle_id)

        adj, edge = {}, {}
        for row in raw:
            f, t, d = row["from_id"], row["to_id"], row["direction"]
            adj.setdefault(f, []).append(t)
            edge[(f, t)] = row
            adj.setdefault(t, []).append(f)
            edge[(t, f)] = {
                "from_id": t, "from_avail": row["to_avail"],
                "direction": INVERSE_DIRECTION[d],
                "to_id": f, "to_avail": row["from_avail"],
            }

        visited = {self.start_id}
        queue   = deque([self.start_id])
        self.steps = []
        while queue:
            cur = queue.popleft()
            for nb in adj.get(cur, []):
                if nb not in visited:
                    visited.add(nb)
                    queue.append(nb)
                    self.steps.append(edge[(cur, nb)])

        self.current_step = -1
        self.placed = {self.start_id}
        self._redraw_all()
        self._draw_piece(self.start_id, C_START)
        total = len(self.steps)
        self.step_label.config(
            text=f"Pieza inicial: {self.start_id}   —   Paso 0 de {total}"
        )
        self.desc_label.config(
            text=f"Coloca la pieza {self.start_id} como punto de partida."
        )
        self.btn_next.config(state=tk.NORMAL if self.steps else tk.DISABLED)
        self.btn_prev.config(state=tk.DISABLED)

    def _next_step(self):
        if self.current_step >= len(self.steps) - 1:
            return
        self.current_step += 1
        step    = self.steps[self.current_step]
        from_id = step["from_id"]
        to_id   = step["to_id"]
        avail   = step["to_avail"]
        direc   = step["direction"]

        self.placed.add(to_id)
        self._repaint_placed()
        self._draw_piece(to_id, C_CURRENT if avail else C_MISSING)

        self.canvas.delete("arrow")
        if avail:
            self._draw_arrow(from_id, to_id)

        n, total = self.current_step + 1, len(self.steps)
        self.step_label.config(text=f"Paso {n} de {total}")
        if avail:
            self.desc_label.config(
                text=(
                    f"Encaja la pieza  {to_id}  en la siguiente dirección:  {DIR_ES[direc]}  de la pieza  {from_id}.\n"
                    f"La pestaña de la pieza {from_id} encaja en la ranura de la pieza {to_id}."
                )
            )
        else:
            self.desc_label.config(
                text=f"⚠  La pieza {to_id} está FALTANTE — omite este paso."
            )

        self.btn_prev.config(state=tk.NORMAL)
        if self.current_step >= total - 1:
            self.btn_next.config(state=tk.DISABLED)
            self.step_label.config(text=f"✓  ¡Rompecabezas completado!  ({total} pasos)")

    def _prev_step(self):
        if self.current_step < 0:
            return
        removed = self.steps[self.current_step]["to_id"]
        self.placed.discard(removed)
        self.current_step -= 1

        self._redraw_all()
        self._repaint_placed()
        self.canvas.delete("arrow")

        if self.current_step >= 0:
            step    = self.steps[self.current_step]
            from_id = step["from_id"]
            to_id   = step["to_id"]
            avail   = step["to_avail"]
            direc   = step["direction"]
            self._draw_piece(to_id, C_CURRENT if avail else C_MISSING)
            if avail:
                self._draw_arrow(from_id, to_id)
            n = self.current_step + 1
            self.step_label.config(text=f"Paso {n} de {len(self.steps)}")
            self.desc_label.config(
                text=(
                    f"Encaja la pieza  {to_id}  al  {DIR_ES[direc]}  de la pieza  {from_id}.\n"
                    f"La pestaña de la pieza {from_id} encaja en la ranura de la pieza {to_id}."
                    if avail else
                    f"⚠  La pieza {to_id} está FALTANTE — omite este paso."
                )
            )
        else:
            self.step_label.config(
                text=f"Pieza inicial: {self.start_id}   —   Paso 0 de {len(self.steps)}"
            )
            self.desc_label.config(
                text=f"Coloca la pieza {self.start_id} como punto de partida."
            )

        self.btn_next.config(state=tk.NORMAL)
        if self.current_step < 0:
            self.btn_prev.config(state=tk.DISABLED)


def main():
    root = tk.Tk()
    app  = PuzzleSolverGUI(root)
    root.mainloop()
    app.driver.close()


if __name__ == "__main__":
    main()
