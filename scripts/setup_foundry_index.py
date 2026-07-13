"""One-time setup script for Foundry IQ (RESEARCH.md §5 steps 4-6):

1. Create an Azure AI Search index (`AZURE_SEARCH_INDEX_NAME`) with a vector
   field (Azure OpenAI vectorizer) + semantic configuration, sized for the
   demo's "enterprise policy knowledge base" use case.
2. Upload the sample documents in `sample_data/policies.json`.
3. Wrap the index as a `SearchIndexKnowledgeSource` and create a
   `KnowledgeBase` that exposes an MCP endpoint.

Run once, after filling in .env:
    python scripts/setup_foundry_index.py

Note: registering the resulting MCP endpoint as a Foundry *project
connection* must still be done via the REST API or `azd ai connection
create` (RESEARCH.md's known Portal bug strips `?api-version` and causes
HTTP 406) — this script only prints the connection payload to run next.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import config

SAMPLE_DATA_PATH = os.path.join(os.path.dirname(__file__), "sample_data", "policies.json")


def _require(name: str, value: str):
    if not value:
        raise SystemExit(f"Missing required config: {name}. Set it in .env before running this script.")


def create_index_and_upload():
    from azure.core.credentials import AzureKeyCredential
    from azure.identity import DefaultAzureCredential
    from azure.search.documents import SearchClient
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        AzureOpenAIVectorizer,
        AzureOpenAIVectorizerParameters,
        HnswAlgorithmConfiguration,
        SearchField,
        SearchFieldDataType,
        SearchIndex,
        SemanticConfiguration,
        SemanticField,
        SemanticPrioritizedFields,
        SemanticSearch,
        SimpleField,
        VectorSearch,
        VectorSearchProfile,
    )

    _require("AZURE_SEARCH_ENDPOINT", config.AZURE_SEARCH_ENDPOINT)
    _require("AZURE_SEARCH_INDEX_NAME", config.AZURE_SEARCH_INDEX_NAME)
    _require("AZURE_OPENAI_ENDPOINT", config.AZURE_OPENAI_ENDPOINT)

    credential = (
        AzureKeyCredential(config.AZURE_SEARCH_ADMIN_KEY)
        if config.AZURE_SEARCH_ADMIN_KEY
        else DefaultAzureCredential()
    )
    index_client = SearchIndexClient(endpoint=config.AZURE_SEARCH_ENDPOINT, credential=credential)

    vectorizer_name = "policies-openai-vectorizer"
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SearchField(name="title", type=SearchFieldDataType.String, searchable=True, filterable=True),
        SearchField(name="category", type=SearchFieldDataType.String, searchable=True, filterable=True, facetable=True),
        SearchField(name="content", type=SearchFieldDataType.String, searchable=True),
        SearchField(
            name="contentVector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=3072,
            vector_search_profile_name="policies-vector-profile",
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="policies-hnsw")],
        profiles=[
            VectorSearchProfile(
                name="policies-vector-profile",
                algorithm_configuration_name="policies-hnsw",
                vectorizer_name=vectorizer_name,
            )
        ],
        vectorizers=[
            AzureOpenAIVectorizer(
                vectorizer_name=vectorizer_name,
                parameters=AzureOpenAIVectorizerParameters(
                    resource_url=config.AZURE_OPENAI_ENDPOINT,
                    deployment_name=config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
                    model_name=config.AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
                ),
            )
        ],
    )

    semantic_search = SemanticSearch(
        configurations=[
            SemanticConfiguration(
                name="policies-semantic-config",
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="title"),
                    content_fields=[SemanticField(field_name="content")],
                    keywords_fields=[SemanticField(field_name="category")],
                ),
            )
        ]
    )

    index = SearchIndex(
        name=config.AZURE_SEARCH_INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
    )
    index_client.create_or_update_index(index)
    print(f"Index '{config.AZURE_SEARCH_INDEX_NAME}' created/updated on {config.AZURE_SEARCH_ENDPOINT}.")

    with open(SAMPLE_DATA_PATH, encoding="utf-8") as f:
        docs = json.load(f)

    search_client = SearchClient(
        endpoint=config.AZURE_SEARCH_ENDPOINT,
        index_name=config.AZURE_SEARCH_INDEX_NAME,
        credential=credential,
    )
    # contentVector is populated automatically by the vectorizer on upload
    # when the field has no value and a vectorizer is configured; otherwise
    # compute embeddings client-side before calling upload_documents.
    result = search_client.upload_documents(documents=docs)
    failed = [r for r in result if not r.succeeded]
    print(f"Uploaded {len(docs) - len(failed)}/{len(docs)} sample policy documents.")
    if failed:
        print("Failures:", failed)


def create_knowledge_source_and_base():
    """Wraps the index as a SearchIndexKnowledgeSource and creates the
    KnowledgeBase that exposes the MCP endpoint the demo talks to."""
    from azure.core.credentials import AzureKeyCredential
    from azure.identity import DefaultAzureCredential
    from azure.search.documents.indexes import SearchIndexClient
    from azure.search.documents.indexes.models import (
        KnowledgeBase,
        KnowledgeBaseAzureOpenAIModel,
        KnowledgeSourceReference,
        SearchIndexKnowledgeSource,
        SearchIndexKnowledgeSourceParameters,
    )
    from azure.search.documents.indexes.models import AzureOpenAIVectorizerParameters

    _require("FOUNDRY_KNOWLEDGE_BASE_NAME", config.FOUNDRY_KNOWLEDGE_BASE_NAME)
    _require("AZURE_OPENAI_ENDPOINT", config.AZURE_OPENAI_ENDPOINT)

    credential = (
        AzureKeyCredential(config.AZURE_SEARCH_ADMIN_KEY)
        if config.AZURE_SEARCH_ADMIN_KEY
        else DefaultAzureCredential()
    )
    index_client = SearchIndexClient(endpoint=config.AZURE_SEARCH_ENDPOINT, credential=credential)

    ks_name = f"{config.AZURE_SEARCH_INDEX_NAME}-ks"
    knowledge_source = SearchIndexKnowledgeSource(
        name=ks_name,
        search_index_parameters=SearchIndexKnowledgeSourceParameters(
            search_index_name=config.AZURE_SEARCH_INDEX_NAME,
            semantic_configuration_name="policies-semantic-config",
        ),
    )
    index_client.create_or_update_knowledge_source(knowledge_source=knowledge_source)
    print(f"Knowledge source '{ks_name}' created/updated.")

    knowledge_base = KnowledgeBase(
        name=config.FOUNDRY_KNOWLEDGE_BASE_NAME,
        knowledge_sources=[KnowledgeSourceReference(name=ks_name)],
        models=[
            KnowledgeBaseAzureOpenAIModel(
                azure_open_ai_parameters=AzureOpenAIVectorizerParameters(
                    resource_url=config.AZURE_OPENAI_ENDPOINT,
                    deployment_name=config.AGENT_MODEL,
                    model_name=config.AGENT_MODEL,
                ),
            )
        ],
    )
    index_client.create_or_update_knowledge_base(knowledge_base=knowledge_base)
    print(f"Knowledge base '{config.FOUNDRY_KNOWLEDGE_BASE_NAME}' created/updated.")


def print_knowledge_base_next_steps():
    kb_name = config.FOUNDRY_KNOWLEDGE_BASE_NAME or "<choose-a-knowledge-base-name>"
    mcp_url = (
        f"{config.AZURE_SEARCH_ENDPOINT}/knowledgebases/{kb_name}/mcp"
        f"?api-version=2026-05-01-preview"
    )
    print(
        "\nThe orchestrator talks to Azure AI Search's MCP endpoint directly with\n"
        "DefaultAzureCredential (search.azure.com scope) — no separate Foundry project\n"
        "connection is required for this demo's architecture, so the steps below are\n"
        "only needed if you also want this Knowledge Base callable as a Foundry agent tool:\n"
        f"  MCP endpoint (already live): {mcp_url}\n"
        "  To register it as a Foundry project connection (optional, Portal has a known\n"
        "  '?api-version'-stripping bug — use REST API or CLI instead):\n"
        "       azd ai connection create --project-endpoint "
        f"{config.PROJECT_ENDPOINT} --url \"{mcp_url}\" --audience https://search.azure.com/\n"
    )


if __name__ == "__main__":
    create_index_and_upload()
    create_knowledge_source_and_base()
    print_knowledge_base_next_steps()
