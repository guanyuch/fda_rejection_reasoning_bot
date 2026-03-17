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

### Setup: Host as Custom MCP (Databricks App)

1. **Create a Databricks App** to host the PubMed MCP server:
   - Navigate to **Compute → Apps → Create App**
   - Use the PubMed MCP server package ([npm](https://www.npmjs.com/package/@cyanheads/pubmed-mcp-server) or [Python](https://github.com/JackKuo666/PubMed-MCP-Server))
   - Configure with your [NCBI API key](https://ncbiinsights.ncbi.nlm.nih.gov/2017/11/02/new-api-keys-for-the-e-utilities/) (optional but recommended for higher rate limits)

2. **Register as MCP Server** in Databricks:
   - Navigate to **Agents → MCP Servers**
   - Add the Databricks App as a Custom MCP server
   - Create a Unity Catalog connection for it

3. **Grant permissions**:
   - Grant end users `USE CONNECTION` on the UC connection

### PubMed MCP Capabilities
- **Search**: Query PubMed for articles by keyword, author, date range, MeSH terms
- **Fetch**: Retrieve full article metadata (title, abstract, authors, journal, DOI)
- **Citations**: Find related articles and citation networks for a given PMID
- **Research plans**: Generate structured literature search strategies

---

## Agent 3: openFDA Drug Label & Safety Agent (MCP)

Provides real-time access to FDA drug labels, adverse events, recalls, and approval data via [OpenFDA MCP Server](https://github.com/Augmented-Nature/OpenFDA-MCP-Server). **No PDF processing needed** — all data is accessed via the openFDA REST API.

### Setup: Host as Custom MCP (Databricks App)

1. **Create a Databricks App** to host the openFDA MCP server:
   - Navigate to **Compute → Apps → Create App**
   - Use the [OpenFDA MCP Server](https://github.com/Augmented-Nature/OpenFDA-MCP-Server) package
   - Optionally configure with an [openFDA API key](https://open.fda.gov/apis/authentication/) for higher rate limits

2. **Register as MCP Server** in Databricks:
   - Navigate to **Agents → MCP Servers**
   - Add the Databricks App as a Custom MCP server
   - Create a Unity Catalog connection for it

3. **Grant permissions**:
   - Grant end users `USE CONNECTION` on the UC connection

### openFDA MCP Capabilities
- **Drug Labels**: Search prescription and OTC drug labeling (indications, warnings, adverse reactions)
- **Adverse Events**: Query FAERS (FDA Adverse Event Reporting System) data
- **Recalls**: Search drug recall and enforcement data
- **Approvals**: Look up NDA/BLA approval history and status
- **NDC Directory**: Query National Drug Code directory

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
