# Databricks notebook source

# MAGIC %md
# MAGIC # Step 1: PDF Preparation
# MAGIC
# MAGIC This notebook handles:
# MAGIC 1. Unzipping the FDA Complete Response Letters (CRLs) from the downloaded zip file
# MAGIC 2. Parsing PDFs into structured text using `ai_parse_document()`
# MAGIC 3. Creating a bronze table with parsed letter content
# MAGIC 4. Running the KIE (Key Information Extraction) endpoint against parsed text
# MAGIC
# MAGIC ### Prerequisites
# MAGIC - Upload `ApprovedCRLs_NDA_BLA_2020-2024.zip` to a Unity Catalog Volume
# MAGIC - Serverless compute enabled
# MAGIC - `ai_parse_document()` available (Mosaic AI)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.1 Unzip the FDA CRL PDFs

# COMMAND ----------

import zipfile
import os

# UPDATE THIS PATH to match your Unity Catalog volume location
zip_path = "/Volumes/<catalog>/<schema>/<volume>/ApprovedCRLs_NDA_BLA_2020-2024.zip"
extract_dir = os.path.dirname(zip_path)

with zipfile.ZipFile(zip_path, 'r') as zip_ref:
    zip_ref.extractall(extract_dir)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.2 Verify extracted files

# COMMAND ----------

# List extracted PDF files
dbutils.fs.ls(f'/Volumes/<catalog>/<schema>/<volume>/ApprovedCRLs_NDA_BLA_2020-2024/')

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.3 Parse PDFs with `ai_parse_document()`
# MAGIC
# MAGIC This uses Databricks' built-in `ai_parse_document()` function to convert PDF content into structured markdown text.
# MAGIC You can test with a small batch first (LIMIT 10) before processing all documents.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Test with a small batch first
# MAGIC CREATE OR REPLACE TABLE <catalog>.<schema>.parsed_letters_raw AS
# MAGIC SELECT
# MAGIC   path,
# MAGIC   ai_parse_document(content) AS parsed_doc
# MAGIC FROM READ_FILES('/Volumes/<catalog>/<schema>/<volume>/ApprovedCRLs_NDA_BLA_2020-2024/*.pdf', format => 'binaryFile')
# MAGIC LIMIT 10

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Preview parsed results (VARIANT columns require explicit cast)
# MAGIC SELECT path, parsed_doc::STRING AS parsed_doc FROM <catalog>.<schema>.parsed_letters_raw

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.4 Extract text from parsed document elements

# COMMAND ----------

# MAGIC %sql
# MAGIC -- View the extracted text content from parsed documents
# MAGIC SELECT
# MAGIC   path,
# MAGIC   concat_ws(
# MAGIC     '\n\n',
# MAGIC     transform(
# MAGIC       try_cast(parsed_doc:document:elements AS ARRAY<VARIANT>),
# MAGIC       e -> try_cast(e:content AS STRING)
# MAGIC     )
# MAGIC   ) AS text
# MAGIC FROM <catalog>.<schema>.parsed_letters_raw

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.5 Create the full parsed letters table (all documents)
# MAGIC
# MAGIC This processes ALL PDFs and creates a clean table with path, modification time, parsed content, and extracted text.

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE OR REPLACE TABLE <catalog>.<schema>.parsed_letters AS
# MAGIC WITH src AS (
# MAGIC   SELECT
# MAGIC     path,
# MAGIC     modificationTime,
# MAGIC     ai_parse_document(content) AS parsed_doc
# MAGIC   FROM READ_FILES('/Volumes/<catalog>/<schema>/<volume>/ApprovedCRLs_NDA_BLA_2020-2024/*.pdf', format => 'binaryFile')
# MAGIC )
# MAGIC SELECT
# MAGIC   path,
# MAGIC   modificationTime,
# MAGIC   parsed_doc AS parsed_content,
# MAGIC   concat_ws(
# MAGIC     '\n\n',
# MAGIC     transform(
# MAGIC       try_cast(parsed_doc:document:elements AS ARRAY<VARIANT>),
# MAGIC       e -> try_cast(e:content AS STRING)
# MAGIC     )
# MAGIC   ) AS text
# MAGIC FROM src;
# MAGIC
# MAGIC SELECT path, modificationTime, parsed_content::STRING AS parsed_content, text FROM <catalog>.<schema>.parsed_letters;

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1.6 (Optional) Run KIE endpoint against parsed text
# MAGIC
# MAGIC After deploying the KIE agent in Step 2 & 3, you can run extraction in a single query:

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Only run this after deploying the KIE endpoint (see Notebook 03)
# MAGIC -- CREATE OR REPLACE TABLE <catalog>.<schema>.structured_insights AS
# MAGIC -- SELECT
# MAGIC --   path,
# MAGIC --   ai_query(
# MAGIC --     '<your-kie-endpoint-name>',
# MAGIC --     text
# MAGIC --   ) AS extracted_data
# MAGIC -- FROM
# MAGIC --   <catalog>.<schema>.parsed_letters;
