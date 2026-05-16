"""Graph traversal algorithms for multi-hop reasoning."""

from __future__ import annotations

from typing import Any

from evograph.graph.neo4j_client import neo4j_client
from evograph.models.domain import GraphEntity, GraphRelation, EntityType


async def get_entity_by_id(entity_id: str) -> dict[str, Any] | None:
    results = await neo4j_client.execute_query(
        "MATCH (e:Entity {id: $id}) RETURN e",
        {"id": entity_id},
    )
    return results[0]["e"] if results else None


async def get_entity_by_name(name: str) -> list[dict[str, Any]]:
    return await neo4j_client.execute_query(
        """
        MATCH (e:Entity)
        WHERE toLower(e.name) CONTAINS toLower($name)
           OR any(alias IN e.aliases WHERE toLower(alias) CONTAINS toLower($name))
        RETURN e
        LIMIT 10
        """,
        {"name": name},
    )


async def get_neighborhood(
    entity_id: str,
    hops: int = 2,
    relation_types: list[str] | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    rel_filter = ""
    if relation_types:
        types_str = "|".join(relation_types)
        rel_filter = f":{types_str}"

    query = f"""
    MATCH path = (start:Entity {{id: $entity_id}})-[r{rel_filter}*1..{hops}]-(neighbor:Entity)
    WHERE all(rel IN relationships(path) WHERE rel.is_active = true)
    WITH DISTINCT neighbor, relationships(path) AS rels
    LIMIT $limit
    RETURN neighbor, rels
    """
    results = await neo4j_client.execute_query(
        query, {"entity_id": entity_id, "limit": limit}
    )

    entities = []
    relations = []
    seen_entities: set[str] = set()
    seen_relations: set[str] = set()

    for record in results:
        node = record["neighbor"]
        if node["id"] not in seen_entities:
            entities.append(node)
            seen_entities.add(node["id"])
        for rel in record["rels"]:
            rel_id = rel.get("id", "")
            if rel_id and rel_id not in seen_relations:
                relations.append(rel)
                seen_relations.add(rel_id)

    return {"entities": entities, "relations": relations}


async def find_path(
    source_id: str, target_id: str, max_hops: int = 5
) -> list[dict[str, Any]]:
    results = await neo4j_client.execute_query(
        f"""
        MATCH path = shortestPath(
            (a:Entity {{id: $source_id}})-[*..{max_hops}]-(b:Entity {{id: $target_id}})
        )
        WHERE all(r IN relationships(path) WHERE r.is_active = true)
        RETURN nodes(path) AS nodes, relationships(path) AS rels
        """,
        {"source_id": source_id, "target_id": target_id},
    )
    return results


async def get_temporal_relations(
    entity_id: str, timestamp: str | None = None
) -> list[dict[str, Any]]:
    if timestamp:
        query = """
        MATCH (e:Entity {id: $entity_id})-[r]->(target:Entity)
        WHERE r.is_active = true
          AND (r.valid_from IS NULL OR r.valid_from <= datetime($ts))
          AND (r.valid_to IS NULL OR r.valid_to >= datetime($ts))
        RETURN r, target
        ORDER BY r.valid_from DESC
        """
        return await neo4j_client.execute_query(
            query, {"entity_id": entity_id, "ts": timestamp}
        )
    else:
        query = """
        MATCH (e:Entity {id: $entity_id})-[r]->(target:Entity)
        WHERE r.is_active = true
        RETURN r, target
        ORDER BY r.valid_from DESC
        """
        return await neo4j_client.execute_query(query, {"entity_id": entity_id})


async def get_causal_chain(event_id: str, depth: int = 3) -> list[dict[str, Any]]:
    return await neo4j_client.execute_query(
        f"""
        MATCH path = (start:Event {{id: $event_id}})-[:CAUSED_BY|RESULTED_IN*1..{depth}]-(related)
        RETURN nodes(path) AS nodes, relationships(path) AS rels
        """,
        {"event_id": event_id},
    )


async def get_graph_stats() -> dict[str, Any]:
    stats = await neo4j_client.execute_query("""
        MATCH (e:Entity)
        WITH count(e) AS entity_count, collect(e.type) AS types
        MATCH ()-[r]->()
        WITH entity_count, types, count(r) AS relation_count
        MATCH (d:Document)
        WITH entity_count, types, relation_count, count(d) AS doc_count
        MATCH (c:Conflict {status: 'open'})
        RETURN entity_count, relation_count, doc_count, count(c) AS conflict_count
    """)
    return stats[0] if stats else {}
