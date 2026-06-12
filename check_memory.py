from qdrant_client import QdrantClient

client = QdrantClient(host="localhost", port=6333)

print("Collections:", [c.name for c in client.get_collections().collections])

points = client.scroll(collection_name="campo_memories", limit=10)
for point in points[0]:
    print(point.payload)