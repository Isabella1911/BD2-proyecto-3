# Proyecto 03 — Base de Datos 2
## Setup: Neo4j con Docker

---

## 1. Correr Neo4j con Docker

Asegúrate de tener Docker Desktop abierto y corriendo, luego ejecuta en PowerShell:

```powershell
docker run --name neo4j-puzzle `
  -p 7474:7474 -p 7687:7687 `
  -e NEO4J_AUTH=neo4j/password123 `
  -d neo4j:latest
```

> Este comando descarga la imagen de Neo4j (solo la primera vez) y levanta el contenedor en segundo plano.

---

## 2. Verificar que arrancó correctamente

```powershell
docker ps
```

Debes ver algo así:

```
CONTAINER ID   IMAGE          STATUS         PORTS                              NAMES
40825186b5a9   neo4j:latest   Up N seconds   0.0.0.0:7474->7474, 7687->7687    neo4j-puzzle
```

Si el contenedor no aparece, revisa los logs:

```powershell
docker logs neo4j-puzzle
```

### Apagar y volver a encender el contenedor

```powershell
# Apagar
docker stop neo4j-puzzle

# Volver a encender (sin perder datos)
docker start neo4j-puzzle
```

> **Importante:** los datos persisten mientras no elimines el contenedor. Si haces `docker rm neo4j-puzzle` se pierden todos los nodos.

---

## 3. Crear el archivo `.env`

En la misma carpeta donde está `proyecto3.py`, crea un archivo llamado `.env` con este contenido:

```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=password123
```

> Si cambiaste la contraseña al correr el `docker run`, usa esa misma aquí.

### Instalar dependencias de Python

```powershell
pip install neo4j python-dotenv
```

### Correr el script

```powershell
python proyecto3.py
```

---

## 4. Acceder al browser de Neo4j (localhost)

Abre tu navegador y ve a:

```
http://localhost:7474
```

Ingresa con las credenciales:

- **Usuario:** `neo4j`
- **Contraseña:** `password123`

Una vez dentro, puedes ver todos los nodos y relaciones con:

```cypher
MATCH (n) RETURN n
```

O filtrar solo las piezas de un rompecabezas específico:

```cypher
MATCH (p:Piece {puzzle_id: 1})-[r]->(q:Piece)
RETURN p, r, q
```

---

## Resumen de puertos

| Puerto | Servicio |
|--------|----------|
| `7474` | Neo4j Browser (interfaz web) |
| `7687` | Bolt (conexión desde Python) |