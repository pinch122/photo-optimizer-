import uuid
from typing import List, Dict, Any, Optional
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from app.qdrant_client_helper import get_qdrant_client
from app.logging_config import logger

class QdrantService:
    @classmethod
    def get_collection_name(cls, model_name: str) -> str:
        """
        Generates a standardized collection name from the model identifier.
        e.g., 'clip-ViT-B-32' -> 'media_embeddings_clip_vit_b_32'
        """
        clean_name = model_name.lower().replace("-", "_").replace(".", "_")
        return f"media_embeddings_{clean_name}"

    @classmethod
    def ensure_collection(cls, model_name: str, dimension: int) -> str:
        """
        Verifies that a versioned Qdrant collection exists for the model.
        Creates it automatically with Cosine index checks if missing.
        """
        collection_name = cls.get_collection_name(model_name)
        client = get_qdrant_client()
        
        try:
            # Check existence of target collection index
            if not client.collection_exists(collection_name):
                logger.info(f"Qdrant Service: Collection '{collection_name}' not found. Initializing with dimension={dimension}.")
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=dimension,
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"Qdrant Service: Collection '{collection_name}' created successfully.")
            return collection_name
        except Exception as e:
            logger.error(f"Qdrant Service: Failed verifying collection status for '{collection_name}': {e}")
            raise

    @classmethod
    def upsert_vector(
        cls,
        asset_id: uuid.UUID,
        vector: List[float],
        model_name: str,
        payload: Dict[str, Any]
    ) -> None:
        """
        Inserts or overwrites (idempotent) a vector into the collection.
        Resolves collection mappings dynamically based on vector shape.
        """
        dimension = len(vector)
        collection_name = cls.ensure_collection(model_name, dimension)
        client = get_qdrant_client()
        
        try:
            # Initialize Qdrant point structural format
            point = PointStruct(
                id=str(asset_id),
                vector=vector,
                payload=payload
            )
            
            client.upsert(
                collection_name=collection_name,
                points=[point]
            )
            logger.info(f"Qdrant Service: Upserted vector point for asset [{asset_id}] in collection '{collection_name}'")
        except Exception as e:
            logger.error(f"Qdrant Service: Failed upserting vector point for [{asset_id}] in '{collection_name}': {e}")
            raise

    @classmethod
    def delete_vector(cls, asset_id: uuid.UUID, model_name: str) -> None:
        """
        Removes the vector matching the asset UUID from the collection.
        """
        collection_name = cls.get_collection_name(model_name)
        client = get_qdrant_client()
        
        try:
            if client.collection_exists(collection_name):
                client.delete(
                    collection_name=collection_name,
                    points_selector=[str(asset_id)]
                )
                logger.info(f"Qdrant Service: Deleted vector point for [{asset_id}] from collection '{collection_name}'")
        except Exception as e:
            logger.error(f"Qdrant Service: Error deleting vector point for [{asset_id}] from '{collection_name}': {e}")
            # Raise no exception to avoid interrupting clean-up chains

    @classmethod
    def search_vectors(
        cls,
        vector: List[float],
        model_name: str,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Queries Qdrant for Top-K closest matching vectors using cosine distance similarity.
        Returns a list of dictionaries with point IDs (uuids) and similarity scores.
        """
        collection_name = cls.get_collection_name(model_name)
        client = get_qdrant_client()
        
        try:
            if not client.collection_exists(collection_name):
                logger.warning(f"Qdrant Service: Collection '{collection_name}' does not exist during search query.")
                return []
                
            response = client.query_points(
                collection_name=collection_name,
                query=vector,
                limit=limit,
                offset=offset,
                with_payload=True
            )
            
            output = []
            for hit in response.points:
                output.append({
                    "id": uuid.UUID(hit.id),
                    "score": float(hit.score),
                    "payload": hit.payload
                })
            return output
        except Exception as e:
            logger.error(f"Qdrant Service: Search query failed on collection '{collection_name}': {e}")
            raise
