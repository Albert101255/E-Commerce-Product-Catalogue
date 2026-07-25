from typing import Any, cast

from elasticsearch import Elasticsearch

from app.core.config import settings

# Initialize ES client if URL is provided
es_client: Elasticsearch | None = None
if settings.ELASTICSEARCH_URL:
    es_client = Elasticsearch(settings.ELASTICSEARCH_URL)

# In-Memory storage for Mock Elasticsearch
_mock_index: dict[int, dict[str, Any]] = {}


class ElasticsearchService:
    @staticmethod
    def index_product(
        product_id: int,
        name: str,
        description: str | None,
        sku: str,
        category_name: str | None,
        brand_name: str | None,
        price: float,
        rating: float,
    ) -> None:
        doc = {
            "id": product_id,
            "name": name,
            "description": description or "",
            "sku": sku,
            "category_name": category_name or "",
            "brand_name": brand_name or "",
            "price": price,
            "rating": rating,
        }

        if es_client:
            es_client.index(index="products", id=str(product_id), document=doc)
        else:
            _mock_index[product_id] = doc

    @staticmethod
    def delete_product(product_id: int) -> None:
        if es_client:
            try:
                es_client.delete(index="products", id=str(product_id))
            except Exception:
                pass
        else:
            _mock_index.pop(product_id, None)

    @staticmethod
    def search_products(
        query: str,
        category: str | None = None,
        brand: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        sort_by: str | None = None,
        skip: int = 0,
        limit: int = 10,
    ) -> dict[str, Any]:
        if es_client:
            # Construct Elasticsearch query
            must_queries: list[dict[str, Any]] = []
            filter_queries: list[dict[str, Any]] = []

            if query:
                must_queries.append(
                    {
                        "multi_match": {
                            "query": query,
                            "fields": ["name^3", "description", "sku^2"],
                            "fuzziness": "AUTO",
                        }
                    }
                )
            else:
                must_queries.append({"match_all": {}})

            if category:
                filter_queries.append({"term": {"category_name.keyword": category}})
            if brand:
                filter_queries.append({"term": {"brand_name.keyword": brand}})
            if min_price is not None or max_price is not None:
                price_range: dict[str, Any] = {}
                if min_price is not None:
                    price_range["gte"] = min_price
                if max_price is not None:
                    price_range["lte"] = max_price
                filter_queries.append({"range": {"price": price_range}})

            es_query = {
                "bool": {
                    "must": must_queries,
                    "filter": filter_queries,
                }
            }

            # Sort configurations
            es_sort: list[Any] = []
            if sort_by == "price_asc":
                es_sort.append({"price": {"order": "asc"}})
            elif sort_by == "price_desc":
                es_sort.append({"price": {"order": "desc"}})
            elif sort_by == "rating":
                es_sort.append({"rating": {"order": "desc"}})

            response = es_client.search(
                index="products",
                query=es_query,
                sort=es_sort,
                from_=skip,
                size=limit,
                aggs={
                    "categories": {"terms": {"field": "category_name.keyword"}},
                    "brands": {"terms": {"field": "brand_name.keyword"}},
                },
            )

            hits = response["hits"]["hits"]
            total = (
                response["hits"]["total"]["value"]
                if isinstance(response["hits"]["total"], dict)
                else response["hits"]["total"]
            )
            results = [hit["_source"] for hit in hits]

            # Aggregations extraction
            categories_agg = {
                bucket["key"]: bucket["doc_count"]
                for bucket in response.get("aggregations", {})
                .get("categories", {})
                .get("buckets", [])
            }
            brands_agg = {
                bucket["key"]: bucket["doc_count"]
                for bucket in response.get("aggregations", {})
                .get("brands", {})
                .get("buckets", [])
            }

            return {
                "total": total,
                "results": results,
                "facets": {
                    "categories": categories_agg,
                    "brands": brands_agg,
                },
            }

        else:
            # Perform search on Mock Index
            results = list(_mock_index.values())

            # Apply query filtering (fuzzy/substring)
            if query:
                q = query.lower()
                results = [
                    doc
                    for doc in results
                    if q in doc["name"].lower()
                    or q in doc["description"].lower()
                    or q in doc["sku"].lower()
                ]

            # Apply term filtering
            if category:
                results = [
                    doc
                    for doc in results
                    if doc["category_name"].lower() == category.lower()
                ]
            if brand:
                results = [
                    doc for doc in results if doc["brand_name"].lower() == brand.lower()
                ]
            if min_price is not None:
                results = [doc for doc in results if doc["price"] >= min_price]
            if max_price is not None:
                results = [doc for doc in results if doc["price"] <= max_price]

            # Sort
            if sort_by == "price_asc":
                results.sort(key=lambda x: x["price"])
            elif sort_by == "price_desc":
                results.sort(key=lambda x: x["price"], reverse=True)
            elif sort_by == "rating":
                results.sort(key=lambda x: x["rating"], reverse=True)

            total = len(results)
            paginated_results = results[skip : skip + limit]

            # Build aggregations
            categories_agg = {}
            brands_agg = {}
            for doc in results:
                c = doc["category_name"]
                b = doc["brand_name"]
                if c:
                    categories_agg[c] = categories_agg.get(c, 0) + 1
                if b:
                    brands_agg[b] = brands_agg.get(b, 0) + 1

            return {
                "total": total,
                "results": paginated_results,
                "facets": {
                    "categories": categories_agg,
                    "brands": brands_agg,
                },
            }

    @staticmethod
    def autocomplete(query: str) -> list[str]:
        if not query:
            return []

        if es_client:
            response = es_client.search(
                index="products",
                query={"match_phrase_prefix": {"name": query}},
                size=5,
            )
            hits = response["hits"]["hits"]
            return [cast(str, hit["_source"]["name"]) for hit in hits]
        else:
            q = query.lower()
            matches = [
                doc["name"]
                for doc in _mock_index.values()
                if doc["name"].lower().startswith(q)
            ]
            return matches[:5]
