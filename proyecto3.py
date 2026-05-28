from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

load_dotenv()

# ─────────────────────────────────────────────
#  CONFIGURACIÓN
# ─────────────────────────────────────────────
URI      = os.getenv("NEO4J_URI")
USER     = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")

if not all([URI, USER, PASSWORD]):
    raise EnvironmentError("Faltan credenciales en el archivo .env (NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)")

CARDINAL_DIRECTIONS  = ["UP", "DOWN", "LEFT", "RIGHT"]
DIAGONAL_DIRECTIONS  = ["UP_RIGHT", "UP_LEFT", "DOWN_RIGHT", "DOWN_LEFT"]
ALL_DIRECTIONS       = CARDINAL_DIRECTIONS + DIAGONAL_DIRECTIONS

# ─────────────────────────────────────────────
#  DRIVER
# ─────────────────────────────────────────────
driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

def run(query, **params):
    with driver.session() as session:
        return session.run(query, **params).data()

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────
def ask(prompt, valid=None, default=None):
    while True:
        raw = input(prompt).strip()
        if raw == "" and default is not None:
            return default
        if valid is None or raw.upper() in [v.upper() for v in valid]:
            return raw
        print(f"  Opciones válidas: {valid}")

def ask_bool(prompt):
    return ask(prompt + " (s/n): ", valid=["s", "n"]).lower() == "s"

def ask_int(prompt):
    while True:
        try:
            return int(input(prompt).strip())
        except ValueError:
            print("  Ingresa un número entero.")

def available_directions(shape):
    return CARDINAL_DIRECTIONS if shape == "regular" else ALL_DIRECTIONS

# ─────────────────────────────────────────────
#  INICIALIZACIÓN DE LA BD
# ─────────────────────────────────────────────
def init_db():
    run("CREATE CONSTRAINT piece_id IF NOT EXISTS FOR (p:Piece) REQUIRE p.id IS UNIQUE")
    run("CREATE CONSTRAINT puzzle_id IF NOT EXISTS FOR (r:Puzzle) REQUIRE r.id IS UNIQUE")
    print("  ✓ Constraints listos.\n")

# ─────────────────────────────────────────────
#  CREAR ROMPECABEZAS
# ─────────────────────────────────────────────
def create_puzzle():
    print("\n══════════════════════════════════")
    print("  REGISTRAR ROMPECABEZAS")
    print("══════════════════════════════════")

    pid        = ask_int("ID del rompecabezas: ")
    name       = input("Nombre: ").strip()
    brand      = input("Marca: ").strip()
    material   = input("Material: ").strip()
    theme      = input("Temática: ").strip()
    shape      = ask("Forma (regular/irregular): ", valid=["regular", "irregular"])
    total      = ask_int("Total de piezas: ")

    run("""
        MERGE (r:Puzzle {id: $id})
        SET r.name=$name, r.brand=$brand, r.material=$material,
            r.theme=$theme, r.shape=$shape, r.total_pieces=$total
    """, id=pid, name=name, brand=brand, material=material,
         theme=theme, shape=shape, total=total)

    print(f"  ✓ Rompecabezas '{name}' creado.\n")
    return pid, shape

# ─────────────────────────────────────────────
#  CREAR PIEZAS
# ─────────────────────────────────────────────
def create_pieces(puzzle_id):
    print("\n══════════════════════════════════")
    print("  REGISTRAR PIEZAS")
    print("  (escribe 'fin' en el ID para terminar)")
    print("══════════════════════════════════")

    pieces = []
    while True:
        raw = input("\nID de pieza (o 'fin'): ").strip()
        if raw.lower() == "fin":
            break
        try:
            pid = int(raw)
        except ValueError:
            print("  ID debe ser un número.")
            continue

        x         = ask_int("  Posición X (columna): ")
        y         = ask_int("  Posición Y (fila): ")
        available = ask_bool("  ¿Disponible?")

        run("""
            MERGE (p:Piece {id: $id})
            SET p.x=$x, p.y=$y, p.available=$available, p.puzzle_id=$puzzle_id
            WITH p
            MATCH (r:Puzzle {id: $puzzle_id})
            MERGE (p)-[:BELONGS_TO]->(r)
        """, id=pid, x=x, y=y, available=available, puzzle_id=puzzle_id)

        pieces.append(pid)
        print(f"  ✓ Pieza {pid} registrada en ({x},{y}), disponible={available}")

    print(f"\n  ✓ {len(pieces)} piezas registradas.")
    return pieces

