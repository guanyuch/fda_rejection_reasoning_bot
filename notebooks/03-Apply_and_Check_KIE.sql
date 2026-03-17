-- Databricks notebook source

-- MAGIC %md
-- MAGIC # Step 3: Apply KIE & Build Gold Table
-- MAGIC
-- MAGIC This notebook:
-- MAGIC 1. Runs the deployed KIE agent endpoint against all parsed FDA letters
-- MAGIC 2. Flattens the extracted JSON into clean, queryable columns
-- MAGIC
-- MAGIC ### Prerequisites
-- MAGIC - Notebook 01 completed (parsed_letters table exists)
-- MAGIC - KIE Agent Brick deployed as a serverless endpoint (see Step 2 in README)
-- MAGIC - Update the endpoint name below to match your deployment
-- MAGIC
-- MAGIC **Widget Parameters:**
-- MAGIC - `SourceTableName`: e.g. `<catalog>.<schema>.parsed_letters`
-- MAGIC - `DestinationTableName`: e.g. `<catalog>.<schema>.structured_insights`

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 3.1 Test extraction on a small batch
-- MAGIC
-- MAGIC Run the KIE endpoint on 20 documents first to verify quality.

-- COMMAND ----------

-- Preview: test on 20 documents
WITH query_results AS (
  SELECT `text` AS input,
    ai_query(
      '<your-kie-endpoint-name>',  -- Replace with your deployed endpoint name
      input,
      failOnError => false
    ) AS response
  FROM (
    SELECT `text`
    FROM IDENTIFIER(:SourceTableName)
    LIMIT 20
  )
)
SELECT
  input,
  response.result::STRING AS response,
  response.errorMessage::STRING AS error
FROM query_results

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 3.2 Run extraction on all documents
-- MAGIC
-- MAGIC Once satisfied with the test results, run on the full dataset.

-- COMMAND ----------

CREATE OR REPLACE TABLE IDENTIFIER(:DestinationTableName) AS
WITH query_results AS (
  SELECT
    path,
    `text` AS input,
    ai_query(
      '<your-kie-endpoint-name>',  -- Replace with your deployed endpoint name
      input,
      failOnError => false
    ) AS response
  FROM (
    SELECT path, `text`
    FROM IDENTIFIER(:SourceTableName)
  )
)
SELECT
  path,
  input,
  response.result::STRING AS extracted_info,
  response.errorMessage::STRING AS error
FROM query_results

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 3.3 Verify extraction results

-- COMMAND ----------

SELECT path, extracted_info::STRING AS extracted_info, error FROM IDENTIFIER(:DestinationTableName)

-- COMMAND ----------

-- MAGIC %md
-- MAGIC ## 3.4 Gold Table — Flatten JSON into structured columns
-- MAGIC
-- MAGIC Extract each field from the KIE JSON output into individual columns
-- MAGIC for easy querying and analysis.

-- COMMAND ----------

SELECT
  extracted_info:NDA_ID::STRING AS NDA_ID,
  extracted_info:applicant::STRING AS applicant,
  extracted_info:application_number::STRING AS application_number,
  extracted_info:application_type::STRING AS application_type,
  extracted_info:carton_container_labeling_instructions::STRING AS carton_container_labeling_instructions,
  extracted_info:date_letter_reply::STRING AS date_letter_reply,
  extracted_info:date_original_submission::STRING AS date_original_submission,
  extracted_info:prescribing_information_instructions::STRING AS prescribing_information_instructions,
  extracted_info:primary_deficiency_category::STRING AS primary_deficiency_category,
  extracted_info:regulatory_context::STRING AS regulatory_context,
  extracted_info:resubmission_instructions::STRING AS resubmission_instructions,
  extracted_info:safety_update_instructions::STRING AS safety_update_instructions,
  extracted_info:drug_product.dosage_form::STRING AS dosage_form,
  extracted_info:drug_product.name::STRING AS drug_name,
  extracted_info:fda_letter_author.fda_letter_author_full_role::STRING AS fda_letter_author_full_role,
  extracted_info:fda_letter_author.fda_letter_author_title::STRING AS fda_letter_author_title,
  extracted_info:fda_rejection_citing::STRING AS fda_rejection_citing,
  extracted_info:deficiency_summary_paragraph::STRING AS deficiency_summary_paragraph
FROM
  IDENTIFIER(:DestinationTableName)
LIMIT 5
