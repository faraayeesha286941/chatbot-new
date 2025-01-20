import psycopg2
from datetime import datetime
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import re

class ActionHandleDownlinkUser(Action):
    def name(self) -> str:
        return "action_handle_downlink_user"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text="Please provide a valid Cell ID to proceed.")
        return [SlotSet("awaiting_cell_id", True)]

class ActionGetAverageDownloadSpeed(Action):
    def name(self) -> Text:
        return "action_get_average_download_speed"
    
    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Get the cell ID from the latest message
        cell_id = None
        for entity in tracker.latest_message.get('entities', []):
            if entity['entity'] == 'cell_id':
                cell_id = entity['value']
                break
        
        if not cell_id:
            # If no cell_id in entities, check if it's in the raw text
            message_text = tracker.latest_message.get('text', '')
            # Add your cell ID pattern matching logic here if needed
            
        if not cell_id:
            dispatcher.utter_message(text="Please provide a valid Cell ID to proceed.")
            return [SlotSet("awaiting_cell_id", True)]

        try:
            # Connect to PostgreSQL database
            connection = psycopg2.connect(
                host="localhost",
                database="chatbot_gis",
                user="rasa_user",
                password="123456"
            )
            cursor = connection.cursor()

            # Validate cell_id
            query_check = """SELECT EXISTS (SELECT 1 FROM public."OSS_data" WHERE "CELL_ID" = %s)"""
            cursor.execute(query_check, (cell_id,))
            if not cursor.fetchone()[0]:
                dispatcher.utter_message(text=f"Cell ID '{cell_id}' does not exist in the database.")
                return [SlotSet("awaiting_cell_id", False), SlotSet("cell_id", None)]

            # Rest of your existing database query code...
            start_date, end_date = datetime(2024, 10, 21), datetime(2024, 10, 27)
            query_data = """
                SELECT 
                    COALESCE(AVG("Avg. DL User Thp Mbps avg"), 0),
                    COUNT(*),
                    MIN("Avg. DL User Thp Mbps avg"),
                    MAX("Avg. DL User Thp Mbps avg")
                FROM public."OSS_data"
                WHERE "CELL_ID" = %s AND "PM_DATETIME" BETWEEN %s AND %s
            """
            cursor.execute(query_data, (cell_id, start_date, end_date))
            avg_speed, record_count, min_speed, max_speed = cursor.fetchone()

            if record_count > 0:
                response = (
                    f"Here's the downlink user analysis for Cell ID {cell_id} between "
                    f"{start_date.strftime('%d/%m')} and {end_date.strftime('%d/%m')}:\n"
                    f"• Average speed: {avg_speed:.2f} Mbps\n"
                    f"• Lowest speed: {min_speed:.2f} Mbps\n"
                    f"• Highest speed: {max_speed:.2f} Mbps\n"
                    f"(Based on {record_count} records)"
                )
                dispatcher.utter_message(text=response)
            else:
                dispatcher.utter_message(text="No data available for the specified date range.")

        except psycopg2.Error as e:
            dispatcher.utter_message(text="An error occurred while accessing the database. Please try again later.")
            print(f"Database error: {e}")
        finally:
            if 'connection' in locals():
                cursor.close()
                connection.close()

        return [SlotSet("awaiting_cell_id", False), SlotSet("cell_id", None)]

    def extract_cell_id(self, tracker: Tracker) -> Text:
        # Check for entity in the latest message
        entity_cell_id = next(
            (e["value"] for e in tracker.latest_message["entities"] if e["entity"] == "cell_id"),
            None
        )
        if entity_cell_id:
            return entity_cell_id

        # Extract Cell ID from text input
        message_text = tracker.latest_message['text']
        possible_prefixes = ['cell id:', 'cell id ', 'cell:', 'id:']
        for prefix in possible_prefixes:
            if prefix in message_text.lower():
                cell_id_match = re.search(r'[A-Z0-9]+[-_][A-Z0-9]+(?:[-_][A-Z0-9]+)*', message_text.lower().split(prefix.lower(), 1)[1])
                if cell_id_match:
                    return cell_id_match.group()

        return None


class ActionGetLowPRBUtilization(Action):
    def name(self) -> Text:
        return "action_get_low_prb_utilization"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Extract date from user message
        message_text = tracker.latest_message.get('text', '')
        date_match = re.search(r'\d{4}-\d{2}-\d{2}', message_text)
        if not date_match:
            dispatcher.utter_message(text="Please specify a valid date in YYYY-MM-DD format.")
            return []

        target_date = datetime.strptime(date_match.group(), '%Y-%m-%d').date()

        try:
            # Connect to PostgreSQL database
            connection = psycopg2.connect(
                host="localhost",
                database="chatbot_gis",
                user="rasa_user",
                password="123456"
            )
            cursor = connection.cursor()

            # Fetch cells with low PRB utilization
            low_prb_threshold = 20  # Define your threshold for "low"
            query = """
                SELECT "CELL_ID", "PRB Utilization avg"
                FROM public."OSS_data"
                WHERE "PM_DATETIME"::date = %s AND "PRB Utilization avg" < %s
                ORDER BY "PRB Utilization avg" ASC
                LIMIT 10
            """
            cursor.execute(query, (target_date, low_prb_threshold))
            results = cursor.fetchall()

            if results:
                CHUNK_SIZE = 5
                for i in range(0, len(results), CHUNK_SIZE):
                    chunk = results[i:i + CHUNK_SIZE]
                    response = "\n".join([f"• {row[0]}: {row[1]}%" for row in chunk])
                    dispatcher.utter_message(text=response)
                if len(results) >= 10:
                    dispatcher.utter_message(
                        text="(Only the first 10 results are shown. Please refine your query for more details.)"
                    )
            else:
                dispatcher.utter_message(text=f"No cells found with low PRB utilization on {target_date}.")

        except psycopg2.Error:
            dispatcher.utter_message(response="utter_database_error")
        finally:
            if 'connection' in locals():
                cursor.close()
                connection.close()

        return []
