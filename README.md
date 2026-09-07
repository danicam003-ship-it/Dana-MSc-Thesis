# RAG Experiment Pipeline

This repository contains the data preparation pipeline and the four RAG
architectures compared in the thesis, plus an interactive testing script.

## Contents

1. [Corpus Preparation and Graph Construction](#corpus-preparation-and-graph-construction) — `prepare_experiment_data.py`
2. [Shared Pipeline and Baseline Model (Model 1)](#shared-pipeline-and-baseline-model-model-1) — `single_agent_rag_baseline.py`
3. [Domain-Routed Multi-Agent Passage Retrieval (Model 2)](#domain-routed-multi-agent-passage-retrieval-model-2) — `multi_agent_passage_rag.py`
4. [Multi-Agent Question-to-Question Retrieval (Model 3)](#multi-agent-question-to-question-retrieval-model-3) — `multi_agent_question_to_question_rag.py`
5. [Graph-Supported Query Expansion (Model 4)](#graph-supported-query-expansion-model-4) — `graph_supported_rag.py`
6. [Asking Questions to the Model](#asking-questions-to-the-model) — `ask_rag_model.py`

---

## Corpus Preparation and Graph Construction

`prepare_experiment_data.py` prepares the raw thesis corpus for all downstream RAG
experiments. It reads source files from a raw data directory and produces the
standard JSONL and CSV files used by the RAG models.

## Supported source formats

| Format | Extension(s) | Extraction method |
|---|---|---|
| PDF | `.pdf` | `pypdf` |
| HTML | `.html`, `.htm` | A simple HTML parser that strips `<script>` and `<style>` content |
| XML | `.xml` | `xml.etree.ElementTree` |

Extracted text is normalised by removing non-breaking spaces, repairing
hyphenated line breaks, and collapsing repeated whitespace.

## Pipeline

### 1. Passage extraction and chunking

Each source document is divided into overlapping, word-based chunks.

- Default chunk size: **220 words**
- Default overlap: **40 words**

Each chunk is written as one JSONL record in `passages.jsonl`, with fields:

`chunk_id`, `record_id`, `text`, `retrieval_text`, `source_id`, `source_title`,
`source_type`, `source_file`, `doi`, `section`, `agent_domain`, `symptom_tags`,
`concept_tags`, `life_stage_tags`, `license_metadata`

These fields provide the metadata needed for filtering, provenance, domain
routing, and later evaluation.

### 2. Q&A pair preparation

The script also reads the human-reviewed Q&A workbook. Each accepted Q&A row
is normalised into a standard record containing:

- question
- transcript-derived answer
- source title
- interviewer metadata (where available)
- agent domain
- concept tags, symptom tags, life-stage tags
- license metadata

The full Q&A set is split into training and testing portions using a
**stratified split by agent domain** (default test ratio: **20%**). Held-out
test questions are excluded from both the question-to-question retrieval
index and the knowledge-graph construction, to reduce evaluation leakage.

### 3. Concept tagging

Concept tagging draws on two sources:

1. **Default vocabulary** — a built-in set of expert-defined concepts for the
   six content domains: `mental_health`, `sleep`, `hormonal_health`,
   `lifestyle`, `nutrition_body`, `intervention`.
2. **Highlighted concept metadata matrix** — additional concept labels,
   synonyms, suggested domains, and graph node types read from the
   `Concept_Matrix` and `Highlighted_Phrases` sheets.

Key functions:

- `matrix_domain` — normalises spreadsheet domain labels into the six
  internal content domains.
- `matrix_concept_type` — maps graph labels into node types: `concept`,
  `symptom`, `condition`, `intervention`, `context`, `life_stage`, `safety`,
  `nutrient`.
- `match_concepts`, `choose_domain`, `tags_from_text` — use the combined
  vocabulary to assign tags and an agent domain to each chunk or Q&A record.

### 4. Knowledge graph construction

The knowledge graph is built in the same script.

- **Nodes** are created for concepts that appear in the prepared evidence.
- **Candidate edges** are created when two concepts co-occur in the same
  passage chunk or training Q&A record.

Relation labels are assigned by rule:

| Condition | Relation label |
|---|---|
| Same-domain pair | `co_occurs_with` |
| Cross-domain pair | `associated_with` |
| Pair involves the intervention domain | `may_be_supported_by` |
| Pair involves a safety concept | `has_red_flag` |

Each edge stores its supporting evidence identifiers, source count,
corroboration count, extraction method, source quality, extraction
confidence, and extraction type.

> **Note:** These edges are automatically extracted co-occurrence
> candidates, not clinically validated causal claims.

## Usage

```bash
python prepare_experiment_data.py \
  --data-dir data/raw \
  --qna-workbook data/raw/huberman_qna_humanreviewed.xlsx \
  --qna-sheet Cleaned_QA_Pairs \
  --concept-matrix data/raw/highlight_concept_metadata_matrix.xlsx \
  --output-dir data/prepared \
  --chunk-words 220 \
  --overlap-words 40 \
  --test-ratio 0.20 \
  --seed 20260719 \
  --graph-min-confidence 0.91
```

All arguments are optional; the defaults above are the ones used in the
thesis experiments.

## Outputs

Written to `--output-dir` (default: `data/prepared/`):

- `passages.jsonl` — chunked passage records
- `qna_pairs.jsonl` / `qna_pairs_train.jsonl` — training Q&A pairs
- `qna_pairs_test.jsonl` — held-out test Q&A pairs
- `qna_pairs_all.jsonl` — full Q&A set (train + test)
- `training_questions.jsonl` — training pairs reshaped for evaluation-style use
- `evaluation_questions.jsonl` — held-out test pairs reshaped for evaluation
- `knowledge_graph.json` — concept graph (nodes and candidate edges)
- `source_manifest.csv` — one row per source file (type, DOI, word/chunk counts, extraction errors, etc.)
- `concept_inventory.csv` — one row per graph concept node
- `agent_concepts.json` — the active concept vocabulary
- `preparation_report.md` — a run summary (domain distribution, leakage notes, counts)

## Leakage control

Held-out Q&A rows are **not** written to `qna_pairs.jsonl` and are **not**
used when constructing graph edges. They are written only to
`qna_pairs_test.jsonl` and `evaluation_questions.jsonl`, keeping the
evaluation set fully separate from both the retrieval index and the graph.

---

## Shared Pipeline and Baseline Model (Model 1)

`single_agent_rag_baseline.py` implements **Model 1**, the single-agent
passage RAG baseline, and defines the shared components imported by the
other model scripts.

### Settings

`FixedRAGSettings` (a dataclass) stores the generator model, embedding model,
reranker model, Qdrant path, collection names, retrieval depth, final
evidence size, maximum generation length, and synthesis evidence budget.

| Setting | Default |
|---|---|
| Retrieval depth (`retrieve_k`) | 40 |
| Final evidence size (`final_k`) | 5 |
| Synthesis budget (`SYNTHESIS_K`) | same as `final_k` |

The synthesis budget defaults to `final_k` specifically so that multi-agent
models don't receive a larger evidence context than the single-agent
baseline, unless a separate ablation explicitly changes `SYNTHESIS_K`.

`settings_with_overrides` allows the embedding model, generator model,
reranker model, Qdrant path, and collection suffix to be changed from the
command line without editing the code. If a different embedding model is
used (e.g. `microsoft/deberta-v3-base`), the script automatically creates a
separate Qdrant collection name, so vectors from ClinicalBERT and DeBERTa are
never mixed in the same index.

### Input standardisation

- `load_jsonl` — reads one JSON record per line, reporting the line number if malformed JSON is found.
- `first_present` — retrieves the first non-empty value from a list of possible field names.
- `standardise_passage_record` — maps passage records into a stable internal format.
- `standardise_qa_record` — same, for Q&A records. Here, `retrieval_text` is set to the stored **question** rather than the answer — this is what enables question-to-question retrieval in Model 3.

### Embedding

`TransformerMeanPoolEmbedder` implements the embedding component. The default
model is ClinicalBERT, but the class is intentionally generic and can also
load compatible encoder models such as DeBERTa. It produces token-level
hidden states and converts them into one vector per text using
attention-mask-aware mean pooling (padding tokens excluded from the average),
then L2-normalises the result before it's stored or searched in Qdrant.

### Vector store

`QdrantVectorStore` creates or reuses a local embedded Qdrant collection by
default, though a remote Qdrant server can be used through environment
variables. Records are embedded and inserted with **deterministic UUID5
point identifiers** generated from their stable record IDs, which makes
re-indexing idempotent.

`search` embeds the user query, retrieves nearest neighbours from Qdrant, and
optionally applies an `agent_domain` metadata filter. The single-agent
baseline searches without this filter; the multi-agent models use it to
restrict retrieval to a selected domain.

### Reranking

`MiniLMCrossEncoderReranker` receives the user query and the candidates
returned by Qdrant, scores each query-candidate pair jointly, and returns the
top `final_k` candidates. This step matters because dense vector search
finds semantically plausible candidates quickly, while the cross-encoder
gives a more precise relevance score by reading the query and candidate
together.

### Generation

`QwenGenerator` uses a Hugging Face pipeline with greedy decoding
(`do_sample=False`). It also counts LLM calls, prompt tokens, and completion
tokens per question, so computational cost can be reported alongside
retrieval quality.

Citation grounding is supported by `format_passage_evidence`,
`evidence_ids`, `extract_citations`, `citation_report`, and
`ensure_citations`. Notably, `citation_report` checks whether the generated
bracketed citations correspond to evidence IDs that were **actually supplied**
to the generator, rather than just counting square brackets.

### The baseline model

`SingleAgentRAGBaseline` combines these components. Its `answer` method
performs one unfiltered dense search over all passage chunks, reranks the
candidates, and sends the top evidence items to the generator. There is no
router, no agent-specific metadata filter, no question-to-question
retrieval, and no graph expansion — this is the controlled baseline against
which the other three architectures are compared.

---

## Domain-Routed Multi-Agent Passage Retrieval (Model 2)

`multi_agent_passage_rag.py` implements **Model 2**. It reuses the same
embedder, Qdrant vector store, MiniLM reranker, and Qwen generator as the
baseline, but changes the orchestration: instead of searching the whole
passage corpus once, the system first routes the query to one or more
domain agents, each of which performs its own domain-filtered retrieval and
produces a short domain finding. A synthesizer then combines the domain
findings into a final answer.

### Agents

Domain agents are defined through `AGENT_PROMPTS`: Psychological Symptoms
(Mental Health), Sleep, Hormonal Health, Lifestyle, Nutrition and Body, and
Intervention. The router and synthesizer are orchestration roles, not
document domains. A safety pre-check is also implemented via regular
expressions for urgent safety language (suicidal ideation, self-harm,
overdose, immediate danger).

### Routing

`route_agents` performs the routing. The router uses `keyword_hits`, which
counts **whole-word or whole-phrase** keyword matches rather than substring
matches — this prevents accidental routing errors such as matching `iron`
inside `environment` or `tired` inside `retired`.

If no domain keyword matches, the router returns an empty list, the model
activates an `unrouted` fallback search, and `router_miss=True` is recorded —
making routing failure visible in the results.

### Orchestration

`AgentFinding` (a dataclass) stores the agent domain, generated answer,
retrieved evidence, number of candidates retrieved before reranking, and
number of candidates remaining after reranking. These counts make it
possible to identify **starved agents** — agents selected by the router that
retrieved no usable evidence after filtering and reranking.

`MultiAgentPassageRAG` performs the full orchestration:
- `retrieve_for_agent` applies the `agent_domain` metadata filter, unless the active agent is `unrouted`.
- `answer` routes the query, runs each active agent sequentially, deduplicates evidence by record ID, sorts evidence by rerank and vector score, applies the synthesis budget, and generates the final answer.

This architecture increases the number of LLM calls compared to the
baseline: one generation call per active domain agent, plus one additional
call for the synthesizer. `llm_calls`, prompt token counts, completion token
counts, and latency are all recorded.

---

## Multi-Agent Question-to-Question Retrieval (Model 3)

`multi_agent_question_to_question_rag.py` implements **Model 3**. It keeps
the same router, safety pre-check, domain prompts, embedder, vector
database, reranker, and generator as Model 2, but changes the **retrieval
unit**: instead of embedding and retrieving passage chunks, it embeds and
retrieves the stored **questions** from the cleaned Q&A corpus. The answer
linked to each retrieved question is then used as evidence for generation.

`format_qna_evidence` formats each retrieved Q&A pair, showing the evidence
ID, source title, stored question, transcript-derived answer, vector score,
and rerank score. The prompt builders `build_qa_agent_prompt` and
`build_qa_synthesis_prompt` explicitly tell the generator that the evidence
consists of *retrieved similar questions and transcript-derived answers*,
not direct clinical diagnoses — because question-to-question retrieval
finds semantic similarity between the user's query and an existing
question; it does not prove the linked answer fully resolves the user's
situation.

`MultiAgentQuestionToQuestionRAG` mirrors the Model 2 architecture: it
routes the query, retrieves similar stored questions for each active agent,
reranks them with the MiniLM cross-encoder, generates domain findings,
merges and deduplicates evidence, applies the same synthesis budget, and
generates the final answer.

**Main methodological difference from Model 2:** Model 2 retrieves evidence
passages; Model 3 retrieves semantically similar questions and uses their
linked answers as evidence.

---

## Graph-Supported Query Expansion (Model 4)

`graph_supported_rag.py` implements **Model 4**. The knowledge graph does
**not** replace Qdrant and is not searched as the main retrieval engine —
it's used as a deterministic query-expansion mechanism *before* dense vector
retrieval. The embedding model, Qdrant vector database, MiniLM reranker, and
Qwen generator all remain unchanged from Models 1–2.

### Graph representation

- `GraphNode` — concept identifier, canonical label, synonyms.
- `GraphEdge` — source concept, target concept, relation type, confidence score, supporting evidence identifiers.

`KnowledgeGraphExpander` loads the graph from `knowledge_graph.json`, keeps
only edges above the configured confidence threshold, and records graph
statistics (nodes in file, edges in file, edges dropped below threshold,
active edges). If no usable edges are loaded, the script raises an error
unless `--allow-empty-graph` is explicitly supplied — preventing the
graph-supported experiment from silently becoming identical to ordinary
multi-agent passage RAG.

### Matching and traversal

- Query-node matching uses word-boundary regular expressions, so short terms don't accidentally match inside unrelated words.
- Edge traversal respects direction: only symmetric relations (`associated_with`, `co_occurs_with`, `related_to`) are traversed in both directions. Directed relations (e.g. intervention-support edges) are **not** automatically reversed.
- `expand_query` adds a bounded number of related concept labels to the retrieval query and records an audit trail showing which graph edges contributed to the expansion.

### Routing mode

`GraphSupportedMultiAgentRAG` uses the **expanded** query for first-stage
vector search, but the **original** user query for MiniLM reranking and
answer generation — making the graph a candidate-expansion mechanism rather
than a replacement reasoning engine.

| `--route-on` | Router sees | Notes |
|---|---|---|
| `original` (default) | Original user query | Cleaner ablation: the graph changes retrieval candidates without also changing which agents are selected. |
| `expanded` | Graph-expanded query | Changes two things at once (retrieval wording and agent selection) — report as a separate ablation. |

---

## Asking Questions to the Model

`ask_rag_model.py` is an interactive testing script for asking the
implemented RAG models custom questions **outside** the formal evaluation
loop. Unlike `run_experiment_batch.py` (which processes a fixed evaluation
set and writes structured outputs for metric calculation), this script is
designed for manual inspection of chatbot behaviour.

The user selects one of the implemented architectures; the script then
loads the same prepared JSONL data files, model settings, Qdrant vector
collections, embedding model, reranker, graph file, and generation settings
used in the experiments. It checks that the relevant vector index exists and
contains the expected number of records, rebuilding it first if needed.

Questions can be supplied:
- as a single question via the command line,
- from a file containing multiple questions, or
- interactively.

In interactive mode, the script repeatedly waits for a question, sends it to
the selected model's `answer()` method, and prints the generated answer in a
readable format, including: the original query, routed agents (where
relevant), graph-added terms (for the graph-supported model), the final
answer, the evidence items used, reranking scores, and citation validity
information. The goal isn't just to show the chatbot's answer — it's to
make the retrieval and grounding behaviour visible during manual testing.

> **No conversational memory.** Each question is processed independently,
> even across multiple questions in the same session. Previous questions
> and answers are not stored, summarised, or inserted into the next prompt —
> keeping manual testing consistent with the formal evaluation setting,
> where each evaluation question is treated as a standalone input.
