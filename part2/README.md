# Part 2: Building the Regulatory Risk Copilot — From Extraction to Actionable Intelligence

Part 1 turned unstructured FDA Complete Response Letters into structured data. Part 2 turns that data into a **decision-support copilot** using Databricks Agent Bricks Supervisor to orchestrate multiple specialized agents — all configured through the UI with minimal code.

## Multi-Agent Architecture

```
User Query: "We're preparing an NDA for a GLP-1 oral tablet.
             What are the top rejection risks?"
                    │
                    ▼
          ┌─────────────────────┐
          │  Supervisor Agent    │  Routes, orchestrates, synthesizes
          │  (Agent Bricks UI)   │
          └────────┬────────────┘
       ┌───────────┼───────────────┐
       ▼           ▼               ▼
┌────────────┐ ┌────────────┐ ┌──────────────┐
│    CRL     │ │  PubMed    │ │   openFDA    │
│ Knowledge  │ │   Agent    │ │ Drug Label   │
│  Assistant │ │   (MCP)    │ │ Agent (MCP)  │
└────────────┘ └────────────┘ └──────────────┘
  Vector Search   PubMed MCP     OpenFDA MCP
  on Part 1 data  (Custom App)   (Custom App)
```

## Prerequisites

- Part 1 completed: `parsed_letters` and `structured_insights` tables exist in Unity Catalog
- Databricks workspace with serverless compute and Unity Catalog enabled
- Agent Bricks Supervisor enabled (supported regions: `us-east-1` or `us-west-2`)
- Foundation models available via `system.ai` schema

---

## Agent 1: CRL Knowledge Assistant

Uses the structured CRL data from Part 1 as a knowledge base to answer questions about historical FDA rejection patterns.

### Option A: Vector Search Index (Recommended)

Create a Vector Search index on the deficiency summaries for semantic retrieval.

1. Run [`01-Vector_Search_Index.py`](01-Vector_Search_Index.py) to create the index
2. In Agent Bricks, create a **Knowledge Assistant**:
   - **Data source**: Select the Vector Search index
   - **Description**: "Searches historical FDA Complete Response Letters to find rejection patterns, common deficiencies, and regulatory citations by drug class, dosage form, or indication"
3. Deploy the Knowledge Assistant endpoint

### Option B: Direct UC Table (Simpler)

Skip the vector index and point the Knowledge Assistant directly to the Unity Catalog table location.

1. In Agent Bricks, create a **Knowledge Assistant**:
   - **Data source**: Point to the `structured_insights` table or the raw `parsed_letters` table in UC
   - **Description**: Same as above
2. Deploy the endpoint

---

## Agent 2: PubMed Literature Agent (MCP)

