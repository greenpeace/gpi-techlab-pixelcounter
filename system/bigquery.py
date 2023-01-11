
import logging
import time
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
# get bigquery client
bigquery_client = bigquery.Client()

# BigQuery Schema
schema_shortnerstats = [
    bigquery.SchemaField("date", "DATETIME"),
    bigquery.SchemaField("short", "STRING"),
    bigquery.SchemaField("docid", "STRING"),
    bigquery.SchemaField("host", "STRING"),
    bigquery.SchemaField("host_url", "STRING"),
    bigquery.SchemaField("ip_address", "STRING"),
    bigquery.SchemaField("requested_url", "STRING"),
    bigquery.SchemaField('referer_page', "STRING"),
    bigquery.SchemaField('schema', "STRING"),
    bigquery.SchemaField('routing_exception', "STRING"),
    bigquery.SchemaField('origin', "STRING"),
    bigquery.SchemaField("method", "STRING"),
    bigquery.SchemaField("full_path", "STRING"),
    bigquery.SchemaField("user_agent", "STRING"),
    bigquery.SchemaField("language", "STRING"),
    bigquery.SchemaField("user_agent_language", "STRING"),
    bigquery.SchemaField("browser", "STRING"),
    bigquery.SchemaField("platform", "STRING"),
    bigquery.SchemaField("version", "STRING"),
    bigquery.SchemaField("user_agent_string", "STRING"),
    bigquery.SchemaField("page_name", "STRING"),
    bigquery.SchemaField("query_string", "STRING"),
]

# BigQuery Schema
schema_trackingstats = [
    bigquery.SchemaField("date", "DATETIME"),
    bigquery.SchemaField("host", "STRING"),
    bigquery.SchemaField("host_url", "STRING"),
    bigquery.SchemaField("ip_address", "STRING"),
    bigquery.SchemaField("requested_url", "STRING"),
    bigquery.SchemaField('referer_page', "STRING"),
    bigquery.SchemaField('schema', "STRING"),
    bigquery.SchemaField('routing_exception', "STRING"),
    bigquery.SchemaField('origin', "STRING"),
    bigquery.SchemaField("method", "STRING"),
    bigquery.SchemaField("full_path", "STRING"),
    bigquery.SchemaField("user_agent", "STRING"),
    bigquery.SchemaField("language", "STRING"),
    bigquery.SchemaField("user_agent_language", "STRING"),
    bigquery.SchemaField("browser", "STRING"),
    bigquery.SchemaField("platform", "STRING"),
    bigquery.SchemaField("version", "STRING"),
    bigquery.SchemaField("user_agent_string", "STRING"),
    bigquery.SchemaField("page_name", "STRING"),
    bigquery.SchemaField("query_string", "STRING"),
]

def exist_dataset_table(table_id, dataset_id, project_id, schema):
    try:
        dataset_ref = "{}.{}".format(project_id, dataset_id)
        bigquery_client.get_dataset(dataset_ref)  # Make an API request.

    except NotFound:
        dataset_ref = "{}.{}".format(project_id, dataset_id)
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "EU"
        dataset = bigquery_client.create_dataset(dataset)  # Make an API request.
        logging.info("Created dataset {}.{}".format(bigquery_client.project, dataset.dataset_id))

    try:
        table_ref = "{}.{}.{}".format(project_id, dataset_id, table_id)
        bigquery_client.get_table(table_ref)  # Make an API request.

    except NotFound:

        table_ref = "{}.{}.{}".format(project_id, dataset_id, table_id)

        table = bigquery.Table(table_ref, schema=schema)

#        table.time_partitioning = bigquery.TimePartitioning(
#            type_=bigquery.TimePartitioningType.DAY,
#            field="date"
#        )
#        if clustering_fields is not None:
#            table.clustering_fields = clustering_fields
        try:
            table = bigquery_client.create_table(table)  # Make an API request.
            logging.info("Created table {}.{}.{}".format(table.project, table.dataset_id, table.table_id))
        except:
            logging.error('{{"Error: Writing data to BigQuery {} - request response time in hh:mm:ss {} ."}}'.format(table, time.strftime("%H:%M:%S", time.gmtime(time.time()))))

    return True


def insert_rows_bq(table_id, dataset_id, project_id, data):

    table_ref = "{}.{}.{}".format(project_id, dataset_id, table_id)
    table = bigquery_client.get_table(table_ref)

    resp = bigquery_client.insert_rows_json(
        json_rows = data,
        table = table_ref,
    )
    
    assert resp == []
    logging.info("Success uploaded to table {}".format(table.table_id))
    