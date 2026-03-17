# Databricks notebook source

# MAGIC %md
# MAGIC # Part 2, Step 1: Create Vector Search Index on CRL Data
# MAGIC
# MAGIC This notebook creates a Vector Search index on the structured CRL insights from Part 1,
# MAGIC enabling semantic search over FDA rejection patterns for the Knowledge Assistant agent.
# MAGIC
# MAGIC ### Prerequisites
# MAGIC - Part 1 completed: `structured_insights` table exists with extracted CRL data
# MAGIC - Vector Search endpoint available (or will be created below)
# MAGIC - `databricks-gte-large-en` embedding model endpoint available

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.1 Configuration
# MAGIC
# MAGIC Update these values to match your environment.

# COMMAND ----------

# Configuration - UPDATE THESE
CATALOG = "<catalog>"
SCHEMA = "<schema>"
SOURCE_TABLE = f"{CATALOG}.{SCHEMA}.structured_insights"

# Vector Search settings
VS_ENDPOINT_NAME = "fda_crl_vs_endpoint"
VS_INDEX_NAME = f"{CATALOG}.{SCHEMA}.crl_deficiency_index"
EMBEDDING_MODEL_ENDPOINT = "databricks-gte-large-en"

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.2 Prepare the search corpus
# MAGIC
# MAGIC Create a table with the text content we want to make searchable.
# MAGIC We combine key fields into a single searchable text column.

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE IDENTIFIER(:search_corpus_table) AS
# MAGIC SELECT
# MAGIC   path,
# MAGIC   extracted_info:NDA_ID::STRING AS NDA_ID,
# MAGIC   extracted_info:applicant::STRING AS applicant,
# MAGIC   extracted_info:application_type::STRING AS application_type,
# MAGIC   extracted_info:drug_product.name::STRING AS drug_name,
# MAGIC   extracted_info:drug_product.dosage_form::STRING AS dosage_form,
# MAGIC   extracted_info:primary_deficiency_category::STRING AS primary_deficiency_category,
# MAGIC   extracted_info:deficiency_summary_paragraphs::STRING AS deficiency_summary,
# MAGIC   extracted_info:FDA_Rejection_Citing::STRING AS rejection_citing,
# MAGIC   extracted_info:date_letter_reply::STRING AS date_letter_reply,
# MAGIC   CONCAT_WS(' | ',
# MAGIC     CONCAT('NDA: ', extracted_info:NDA_ID::STRING),
# MAGIC     CONCAT('Drug: ', extracted_info:drug_product.name::STRING),
# MAGIC     CONCAT('Dosage Form: ', extracted_info:drug_product.dosage_form::STRING),
# MAGIC     CONCAT('Application Type: ', extracted_info:application_type::STRING),
# MAGIC     CONCAT('Primary Deficiency: ', extracted_info:primary_deficiency_category::STRING),
# MAGIC     CONCAT('Deficiency Summary: ', extracted_info:deficiency_summary_paragraphs::STRING),
# MAGIC     CONCAT('FDA Rejection Citing: ', extracted_info:FDA_Rejection_Citing::STRING)
# MAGIC   ) AS search_text
# MAGIC FROM IDENTIFIER(:source_table)
# MAGIC WHERE extracted_info IS NOT NULL

# COMMAND ----------

spark.sql(f"""
    SELECT * FROM {CATALOG}.{SCHEMA}.crl_search_corpus LIMIT 5
""").display()

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.3 Create Vector Search Endpoint (if needed)

# COMMAND ----------

from databricks.vector_search.client import VectorSearchClient

vsc = VectorSearchClient()

# Check if endpoint exists, create if not
try:
    vsc.get_endpoint(VS_ENDPOINT_NAME)
    print(f"Endpoint '{VS_ENDPOINT_NAME}' already exists.")
except Exception:
    print(f"Creating endpoint '{VS_ENDPOINT_NAME}'...")
    vsc.create_endpoint(name=VS_ENDPOINT_NAME, endpoint_type="STANDARD")
    print("Endpoint created. It may take a few minutes to be ready.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.4 Create Vector Search Index
# MAGIC
# MAGIC Creates a Delta Sync index that automatically stays in sync with the source table.

# COMMAND ----------

SEARCH_CORPUS_TABLE = f"{CATALOG}.{SCHEMA}.crl_search_corpus"

# Create the index
try:
    index = vsc.get_index(VS_ENDPOINT_NAME, VS_INDEX_NAME)
    print(f"Index '{VS_INDEX_NAME}' already exists.")
except Exception:
    print(f"Creating index '{VS_INDEX_NAME}'...")
    index = vsc.create_delta_sync_index(
        endpoint_name=VS_ENDPOINT_NAME,
        index_name=VS_INDEX_NAME,
        source_table_name=SEARCH_CORPUS_TABLE,
        pipeline_type="TRIGGERED",
        primary_key="path",
        embedding_source_column="search_text",
        embedding_model_endpoint_name=EMBEDDING_MODEL_ENDPOINT,
    )
    print("Index created. Initial sync may take several minutes.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.5 Test the index
# MAGIC
# MAGIC Run a sample similarity search to verify the index is working.

# COMMAND ----------

# Wait for index to be ready (check status)
index = vsc.get_index(VS_ENDPOINT_NAME, VS_INDEX_NAME)
print(f"Index status: {index.describe()}")

# COMMAND ----------

# Test similarity search
results = index.similarity_search(
    query_text="manufacturing facility deficiency oral tablet",
    columns=["NDA_ID", "drug_name", "dosage_form", "primary_deficiency_category", "deficiency_summary"],
    num_results=5,
)

display(results)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Next Steps
# MAGIC
# MAGIC The Vector Search index is ready. Now:
# MAGIC 1. Create a **Knowledge Assistant** in Agent Bricks pointing to this index
# MAGIC 2. Set up the **PubMed MCP** and **openFDA MCP** servers
# MAGIC 3. Wire everything together with the **Supervisor Agent**
# MAGIC
# MAGIC See the [Part 2 README](README.md) for detailed instructions.
