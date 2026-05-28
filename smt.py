from dotenv import load_dotenv
import os
from neo4j import GraphDatabase

load_dotenv()

URI      = os.getenv("NEO4J_URI")
USER     = os.getenv("NEO4J_USER", os.getenv("NEO4J_USERNAME", "neo4j"))
PASSWORD = os.getenv("NEO4J_PASSWORD")

print(f"URI:  {URI}")
print(f"USER: {USER}")
print(f"PASS: {'*' * len(PASSWORD) if PASSWORD else 'None'}")
print()

try:
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    driver.verify_connectivity()
    print("✅ Conexión exitosa a Neo4j!")
    driver.close()
except Exception as e:
    print(f"❌ Error: {e}")