# ─────────────────────────────────────────────
#  CREAR CONEXIONES
# ─────────────────────────────────────────────
def create_connections(shape):
    dirs = available_directions(shape)

    print("\n══════════════════════════════════")
    print("  REGISTRAR CONEXIONES")
    print(f"  Direcciones disponibles: {dirs}")
    print("  (escribe 'fin' para terminar)")
    print("══════════════════════════════════")

    count = 0
    while True:
        print()
        raw = input("Pieza ORIGEN (o 'fin'): ").strip()
        if raw.lower() == "fin":
            break
        try:
            origin = int(raw)
        except ValueError:
            print("  ID debe ser un número.")
            continue

        direction = ask(f"  Dirección {dirs}: ", valid=dirs + ["fin"]).upper()
        if direction == "FIN":
            break

        try:
            dest = int(input("  Pieza DESTINO: ").strip())
        except ValueError:
            print("  ID debe ser un número.")
            continue

        # Verificar que ambas piezas existan
        exists = run("""
            MATCH (a:Piece {id: $origin}), (b:Piece {id: $dest})
            RETURN a, b
        """, origin=origin, dest=dest)

        if not exists:
            print(f"  ✗ Piezas {origin} o {dest} no encontradas. Verifica los IDs.")
            continue

        # Crear relación dinámica según dirección
        run(f"""
            MATCH (a:Piece {{id: $origin}}), (b:Piece {{id: $dest}})
            MERGE (a)-[:{direction}]->(b)
        """, origin=origin, dest=dest)

        count += 1
        print(f"  ✓ ({origin})-[:{direction}]->({dest}) creada.")

    print(f"\n  ✓ {count} conexiones registradas.")

# ─────────────────────────────────────────────
#  VISUALIZAR GRID EN CONSOLA
# ─────────────────────────────────────────────
def visualize_puzzle(puzzle_id):
    pieces = run("""
        MATCH (p:Piece {puzzle_id: $puzzle_id})
        RETURN p.id AS id, p.x AS x, p.y AS y, p.available AS available
        ORDER BY p.y, p.x
    """, puzzle_id=puzzle_id)

    if not pieces:
        print("  No hay piezas registradas aún.")
        return

    max_x = max(p["x"] for p in pieces)
    max_y = max(p["y"] for p in pieces)

    # Construir grid
    grid = {}
    for p in pieces:
        grid[(p["x"], p["y"])] = (p["id"], p["available"])

    print("\n  VISTA DEL ROMPECABEZAS:")
    print("  " + "─" * ((max_x + 1) * 6))
    for y in range(max_y + 1):
        row = "  "
        for x in range(max_x + 1):
            if (x, y) in grid:
                pid, avail = grid[(x, y)]
                marker = f"[{pid:2d}]" if avail else f"[X{pid:2d}]"  # X = faltante
                row += marker + " "
            else:
                row += "     "
        print(row)
    print("  " + "─" * ((max_x + 1) * 6))
    print("  Leyenda: [N] = disponible  |  [XN] = faltante\n")