Provides real-time biomedical literature search via [PubMed MCP Server](https://github.com/cyanheads/pubmed-mcp-server).

### Option A: Use the Public Instance (Quickest)

A public PubMed MCP endpoint is available at `https://pubmed.caseyjhand.com/mcp`. You can add this directly as an **External MCP Server** in Databricks — no app deployment needed.

1. Navigate to **Agents → MCP Servers → Add External MCP Server**
2. Create a Unity Catalog connection pointing to `https://pubmed.caseyjhand.com/mcp`
3. Grant end users `USE CONNECTION` on the UC connection

### Option B: Host as Custom MCP (Databricks App)

For production use, host your own instance for reliability and higher rate limits.

#### File Structure

```
pubmed-mcp-server/
├── app.yaml
├── requirements.txt
├── pyproject.toml
└── server/
    └── main.py
```

#### `app.yaml`

```yaml
command: [
  'uv',
  'run',
  'pubmed-server',
]
env:
  - name: MCP_TRANSPORT_TYPE
    value: http
  - name: MCP_HTTP_PORT
    value: "8000"
  - name: NCBI_API_KEY
    value: "<your-ncbi-api-key>"    # Optional: get one at https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/
```

#### `requirements.txt`

```
uv
```

#### `pyproject.toml`

```toml
[project]
name = "pubmed-mcp-server"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "mcp[cli]",
    "requests",
    "beautifulsoup4",
]

[project.scripts]
pubmed-server = "server.main:main"
```

#### `server/main.py`

```python
import os
import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("PubMed Search")

NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
API_KEY = os.environ.get("NCBI_API_KEY", "")

@mcp.tool()
def search_pubmed(query: str, max_results: int = 10) -> str:
    """Search PubMed for biomedical articles matching the query. Returns PMIDs and article summaries."""
    params = {"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"}
    if API_KEY:
        params["api_key"] = API_KEY
    resp = requests.get(f"{NCBI_BASE}/esearch.fcgi", params=params)
    data = resp.json()
    pmids = data.get("esearchresult", {}).get("idlist", [])
    if not pmids:
        return "No results found."
    # Fetch summaries
    params2 = {"db": "pubmed", "id": ",".join(pmids), "retmode": "json"}
    if API_KEY:
        params2["api_key"] = API_KEY
    resp2 = requests.get(f"{NCBI_BASE}/esummary.fcgi", params=params2)
    summaries = resp2.json().get("result", {})
    results = []
    for pmid in pmids:
        info = summaries.get(pmid, {})
        results.append(f"PMID: {pmid}\nTitle: {info.get('title','N/A')}\nSource: {info.get('source','N/A')} ({info.get('pubdate','N/A')})\nAuthors: {', '.join(a.get('name','') for a in info.get('authors',[])[:3])}\n")
    return "\n".join(results)

@mcp.tool()
def get_pubmed_abstract(pmid: str) -> str:
    """Fetch the full abstract and metadata for a PubMed article by its PMID."""
    params = {"db": "pubmed", "id": pmid, "retmode": "xml"}
    if API_KEY:
        params["api_key"] = API_KEY
    resp = requests.get(f"{NCBI_BASE}/efetch.fcgi", params=params)
    return resp.text[:5000]  # Return first 5000 chars of XML

@mcp.tool()
def find_related_articles(pmid: str, max_results: int = 5) -> str:
    """Find articles related to a given PubMed article by PMID."""
    params = {"dbfrom": "pubmed", "db": "pubmed", "id": pmid, "cmd": "neighbor_score", "retmode": "json"}
    if API_KEY:
        params["api_key"] = API_KEY
    resp = requests.get(f"{NCBI_BASE}/elink.fcgi", params=params)
    data = resp.json()
    links = data.get("linksets", [{}])[0].get("linksetdbs", [{}])[0].get("links", [])
    related_pmids = [l.get("id") for l in links[:max_results]]
    if not related_pmids:
        return "No related articles found."
    return search_pubmed(f"{' OR '.join(related_pmids)}[uid]", max_results)

def main():
    mcp.run(transport="streamable-http", host="0.0.0.0", port=int(os.environ.get("MCP_HTTP_PORT", "8000")))
```

#### Deploy

```bash
# Authenticate
databricks auth login --host https://<your-workspace-hostname>

# Create the app
databricks apps create pubmed-mcp-server

# Sync and deploy
DATABRICKS_USERNAME=$(databricks current-user me | jq -r .userName)
databricks sync ./pubmed-mcp-server "/Users/$DATABRICKS_USERNAME/pubmed-mcp-server"
databricks apps deploy pubmed-mcp-server \
  --source-code-path "/Workspace/Users/$DATABRICKS_USERNAME/pubmed-mcp-server"
```

Your MCP endpoint will be at: `https://<app-url>/mcp`

#### Register in Databricks

1. Navigate to **Agents → MCP Servers**
2. Click **Add Custom MCP Server**
3. Select the deployed Databricks App
4. Grant end users `USE CONNECTION` on the UC connection

### PubMed MCP Tools
| Tool | Description |
|------|-------------|
| `search_pubmed` | Search articles by keyword, MeSH terms, date range |
| `get_pubmed_abstract` | Fetch full abstract and metadata by PMID |
| `find_related_articles` | Discover similar papers and citation networks |

---

## Agent 3: openFDA Drug Label & Safety Agent (MCP)

Provides real-time access to FDA drug labels, adverse events, recalls, and approval data. **No PDF processing needed** — all data is accessed via the [openFDA REST API](https://open.fda.gov/apis/).

### Setup: Host as Custom MCP (Databricks App)

#### File Structure

```
openfda-mcp-server/
├── app.yaml
├── requirements.txt
├── pyproject.toml
└── server/
    └── main.py
```

#### `app.yaml`

```yaml
command: [
  'uv',
  'run',
  'openfda-server',
]
env:
  - name: FDA_API_KEY
    value: "<your-fda-api-key>"    # Optional: get one at https://open.fda.gov/apis/authentication/
```

#### `requirements.txt`

```
uv
```

#### `pyproject.toml`

```toml
[project]
name = "openfda-mcp-server"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "mcp[cli]",
    "requests",
]

[project.scripts]
openfda-server = "server.main:main"
```

#### `server/main.py`

```python
import os
import json
import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("openFDA Search")

BASE_URL = "https://api.fda.gov"
API_KEY = os.environ.get("FDA_API_KEY", "")

def _fda_query(endpoint: str, search: str, limit: int = 5) -> str:
    params = {"search": search, "limit": limit}
    if API_KEY:
        params["api_key"] = API_KEY
    resp = requests.get(f"{BASE_URL}{endpoint}", params=params)
    if resp.status_code != 200:
        return f"Error: {resp.status_code} - {resp.text[:500]}"
    data = resp.json()
    return json.dumps(data.get("results", []), indent=2)[:5000]

@mcp.tool()
def search_drug_labels(query: str, limit: int = 5) -> str:
    """Search FDA drug product labeling (prescribing info, indications, warnings, adverse reactions). Use drug name, active ingredient, or indication as query."""
    return _fda_query("/drug/label.json", query, limit)

@mcp.tool()
def search_drug_adverse_events(query: str, limit: int = 5) -> str:
    """Search FDA FAERS (Adverse Event Reporting System) for drug safety reports. Use drug name or reaction term as query."""
    return _fda_query("/drug/event.json", query, limit)

@mcp.tool()
def search_drug_recalls(query: str, limit: int = 5) -> str:
    """Search FDA drug recall and enforcement reports. Use drug name, company, or reason as query."""
    return _fda_query("/drug/enforcement.json", query, limit)

@mcp.tool()
def search_drug_approvals(query: str, limit: int = 5) -> str:
    """Search FDA drug approval database (Drugs@FDA). Use drug name, applicant, or application number as query."""
    return _fda_query("/drug/drugsfda.json", query, limit)

@mcp.tool()
def search_drug_ndc(query: str, limit: int = 5) -> str:
    """Search the National Drug Code (NDC) directory for drug product information including packaging, routes, and manufacturers."""
    return _fda_query("/drug/ndc.json", query, limit)

def main():
    mcp.run(transport="streamable-http", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
```

#### Deploy

```bash
# Authenticate
databricks auth login --host https://<your-workspace-hostname>

# Create the app
databricks apps create openfda-mcp-server

# Sync and deploy
DATABRICKS_USERNAME=$(databricks current-user me | jq -r .userName)
databricks sync ./openfda-mcp-server "/Users/$DATABRICKS_USERNAME/openfda-mcp-server"
databricks apps deploy openfda-mcp-server \
  --source-code-path "/Workspace/Users/$DATABRICKS_USERNAME/openfda-mcp-server"
```

Your MCP endpoint will be at: `https://<app-url>/mcp`

#### Register in Databricks

1. Navigate to **Agents → MCP Servers**
2. Click **Add Custom MCP Server**
3. Select the deployed Databricks App
4. Grant end users `USE CONNECTION` on the UC connection

### openFDA MCP Tools
| Tool | Description |
|------|-------------|
| `search_drug_labels` | Prescribing info, indications, warnings, adverse reactions |
| `search_drug_adverse_events` | FAERS safety reports |
| `search_drug_recalls` | Recall and enforcement data |
| `search_drug_approvals` | NDA/BLA approval history |
| `search_drug_ndc` | National Drug Code directory |

---

## Supervisor Agent Setup

Once all three sub-agents are configured, wire them together with the Supervisor.

### Steps

1. Navigate to **Agents → Supervisor Agent → Build**
2. **Name**: `FDA Regulatory Risk Copilot`
3. **Description**: "A multi-agent regulatory copilot that helps teams de-risk drug submissions by analyzing historical FDA rejection patterns, cross-referencing biomedical literature, and checking current FDA drug labels and safety data."
4. **Add Agents** (up to 20):
   - **Agent Endpoint**: Select CRL Knowledge Assistant endpoint
     - Name: `CRL Knowledge Base`
     - Description: "Searches historical FDA Complete Response Letters. Use for questions about rejection patterns, common deficiencies, and regulatory citations by drug class, dosage form, or indication."
   - **External MCP Server**: Select PubMed MCP connection
     - Name: `PubMed Literature Search`
     - Description: "Searches PubMed biomedical literature. Use for finding published evidence about drug safety signals, clinical trial results, and regulatory science relevant to the query."
   - **External MCP Server**: Select openFDA MCP connection
     - Name: `FDA Drug Labels & Safety`
     - Description: "Queries FDA drug labels, adverse events, recalls, and approval data. Use for checking current labeling requirements, safety signals in FAERS, and approval history for similar drugs."
5. **Instructions**:
   ```
   You are a regulatory risk copilot for pharmaceutical teams preparing FDA submissions.

   When answering questions:
   1. First check the CRL Knowledge Base for historical rejection patterns relevant to the query
   2. Cross-reference with PubMed for published evidence supporting or contradicting identified risks
   3. Check openFDA for current drug labels, adverse events, and approval status of similar products
   4. Synthesize findings into a prioritized risk assessment with specific citations

   Always cite your sources: CRL application numbers, PubMed PMIDs, and FDA label references.
   ```
6. Click **Create Agent** and wait for build to complete

### Test Queries

Once deployed, try these in the Playground:

> "What are the top 3 deficiency categories for BLA submissions in oncology?"

> "We're submitting an NDA for an oral GLP-1 receptor agonist. What rejection risks should we prepare for?"

> "Are there recent safety signals in FAERS for JAK inhibitors that could impact our upcoming sNDA?"

> "Generate a pre-submission risk checklist for a new biologic targeting PD-L1."

---

## Project Structure

```
part2/
├── README.md                         # This file
└── 01-Vector_Search_Index.py         # Create Vector Search index on CRL data
```

## References

- [Agent Bricks: Supervisor Agent Docs](https://docs.databricks.com/aws/en/generative-ai/agent-bricks/multi-agent-supervisor)
- [MCP on Databricks](https://docs.databricks.com/aws/en/generative-ai/mcp/)
- [Agent Bricks + MCP Integration](https://www.databricks.com/resources/demos/videos/agent-bricks-mcp-integration-databricks)
- [PubMed MCP Server (Node.js)](https://github.com/cyanheads/pubmed-mcp-server)
- [PubMed MCP Server (Python)](https://github.com/JackKuo666/PubMed-MCP-Server)
- [OpenFDA MCP Server](https://github.com/Augmented-Nature/OpenFDA-MCP-Server)
- [openFDA APIs](https://open.fda.gov/apis/)
- [NCBI E-utilities API](https://www.ncbi.nlm.nih.gov/books/NBK25501/)
