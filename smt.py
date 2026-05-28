from dotenv import load_dotenv
from neo4j import GraphDatabase
import os

load_dotenv()

URI      = os.getenv("NEO4J_URI")
USER     = os.getenv("NEO4J_USERNAME")
PASSWORD = os.getenv("NEO4J_PASSWORD")

print(f"Conectando a {URI}...")

try:
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    driver.verify_connectivity()
    print("✓ Conexión exitosa")
    driver.close()
except Exception as e:
    print(f"✗ Error: {e}")