# ─────────────────────────────────────────────
#  ALGORITMO: ARMAR ROMPECABEZAS (BFS)
# ─────────────────────────────────────────────
def solve_puzzle(puzzle_id, shape):
    print("\n══════════════════════════════════")
    print("  ALGORITMO: ARMAR ROMPECABEZAS")
    print("══════════════════════════════════")

    start_id = ask_int("ID de pieza inicial: ")
    dirs     = available_directions(shape)
    dir_str  = "|".join(dirs)

    # BFS desde la pieza inicial usando todas las direcciones posibles
    result = run(f"""
        MATCH (start:Piece {{id: $start_id, puzzle_id: $puzzle_id}})
        CALL apoc.path.bfsTree(start, {{
            relationshipFilter: '{dir_str}>',
            maxLevel: -1
        }}) YIELD path
        WITH nodes(path) AS pieces, relationships(path) AS rels
        UNWIND range(0, size(rels)-1) AS i
        WITH pieces[i] AS from, rels[i] AS rel, pieces[i+1] AS to
        RETURN from.id AS from_id, from.available AS from_avail,
               type(rel) AS direction,
               to.id AS to_id, to.available AS to_avail
        ORDER BY from.y, from.x
    """, start_id=start_id, puzzle_id=puzzle_id)

    if not result:
        # Fallback sin APOC
        result = run(f"""
            MATCH (start:Piece {{id: $start_id, puzzle_id: $puzzle_id}})
            MATCH path = (start)-[:{dir_str}*]->(p:Piece)
            WITH relationships(path)[-1] AS rel,
                 nodes(path)[-2] AS from,
                 nodes(path)[-1] AS to
            RETURN from.id AS from_id, from.available AS from_avail,
                   type(rel) AS direction,
                   to.id AS to_id, to.available AS to_avail
            ORDER BY length(path)
        """, start_id=start_id, puzzle_id=puzzle_id)

    if not result:
        print(f"  No se encontraron conexiones desde la pieza {start_id}.")
        return

    print(f"\n  Pasos para armar desde pieza {start_id}:\n")
    step = 1
    missing = []

    for row in result:
        from_id    = row["from_id"]
        to_id      = row["to_id"]
        direction  = row["direction"]
        to_avail   = row["to_avail"]

        if not to_avail:
            missing.append(to_id)
            status = "⚠ FALTANTE — omitir"
        else:
            status = "✓"

        print(f"  Paso {step:3d}: Pieza {from_id:3d} → [{direction}] → Pieza {to_id:3d}  {status}")
        step += 1

    if missing:
        print(f"\n  ⚠ Piezas faltantes detectadas: {missing}")
        print("  El rompecabezas se armará parcialmente omitiendo esas piezas.")
    else:
        print("\n  ✓ Rompecabezas completo. Todas las piezas disponibles.")

# ─────────────────────────────────────────────
#  MENÚ PRINCIPAL
# ─────────────────────────────────────────────
def menu():
    init_db()

    puzzle_id = None
    shape     = "regular"

    while True:
        print("\n╔══════════════════════════════════╗")
        print("║   GESTOR DE ROMPECABEZAS — Neo4j ║")
        print("╠══════════════════════════════════╣")
        print("║  1. Crear rompecabezas            ║")
        print("║  2. Agregar piezas                ║")
        print("║  3. Agregar conexiones            ║")
        print("║  4. Ver grid en consola           ║")
        print("║  5. Resolver rompecabezas (BFS)   ║")
        print("║  6. Salir                         ║")
        print("╚══════════════════════════════════╝")

        if puzzle_id:
            print(f"  Rompecabezas activo: ID={puzzle_id} | Forma={shape}")

        opt = ask("\nOpción: ", valid=["1","2","3","4","5","6"])

        if opt == "1":
            puzzle_id, shape = create_puzzle()

        elif opt == "2":
            if not puzzle_id:
                puzzle_id = ask_int("ID del rompecabezas a usar: ")
                res = run("MATCH (r:Puzzle {id: $id}) RETURN r.shape AS shape", id=puzzle_id)
                shape = res[0]["shape"] if res else "regular"
            create_pieces(puzzle_id)

        elif opt == "3":
            if not puzzle_id:
                puzzle_id = ask_int("ID del rompecabezas a usar: ")
                res = run("MATCH (r:Puzzle {id: $id}) RETURN r.shape AS shape", id=puzzle_id)
                shape = res[0]["shape"] if res else "regular"
            create_connections(shape)

        elif opt == "4":
            if not puzzle_id:
                puzzle_id = ask_int("ID del rompecabezas: ")
            visualize_puzzle(puzzle_id)

        elif opt == "5":
            if not puzzle_id:
                puzzle_id = ask_int("ID del rompecabezas: ")
                res = run("MATCH (r:Puzzle {id: $id}) RETURN r.shape AS shape", id=puzzle_id)
                shape = res[0]["shape"] if res else "regular"
            solve_puzzle(puzzle_id, shape)

        elif opt == "6":
            print("\n  Hasta luego.\n")
            driver.close()
            break

if __name__ == "__main__":
    menu()