from book_rag import (
    COLLECTION_NAME,
    VECTOR_DB_PATH,
    chunk_pages,
    load_book_pages,
    local_embedding_function,
)
from dataset_store import persistent_vector_client


def build_offline_database() -> None:
    chunks = chunk_pages(load_book_pages())
    if not chunks:
        raise ValueError("The book contains no indexable text.")

    client = persistent_vector_client(VECTOR_DB_PATH)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=local_embedding_function(),
    )
    ids, documents, metadatas = zip(*chunks)
    print(f"Embedding {len(chunks)} page-aware book segments locally...")
    collection.upsert(
        ids=list(ids),
        documents=list(documents),
        metadatas=list(metadatas),
    )

    indexed_ids = set(ids)
    existing_ids = collection.get(include=[])["ids"]
    stale_ids = [item_id for item_id in existing_ids if item_id not in indexed_ids]
    if stale_ids:
        collection.delete(ids=stale_ids)
    print(f"Indexed {collection.count()} segments in {VECTOR_DB_PATH}")


if __name__ == "__main__":
    build_offline_database()
