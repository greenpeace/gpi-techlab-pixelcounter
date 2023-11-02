import system.tracking
import logging
from datetime import datetime
import time
# Get Logging
import logging

# Get BigQuery
import system.bigquery
# Flask
from flask import request, session
# Import project id
from system.setenv import project_id
from system.getsecret import getsecrets
# Import date and time
from system.date import datenow

# Get the secret for dataset
dataset_id = getsecrets("tracking_stats_dataset_id",project_id)
# Get the secret for table
table_id = getsecrets("tracking_stats_table_id",project_id)

def track_visitor():
    if not system.tracking.is_tracking_allowed():
        logging.info("Tracking is not allowed")
        return
    else:
        try:            
            # Create list for BigQuery save
            trackingstats_bq = []
            # Create BQ json string
            trackingstats_bq.append({
                'date': datenow(),
                'host': request.host if request.host else '',
                'host_url': request.host_url if request.host_url else '',
                'ip_address': request.remote_addr if request.remote_addr else '',
                'requested_url': request.url if request.url else '',
                'referer_page': request.referrer if request.referrer else '',
                'schema': request.scheme if request.scheme else '',
                'routing_exception': request.routing_exception if request.routing_exception else '',
                'origin': request.origin if request.origin else '',
                'method': request.method if request.method else '',
                'full_path': request.full_path if request.full_path else '',
                'user_agent': request.headers.get('User-Agent') if request.headers.get('User-Agent') else '',
                'language': request.headers.get('Accept-Language') if request.headers.get('Accept-Language') else '',
                'user_agent_language': request.user_agent.language if request.user_agent.language else '',
                'browser': request.user_agent.browser if request.user_agent.browser else '',
                'platform': request.user_agent.platform if request.user_agent.platform else '',
                'version': request.user_agent.version if request.user_agent.version else '',
                'user_agent_string': request.user_agent.string if request.user_agent.string else '',
                'page_name': request.path if request.path else '',
                'query_string': request.query_string if request.query_string else ''
            })

            try:
                if system.bigquery.exist_dataset_table(table_id, dataset_id, project_id, system.bigquery.schema_trackingstats):
                    system.bigquery.insert_rows_bq(table_id, dataset_id, project_id, trackingstats_bq)
                                
                logging.info('{{"Info: request response time in hh:mm:ss {} ."}}'.format(time.strftime("%H:%M:%S", time.gmtime(time.time()))))
                print('{{"Info: request response time in hh:mm:ss {} ."}}'.format(time.strftime("%H:%M:%S", time.gmtime(time.time()))))
                # Slack Notification
                payload = '{{"text":"request response time in hh:mm:ss {} ."}}'.format(time.strftime("%H:%M:%S", time.gmtime(time.time())))
            except:
                logging.error('{{"Error: Writing data to BigQuery - request response time in hh:mm:ss {} ."}}'.format(time.strftime("%H:%M:%S", time.gmtime(time.time()))))
            
            return
        except Exception as e:
            logging.error("Error Tracking Data", e)
            return