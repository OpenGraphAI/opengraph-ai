#!/usr/bin/env python3
"""
Direct Neo4j query runner for MCP server.
Usage: python neo4j_query.py "<cypher query>"
"""
import sys
import json
import os

def run_query(cypher: str):
    try:
        from neo4j import GraphDatabase
        # Load env manually from project root .env.local
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_file = os.path.join(project_root, '.env.local')
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('export '):
                        line = line[7:]
                    if '=' in line and not line.startswith('#'):
                        key, _, val = line.partition('=')
                        os.environ.setdefault(key.strip(), val.strip())

        uri = os.environ.get('NEO4J_URI') or os.environ.get('NEO4J_URI')
        username = os.environ.get('NEO4J_USERNAME')
        password = os.environ.get('NEO4J_PASSWORD')

        driver = GraphDatabase.driver(uri, auth=(username, password))

        with driver.session() as session:
            result = session.run(cypher)
            records = [dict(record) for record in result]

        driver.close()
        print(json.dumps({"success": True, "data": records}))

    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "No query provided"}))
        sys.exit(1)
    run_query(sys.argv[1])
