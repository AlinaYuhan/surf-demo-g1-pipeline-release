# Optional XJTLU RAG / 可选 XJTLU RAG

> 中文摘要：`xjtlu-rag-system/` 保留了学校知识检索源码，
> `xjtlu_knowledge.db` 和 `rag_index.db` 已确认允许公开。该后端默认不启用，
> 因为在目标交互中带来较大延迟，且效果收益有限。

## Status

The production/default reply backend is direct DeepSeek:

```text
LLM_REPLY_BACKEND=deepseek
```

The optional RAG path is retained for research and future iteration. It is not
started, checked, or required unless explicitly selected.

## Included optional files

```text
xjtlu-rag-system/app.py               FastAPI service
xjtlu-rag-system/chat_engine.py       Retrieval and generation orchestration
xjtlu-rag-system/rag_config.py        RAG-specific settings
xjtlu-rag-system/vector_store.py      Vector lookup
xjtlu-rag-system/memory_store.py      Optional runtime conversation memory
xjtlu-rag-system/xjtlu_knowledge.db   Approved small knowledge database
xjtlu-rag-system/rag_index.db         Approved small vector index database
```

Runtime memory is written beneath `runtime/` and is not part of the public
source or release artifact.

## Enable for an experiment

Install Ollama separately and pull the configured embedding model:

```bash
ollama pull nomic-embed-text
ollama list
./scripts/env_set.sh LLM_REPLY_BACKEND rag
./scripts/check_pipeline.sh
./scripts/run_pipeline.sh --mode wake
```

The defaults use:

```text
EMBED_PROVIDER=ollama
EMBED_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://127.0.0.1:11434
RAG_SERVER_PORT=8010
```

The RAG service still uses the configured DeepSeek/OpenAI-compatible chat
provider for generation. Ollama supplies embeddings by default; it is not the
default chat model.

## Return to the supported default

```bash
./scripts/stop_pipeline.sh
./scripts/env_set.sh LLM_REPLY_BACKEND deepseek
./scripts/check_pipeline.sh
```

Direct DeepSeek does not require the RAG databases, Ollama binary/cache, or
`nomic-embed-text`. Keep performance comparisons explicit about which backend
was enabled.
