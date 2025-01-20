# actions.py
import psycopg2
from datetime import datetime, timedelta, date
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

class ActionGetAverageDownloadSpeed(Action):
    def name(self) -> Text:
        return "action_get_average_download_speed"

    def validate_cell_id_format(self, cell_id: str) -> bool:
        """Validate if the cell ID matches the expected format."""
        import re
        pattern = r'^[A-Z]{2}[0-9]{5}_[0-9]_[0-9]$'
        return bool(re.match(pattern, cell_id))
    
    

    def check_cell_exists(self, cursor, cell_id: str) -> bool:
        """Check if the cell ID exists in the database."""
        query = """
            SELECT EXISTS (
                SELECT 1 
                FROM public.cell_data 
                WHERE cell_id = %s
                LIMIT 1
            )
        """
        cursor.execute(query, (cell_id,))
        return cursor.fetchone()[0]

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        # Extract cell_id from the entity
        cell_id = next(
            (e["value"] for e in tracker.latest_message["entities"] 
             if e["entity"] == "cell_id"),
            None
        )

        if not cell_id:
            dispatcher.utter_message(
                text="I couldn't identify the cell ID. Please provide it in the format 'CP#####_#_#' (for example: CP80091_3_1)."
            )
            return []

        # Validate cell ID format
        if not self.validate_cell_id_format(cell_id):
            dispatcher.utter_message(
                text=f"'{cell_id}' is not a valid cell ID format. Please use the format 'CP#####_#_#' (for example: CP80091_3_1)."
            )
            return [SlotSet("cell_id", None)]

        try:
            # Connect to PostgreSQL
            connection = psycopg2.connect(
                host="localhost",
                database="chatbot_gis",
                user="rasa_user",
                password="123456"
            )
            cursor = connection.cursor()

            # First check if the cell exists in the database
            if not self.check_cell_exists(cursor, cell_id):
                dispatcher.utter_message(
                    text=f"Cell ID '{cell_id}' does not exist in our database. Please check the cell ID and try again."
                )
                return [SlotSet("cell_id", None)]

            # Set the fixed date range for your data
            end_date = date(2024, 10, 17)  # October 17, 2023
            start_date = date(2024, 10, 7)  # October 7, 2023

            # Get the average download speed
            query = """
                SELECT 
                    COALESCE(AVG(download_speed), 0) as avg_speed,
                    COUNT(*) as record_count,
                    MIN(download_speed) as min_speed,
                    MAX(download_speed) as max_speed
                FROM public.cell_data
                WHERE cell_id = %s 
                AND date BETWEEN %s AND %s
            """
            cursor.execute(query, (cell_id, start_date, end_date))
            result = cursor.fetchone()
            avg_speed, record_count, min_speed, max_speed = result

            if record_count > 0:
                response = (
                    f"Here's the download speed analysis for cell {cell_id} for the period {start_date.strftime('%d/%m')} - {end_date.strftime('%d/%m')}:\n"
                    f"• Average speed: {avg_speed:.2f} Mbps\n"
                    f"• Lowest speed: {min_speed:.2f} Mbps\n"
                    f"• Highest speed: {max_speed:.2f} Mbps\n"
                    f"(Based on {record_count} measurements)"
                )
            else:
                response = (
                    f"The cell {cell_id} exists in our database, but there is no download speed data "
                    f"available for the period {start_date.strftime('%d/%m')} - {end_date.strftime('%d/%m')}."
                )

            dispatcher.utter_message(text=response)

        except psycopg2.Error as e:
            dispatcher.utter_message(
                text="I encountered a database error. Please try again later."
            )
            print(f"Database error: {str(e)}")

        finally:
            if 'connection' in locals():
                cursor.close()
                connection.close()

        return [SlotSet("cell_id", None)]