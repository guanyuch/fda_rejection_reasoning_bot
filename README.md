# FDA Rejection Letters - Regulatory Risk Copilot (Part 1: Information Extraction)

A step-by-step guide for extracting structured data from FDA Complete Response Letters (CRLs) using Databricks Agent Bricks, based on the Databricks blog: [Building a Regulatory Risk Copilot with Databricks Agent Bricks (Part 1: Information Extraction)](https://www.databricks.com/blog/building-regulatory-risk-copilot-databricks-agent-bricks-part-1-information-extraction).

## Background

In July 2025, the US FDA publicly released 200+ Complete Response Letters (CRLs) — decision letters explaining why drug and biologic applications (NDAs/BLAs) were **not approved** on first pass. This repo demonstrates how to extract structured insights from these PDFs at scale using Databricks.

## Architecture

```
FDA CRL PDFs (zip)
    │
    ▼
┌──────────────────────────┐
│  01: PDF Preparation     │  Unzip → ai_parse_document() → parsed text table
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  02: KIE Schema Design   │  Define extraction schema via Agent Bricks UI
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  03: Apply KIE &         │  ai_query(<endpoint>, text) → structured JSON
│      Gold Table          │  Flatten JSON → queryable columns
└──────────────────────────┘
```

## Prerequisites

- **Databricks workspace** with serverless compute enabled
- **Unity Catalog** configured with a catalog, schema, and volume
- **Mosaic AI Agent Bricks** (Preview) enabled
- Foundation models accessible via `system.ai` schema
- Supported regions: `us-east-1` or `us-west-2` (AWS) or equivalent Azure regions

## Quick Start

### 1. Get the FDA Data

Download the FDA Complete Response Letters:
- **Approved CRLs**: https://download.open.fda.gov/approved_CRLs.zip
- **Unapproved CRLs**: https://download.open.fda.gov/unapproved_CRLs.zip

Place the zip file in `data/raw/` and upload it to a Unity Catalog Volume in your Databricks workspace.

### 2. Run Notebook 01 — PDF Preparation

[`notebooks/01-PDF_Preparation.py`](notebooks/01-PDF_Preparation.py)

- Unzips the FDA CRL PDFs in your UC Volume
- Uses `ai_parse_document()` to convert PDFs to structured markdown
- Creates a `parsed_letters` table with extracted text

**Key function**: `ai_parse_document(content)` — reliably parses text and images from complex PDF documents.

### 3. Configure KIE Agent — Schema Design (Agent Bricks UI)

[`notebooks/02-KIE_Schema.json`](notebooks/02-KIE_Schema.json)

This step uses the **Agent Bricks Information Extraction UI** in Databricks:

1. Navigate to **Machine Learning → Agent Bricks → Information Extraction**
2. Create a new agent:
   - **Name**: `fda-crl-extraction` (or your preferred name)
   - **Dataset type**: Unlabeled
   - **Data location**: Point to your `parsed_letters` table, and select `text` as the **input column**
   - **Output schema**: Use the default schema first to proceed to the next page. Once on the next page, click **JSON Schema** and paste the contents of `02-KIE_Schema.json`
   - **Optimization**: "Optimize for Complexity" (recommended for regulatory documents)
3. **Refine** the extraction by reviewing sample outputs with your business SME
4. **Deploy** as a serverless endpoint (single-click deployment)

The schema extracts these fields from each CRL:

| Field | Description |
|-------|-------------|
| `application_number` | FDA application identifier (e.g., NDA 123456) |
| `application_type` | NDA or BLA |
| `applicant` | Company name |
| `drug_product` | Drug name, dosage form, strengths, new indication |
| `primary_deficiency_category` | Main reason for rejection |
| `deficiency_summary_paragraphs` | Summary of approvability deficiencies |
| `FDA_Rejection_Citing` | Specific regulatory citations for rejection |
| `fda_letter_author` | FDA signatory title and role |
| `resubmission_instructions` | FDA codes/regulations and required actions |
| `date_original_submission` | Original submission date |
| `date_letter_reply` | CRL date |
| `prescribing_information_instructions` | PI revision guidance |
| `carton_container_labeling_instructions` | Labeling requirements |
| `safety_update_instructions` | Safety data requirements |

### 4. Run Notebook 03 — Apply and Check KIE

[`notebooks/03-Apply_and_Check_KIE.sql`](notebooks/03-Apply_and_Check_KIE.sql)

- Calls your deployed KIE endpoint using `ai_query()` against all parsed documents
- Creates a `structured_insights` table with extracted JSON
- Flattens the extracted JSON into individual queryable columns
- Uses widget parameters for table names — set `SourceTableName` and `DestinationTableName`

**Key function**: `ai_query('<endpoint-name>', text, failOnError => false)`

## Project Structure

```
fda-rejection-letters/
├── README.md
├── data/
│   └── raw/                          # Place zip file here
│       └── PUT_ZIP_FILE_HERE.md
└── notebooks/
    ├── 01-PDF_Preparation.py              # Unzip + parse PDFs
    ├── 02-KIE_Schema.json                 # Extraction schema for Agent Bricks
    └── 03-Apply_and_Check_KIE.sql    # Run KIE + flatten to queryable columns
```

## Configuration

Before running, update placeholder values in the notebooks:

| Placeholder | Example Value |
|-------------|---------------|
| `<catalog>` | `my_catalog` |
| `<schema>` | `fda_letters` |
| `<volume>` | `fda_letters` |
| `<your-kie-endpoint-name>` | `kie-bb69b43d-endpoint` |

## References

- [Blog: Building a Regulatory Risk Copilot (Part 1)](https://www.databricks.com/blog/building-regulatory-risk-copilot-databricks-agent-bricks-part-1-information-extraction)
- [Agent Bricks: Information Extraction Docs](https://docs.databricks.com/en/generative-ai/agent-bricks/key-info-extraction.html)
- [ai_parse_document() Reference](https://docs.databricks.com/en/sql/language-manual/functions/ai_parse_document.html)
- [ai_query() Reference](https://docs.databricks.com/en/sql/language-manual/functions/ai_query.html)
- [FDA Complete Response Letters (openFDA)](https://open.fda.gov/apis/transparency/completeresponseletters/)
