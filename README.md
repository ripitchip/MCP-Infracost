# MCP-Infracost

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server built on top of FastAPI that exposes cloud infrastructure pricing data from the [Infracost GraphQL API](https://www.infracost.io/docs/supported_resources/). It allows AI assistants and MCP-compatible clients to query on-demand compute prices across AWS, GCP, and Azure directly from a conversation.

The repository also ships a companion CLI script for bulk-downloading and cleaning Terraform module READMEs from any GitHub organisation, which can be used to enrich an LLM's context with real-world IaC examples.

---

## Motivation

This project was designed around two concrete objectives:

**1. Maximise the ratio of useful LLM requests.**
Without structured tooling, LLM interactions with infrastructure APIs tend to produce a high proportion of malformed or redundant requests — calls that fail, return empty results, or consume API quota without delivering value. By exposing well-typed, purpose-built MCP tools instead of letting the model call APIs freeform, the server enforces correct parameters upfront and returns only actionable data. The goal is to drive error requests as close to zero as possible, reducing both wasted cost and noise in the model's reasoning chain.

**2. Enable smaller, locally-hosted models to perform specialised infrastructure tasks.**
General-purpose LLMs need to be large (and expensive) to reliably handle broad knowledge domains. By offloading the factual, lookup-heavy parts of the workflow — pricing queries, module documentation retrieval — to dedicated MCP tools, a smaller locally-hosted model (e.g. running under [Ollama](https://ollama.com/) via an [Open WebUI](https://github.com/open-webui/open-webui) devcontainer) can handle IaC cost-estimation tasks that would otherwise require a much larger model. This improves governance over data (nothing leaves the local environment), lowers inference costs, and makes the stack viable in air-gapped or privacy-sensitive settings.

> [!WARNING]
> This project is an academic exercise and is not intended for production use. It may contain security vulnerabilities and should be used with caution.

---

## Table of contents

1. [How it works](#how-it-works)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Environment variables](#environment-variables)
5. [Starting the server](#starting-the-server)
6. [API reference](#api-reference)
7. [MCP integration](#mcp-integration)
8. [Terraform README fetcher](#terraform-readme-fetcher)
9. [License](#license)

---

## How it works

```plain
MCP Client (e.g. Claude Desktop, Cursor)
        │
        │  MCP over HTTP (SSE / Streamable HTTP)
        ▼
┌───────────────────────────────┐
│  FastAPI application          │
│  • GET /infracost/prices      │  ◄── query parameters
│  • GET /hello                 │
│                               │
│  FastApiMCP layer             │  ◄── auto-generates MCP tools
│  • mounted at /mcp            │      from each FastAPI route
└───────────────────────────────┘
        │
        │  HTTPS / GraphQL
        ▼
  Infracost Pricing API
  (pricing.api.infracost.io/graphql)
```

[fastapi-mcp](https://github.com/tadata-org/fastapi-mcp) introspects every route registered on the FastAPI application and automatically exposes each route as an MCP tool. Any MCP-compatible client that connects to `http://localhost:8000/mcp` can therefore invoke `/infracost/prices` as a native tool call without any additional glue code.

---

## Prerequisites

| Requirement                      | Version         | Notes                                                                               |
| -------------------------------- | --------------- | ----------------------------------------------------------------------------------- |
| Python                           | ≥ 3.12          |                                                                                     |
| [uv](https://docs.astral.sh/uv/) | latest          | Python package manager                                                              |
| Node.js                          | ≥ 18 (optional) | Required only for the MCP Inspector                                                 |
| Infracost API key                | —               | Free tier available at [infracost.io](https://www.infracost.io/docs/#2-get-api-key) |
| GitHub personal access token     | —               | Optional — required only for the README fetcher script                              |

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/ripitchip/MCP-Infracost.git
cd MCP-Infracost
```

### 2. Install dependencies

The project uses `uv` as its package manager. All runtime dependencies are declared in [pyproject.toml](pyproject.toml).

```bash
uv pip install -e .
```

<details>
<summary>Core dependencies</summary>

| Package             | Version   | Purpose                       |
| ------------------- | --------- | ----------------------------- |
| `fastapi[standard]` | ≥ 0.129.0 | HTTP framework                |
| `fastapi-mcp`       | ≥ 0.4.0   | MCP layer over FastAPI routes |
| `mcp-proxy`         | ≥ 0.11.0  | MCP proxy utilities           |
| `uvicorn`           | ≥ 0.41.0  | ASGI server                   |
| `python-dotenv`     | ≥ 1.0.1   | `.env` file loading           |

</details>

### 3. Configure environment variables

Copy the example file and fill in at minimum your `INFRACOST_API_KEY`:

```bash
cp .env.example .env
```

See the [Environment variables](#environment-variables) section for a full description of each variable.

---

## Environment variables

| Variable            | Required | Default                                    | Description                                                                                                                                                                                 |
| ------------------- | -------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `INFRACOST_API_KEY` | **Yes**  | —                                          | API key used to authenticate requests to the Infracost GraphQL pricing API. Obtain one for free at [infracost.io](https://www.infracost.io/docs/#2-get-api-key).                            |
| `INFRACOST_API_URL` | No       | `https://pricing.api.infracost.io/graphql` | GraphQL endpoint for the Infracost API. Override only if you are running a self-hosted instance.                                                                                            |
| `GITHUB_TOKEN`      | No       | —                                          | Personal access token used by the README fetcher script to make authenticated GitHub API requests (5 000 req/h vs 60 req/h unauthenticated). Only the `public_repo` read scope is required. |

---

## Starting the server

```bash
uv run src/main.py
```

The server listens on `0.0.0.0:8000` by default. The following endpoints are immediately available:

| Path                    | Description                           |
| ----------------------- | ------------------------------------- |
| `GET /hello`            | Greeting / smoke-test route           |
| `GET /infracost/prices` | Cloud pricing query                   |
| `GET /mcp`              | MCP endpoint (SSE or Streamable HTTP) |
| `GET /docs`             | Auto-generated Swagger UI             |
| `GET /redoc`            | Auto-generated ReDoc UI               |

### Inspecting MCP tools interactively

The [MCP Inspector](https://github.com/modelcontextprotocol/inspector) provides a browser-based UI for browsing and calling the tools exposed by the server:

```bash
npx @modelcontextprotocol/inspector http://localhost:8000/mcp
```

Then open the URL printed in the terminal (typically `http://localhost:6274`).

![Inspector page](image.png)

---

## API reference

### `GET /hello`

A simple greeting endpoint, useful as a smoke-test to confirm the server is reachable.

**Query parameters**

| Parameter | Type     | Default   | Description                      |
| --------- | -------- | --------- | -------------------------------- |
| `name`    | `string` | `"World"` | Name to include in the greeting. |

**Example**

```plain
GET /hello?name=Alice
```

```json
{ "message": "Hello Alice!" }
```

---

### `GET /infracost/prices`

Queries the Infracost GraphQL API for on-demand compute pricing and returns up to five matching product entries.

**Query parameters**

| Parameter       | Type      | Default              | Description                                                                                                                                                                 |
| --------------- | --------- | -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `provider`      | `string`  | `"aws"`              | Cloud provider. Accepted values: `aws`, `gcp`, `azure` (case-insensitive).                                                                                                  |
| `location`      | `string`  | `"france"`           | Logical region alias **or** a raw provider region code. Built-in aliases: `france`, `europe`, `us`. See the table below for the region each alias resolves to per provider. |
| `cores`         | `integer` | `2`                  | Minimum number of vCPUs. Used as a filter attribute for AWS and Azure. Ignored for GCP when `instance_type` is provided.                                                    |
| `instance_type` | `string`  | _(provider default)_ | Exact instance/machine type identifier. When omitted the provider-specific default is used (`m5.large` for AWS, `n2-standard-2` for GCP, `Standard_D2s_v5` for Azure).      |
| `os`            | `string`  | `"Linux"`            | Operating system filter. Accepted values: `Linux`, `Windows`. Applicable to AWS and Azure; ignored for GCP.                                                                 |

**Region alias resolution**

| Alias    | AWS            | GCP            | Azure           |
| -------- | -------------- | -------------- | --------------- |
| `france` | `eu-west-3`    | `europe-west9` | `francecentral` |
| `europe` | `eu-central-1` | `europe-west1` | `westeurope`    |
| `us`     | `us-east-1`    | `us-central1`  | `eastus`        |

Any value that is not a recognised alias is forwarded to the API as-is, enabling you to pass raw region codes such as `ap-southeast-1` directly.

**Response schema**

```json
{
  "provider": "aws",
  "results_count": 3,
  "results": [
    {
      "attributes": [
        { "key": "instanceType", "value": "m5.large" },
        { "key": "vcpu", "value": "2" },
        { "key": "memory", "value": "8 GiB" }
      ],
      "prices": [{ "USD": "0.096", "unit": "Hrs" }]
    }
  ]
}
```

| Field           | Description                                                                                                                                               |
| --------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `provider`      | The provider that was queried, echoed back from the request.                                                                                              |
| `results_count` | Total number of matching products returned by the Infracost API before truncation.                                                                        |
| `results`       | Up to **5** matching product entries, each containing `attributes` (key/value pairs describing the resource) and `prices` (on-demand USD price per unit). |

**Error responses**

| Condition                   | Response                                      |
| --------------------------- | --------------------------------------------- |
| Unsupported provider        | `{ "error": "Provider non supporté" }`        |
| Missing `INFRACOST_API_KEY` | `{ "error": "INFRACOST_API_KEY is not set" }` |
| Network or API error        | `{ "error": "<exception message>" }`          |

**Examples**

```plain
# AWS m5.large in Paris
GET /infracost/prices?provider=aws&location=france&instance_type=m5.large

# Azure 4-core VM in West Europe running Windows
GET /infracost/prices?provider=azure&location=europe&cores=4&os=Windows

# GCP n2-standard-4 in the US
GET /infracost/prices?provider=gcp&location=us&instance_type=n2-standard-4
```

---

## MCP integration

The MCP endpoint is mounted at `/mcp`. Each FastAPI route is automatically reflected as an MCP tool by `fastapi-mcp`, meaning the parameter names, types, and descriptions described in the [API reference](#api-reference) apply equally when invoking the tool from an MCP client.

### Connecting Claude Desktop

Add the following block to your `claude_desktop_config.json` (typically located at `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "infracost": {
      "command": "npx",
      "args": ["mcp-remote", "http://localhost:8000/mcp"]
    }
  }
}
```

Restart Claude Desktop. The `get_infrastructure_prices` and `say_hello` tools will appear in the tool picker.

### Connecting Cursor or other HTTP-native MCP clients

Point the client directly at:

```plain
http://localhost:8000/mcp
```

---

## Terraform README fetcher

`scripts/fetch_terraform_readmes.py` crawls every public repository belonging to a GitHub organisation, downloads each `README.md`, strips all noise (badges, banners, footer sections), and writes both the raw and cleaned versions to disk under `downloads/extractN/`.

The resulting corpus of cleaned documents is designed to be consumed by an LLM as grounding context — see [Using the corpus with the MCP server](#using-the-corpus-with-the-mcp-server) below.

### Usage

```bash
uv run scripts/fetch_terraform_readmes.py [OPTIONS]
```

### Options

| Option               | Type     | Default                 | Description                                                                                                                                             |
| -------------------- | -------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `--org`              | `string` | `terraform-aws-modules` | GitHub organisation to crawl. All public repositories belonging to this organisation will be processed.                                                 |
| `--root`             | `string` | Repository root         | Absolute or relative path to the workspace root. The `downloads/` directory is created under this path. Defaults to the parent directory of the script. |
| `--include-archived` | flag     | `false`                 | When set, archived repositories are included. By default they are skipped.                                                                              |

`GITHUB_TOKEN` is read from the environment (or from `.env`). Without it, requests are made unauthenticated and are subject to GitHub's 60 requests/hour rate limit, which will be exhausted quickly for large organisations. With a token the limit rises to 5 000 requests/hour. Only the default read scope (no special permissions) is required.

### How it fetches READMEs

The script uses the GitHub REST API with no external dependencies — only Python's standard library `urllib`.

```plain
for each repository in the organisation
        │
        ├─ GET /orgs/{org}/repos?per_page=100&page=N&type=public
        │   Paginated until an empty page is returned.
        │   Archived repos are filtered out unless --include-archived is set.
        │
        └─ GET /repos/{org}/{repo}/readme
            GitHub returns the file metadata including the content
            encoded as a base64 string.
            The script base64-decodes it to recover the raw Markdown text.
```

Rate-limit headers (`X-RateLimit-Remaining`, `X-RateLimit-Reset`) are inspected on every request. If the limit is exhausted the script raises a descriptive error that includes the number of seconds until the window resets, allowing you to resume after waiting.

### How it cleans READMEs

Raw Terraform module READMEs are typically dense with CI badges, marketing banners, and administrative footer sections that add zero value as LLM context. The `clean_readme()` function applies a sequence of deterministic transformations to reduce each document to its most information-dense parts:

```plain
Raw Markdown text
        │
        ▼
1. Locate the first H1 title line (# …)
   → Keep the title.
   → Keep the first non-empty, non-heading paragraph line below it
     as the module description. Skip badge/banner lines.
        │
        ▼
2. Locate content start
   → Preferred: the line immediately after a ## Usage heading.
   → Fallback 1: the first H3 heading (### …).
   → Fallback 2: the line after the H1 title.
        │
        ▼
3. Locate content end
   → Scan forward from the content-start position.
   → Stop at the first H2/H3 heading whose normalised title matches
     any entry in the footer set:
       authors · author · license · maintainers · maintainer ·
       contributing · contribution · support · changelog ·
       additional information · security
        │
        ▼
4. Filter body lines
   → Drop any line that is a badge or banner:
       • starts with [![  or  ![
       • contains shields.io
       • contains "badge" and an http(s) URL
   → Drop the ## Usage heading line itself (its content is kept).
        │
        ▼
5. Reassemble
   → Concatenate: [title + description] + [filtered body]
   → Collapse runs of consecutive blank lines to a single blank line.
   → Strip leading and trailing blank lines.
        │
        ▼
Cleaned Markdown text
```

**Before / after example** (truncated for brevity):

```markdown
# terraform-aws-vpc

[![Build Status](https://…)](https://…) ← removed
[![License](https://…)](https://…) ← removed

A Terraform module for creating AWS VPCs.

## Usage ← heading removed, content kept

module "vpc" {
source = "terraform-aws-modules/vpc/aws"
name = "my-vpc"
cidr = "10.0.0.0/16"
}

## Authors ← stop here — footer removed

…
```

Becomes:

```markdown
# terraform-aws-vpc

A Terraform module for creating AWS VPCs.

module "vpc" {
source = "terraform-aws-modules/vpc/aws"
name = "my-vpc"
cidr = "10.0.0.0/16"
}
```

### Output structure

Each run creates a new numbered directory under `downloads/` so that successive runs never overwrite previous output:

```plain
downloads/
└── extractN/
    ├── README.md           # Human-readable index of processed / skipped repos
    ├── summary.json        # Machine-readable run metadata (timestamps, counts, paths)
    └── <repo-name>/
        ├── README.original.md   # Raw README exactly as returned by GitHub
        └── README.cleaned.md    # Cleaned, example-focused extract
```

`summary.json` schema:

```json
{
  "organization": "terraform-aws-modules",
  "output": "downloads/extract1",
  "repository_count": 42,
  "generated_at": 1708444800,
  "processed": [
    {
      "repo": "terraform-aws-vpc",
      "readme_path": "README.md",
      "original_file": "downloads/extract1/terraform-aws-vpc/README.original.md",
      "cleaned_file": "downloads/extract1/terraform-aws-vpc/README.cleaned.md"
    }
  ],
  "skipped": [{ "repo": "terraform-aws-legacy", "reason": "archived" }]
}
```

### Examples

```bash
# Fetch all public repos from terraform-aws-modules (default)
uv run scripts/fetch_terraform_readmes.py

# Fetch from a different organisation, including archived repos
uv run scripts/fetch_terraform_readmes.py --org hashicorp --include-archived

# Override the output root directory
uv run scripts/fetch_terraform_readmes.py --root /tmp/my-workspace
```

---

### Using the corpus with the MCP server

The cleaned READMEs are plain Markdown files — small, focused, and free of noise. They are well-suited for use as grounding context for an LLM when answering questions about Terraform modules. Below are three progressively more sophisticated patterns for integrating the corpus with this MCP server.

#### Pattern 1 — Static system prompt injection

The simplest approach: read one or more `README.cleaned.md` files at server start-up and inject their content into a system prompt that accompanies every LLM call.

```plain
┌── MCP server ─────────────────────────────────────────────┐
│  On start-up: load downloads/extract1/*/README.cleaned.md  │
│  Build a combined system prompt:                           │
│    "You are an IaC cost assistant. Here is the             │
│     documentation for the available Terraform modules:     │
│     <cleaned READMEs concatenated here>"                   │
└────────────────────────────────────────────────────────────┘
```

**Trade-offs:** trivial to implement; works only for small corpora (a few modules) because the entire corpus must fit in the model's context window.

#### Pattern 2 — Retrieval-augmented generation (RAG)

For larger corpora (dozens to hundreds of modules), embed each `README.cleaned.md` into a vector store at index time. At query time, retrieve the most semantically relevant documents and inject only those into the context.

```plain
Index time (run once after each fetch)
  cleaned READMEs → text chunker → embedding model → vector store

Query time (per MCP tool call)
  user query → embedding model → vector store similarity search
             → top-K relevant README chunks
             → injected as context into the LLM prompt
             → LLM generates answer grounded in module documentation
```

A new MCP route could expose this capability:

```plain
GET /infracost/context?query=create+a+VPC+with+public+subnets
→ returns: { "chunks": [ { "repo": "terraform-aws-vpc", "content": "…" } ] }
```

The MCP client (e.g. Claude) could call `get_infracost_context` to fetch relevant documentation before calling `get_infracost_prices` to estimate costs — chaining the two tools in a single reasoning step.

#### Pattern 3 — Tool-augmented context (current architecture extension)

No vector store required. Add a dedicated MCP tool that reads the `downloads/` directory at request time and returns the cleaned README for a named module. The LLM decides when to call it.

```python
@router.get("/infracost/module-doc")
async def get_module_doc(module: str = Query(...)) -> dict:
    """Return the cleaned README for a Terraform module by name."""
    path = Path("downloads") / "extract1" / module / "README.cleaned.md"
    if not path.exists():
        return {"error": f"No documentation found for module '{module}'"}
    return {"module": module, "documentation": path.read_text()}
```

`fastapi-mcp` would automatically expose this as a `get_module_doc` tool. A typical multi-step interaction would then look like:

```plain
User:  "How much does the terraform-aws-vpc module cost to run in Paris?"

LLM:   [calls get_module_doc(module="terraform-aws-vpc")]
       → reads the cleaned README to understand required inputs

       [calls get_infracost_prices(provider="aws", location="france",
                                   instance_type="…")]
       → retrieves live on-demand pricing

       [synthesises both results into a final answer]
```

This pattern keeps the architecture stateless and simple while allowing the LLM to ground its answers in real module documentation.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
