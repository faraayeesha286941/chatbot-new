import psycopg2
from datetime import datetime
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
from collections import defaultdict
# from geopy.distance import geodesic
import re

class ActionHandleDownlinkUser(Action):
    def name(self) -> str:
        return "action_handle_downlink_user"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text="Please provide a valid Cell ID to proceed.")
        return [SlotSet("awaiting_cell_id", True)]
    
class ActionFindComplaintsNearby(Action):
    def name(self) -> Text:
        return "action_find_complaints_nearby"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        site_id = None

        # Extract entity
        for entity in tracker.latest_message.get('entities', []):
            if entity['entity'] == 'siteid':
                site_id = entity['value']
                break

        if not site_id:
            site_id = tracker.latest_message.get('text', '').strip()

        if not site_id:
            dispatcher.utter_message(text="Please provide a valid Site ID.")
            return []

        site_id = site_id.strip().upper()

        try:
            connection = psycopg2.connect(
                host="localhost",
                database="chatbot_gis",
                user="rasa_user",
                password="123456"
            )
            cursor = connection.cursor()

            query = """
                SELECT "Ticket ID", "Customer N", "Case Categ", dist
                FROM public.distance_by_site
                WHERE siteid ILIKE %s AND dist <= 500
                ORDER BY dist ASC
            """
            cursor.execute(query, (f"%{site_id}%",)) 

            complaints = cursor.fetchall()

            if complaints:
                msg = f"✅ Found {len(complaints)} complaints within 500m of Site {site_id}:\n\n"
                for ticket_id, customer, case_categ, distance in complaints:
                    msg += f"🎫 Ticket: {ticket_id}\n🙋 Customer: {customer}\n📂 Category: {case_categ}\n📏 Distance: {distance:.2f} km\n\n"
                dispatcher.utter_message(text=msg)
            else:
                dispatcher.utter_message(text=f"No complaints found within 500m for Site {site_id}.")

        except Exception as e:
            print(f"❌ Database Error: {e}")
            dispatcher.utter_message(text="An error occurred while fetching nearby complaints.")
        finally:
            if 'connection' in locals():
                cursor.close()
                connection.close()

        return []


class ActionCheckSectorCongestion(Action):
    def name(self) -> Text:
        return "action_check_sector_congestion"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        sector_id = tracker.get_slot("cell_ids")
        if not sector_id:
            dispatcher.utter_message(text="Please provide a valid Sector ID.")
            return []

        sector_id = sector_id.strip().upper()

        try:
            connection = psycopg2.connect(
                host="localhost",
                database="chatbot_gis",
                user="rasa_user",
                password="123456"
            )
            cursor = connection.cursor()

            query = """
                SELECT DISTINCT cell_name, prb_utilization_avg
                FROM public.load_balancing
                WHERE cell_name ILIKE %s
            """
            cursor.execute(query, (f"{sector_id}-%",))
            results = cursor.fetchall()

            if not results:
                dispatcher.utter_message(text=f"No PRB data found for sector {sector_id}.")
                return []

            from collections import defaultdict
            layer_stats = defaultdict(list)

            for cell_name, prb_util in results:
                layer_stats[cell_name].append(prb_util)

            total_layers = len(layer_stats)

            # Determine sectors based on last digit of layer suffix (e.g., 21 -> sector 1)
            sector_map = defaultdict(list)
            for cell_name in layer_stats:
                match = re.search(r"-(\d{2})$", cell_name)
                if match:
                    last_two_digits = int(match.group(1))
                    sector_num = last_two_digits % 10  # sector 1 from 21, 71, etc.
                    sector_map[sector_num].append(cell_name)

            total_sectors = len(sector_map)

            # Header summary
            response = (
                f"🔍 Sector Analysis for {sector_id}:\n"
                f"📊 Total Sectors: {total_sectors}\n"
                f"📋 Total Layers: {total_layers}\n\n"
            )

            # Show sector groupings
            for sector_num, layers in sorted(sector_map.items()):
                response += f"📡 Sector {sector_num}: {', '.join(sorted(layers))}\n"

            # PRB per layer and congestion status
            congested_layers = []
            response += "\n📈 PRB Utilization per Layer:\n"
            for cell_name, prb_list in layer_stats.items():
                avg_util = sum(prb_list) / len(prb_list)
                response += f"• Layer: {cell_name} → PRB Utilization: {avg_util:.0f}%\n"
                if avg_util >= 70:
                    congested_layers.append(cell_name)

            if congested_layers:
                response += "\n⚠️ Congested Layers:\n" + "\n".join(f"- {layer}" for layer in congested_layers)
            else:
                response += "\n✅ No congested layers detected."

            dispatcher.utter_message(text=response)

        except Exception as e:
            print("❌ ERROR:", e)
            dispatcher.utter_message(text="An error occurred while accessing the database.")
        finally:
            if 'connection' in locals():
                cursor.close()
                connection.close()

        return []


class ActionGetTicketInfo(Action):
    def name(self) -> Text:
        return "action_get_ticket_info"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        ticket_id = next((e["value"] for e in tracker.latest_message.get("entities", []) if e["entity"] == "ticket_id"), None)

        if not ticket_id:
            dispatcher.utter_message(text="Please provide a valid Ticket ID.")
            return []

        try:
            connection = psycopg2.connect(
                host="localhost",
                database="chatbot_gis",
                user="rasa_user",
                password="123456"
            )
            cursor = connection.cursor()

            # Query ticket info without coordinates
            query_ticket = """
                SELECT 
                    "Ticket ID", "Customer Name", "Case Category L1", "Case Category L2", "Case Category L3",
                    "Ticket Status", "Closed Reason", "Resolved Reason", "Resolution","[DAISY] Latitude", "[DAISY] Longitude"
                FROM public.network_complaint
                WHERE "Ticket ID" = %s
            """
            cursor.execute(query_ticket, (ticket_id,))
            ticket = cursor.fetchone()

            if not ticket:
                dispatcher.utter_message(text=f"❌ Ticket ID '{ticket_id}' not found.")
                return []

            (
                tid, customer, cat1, cat2, cat3, status,
                closed_reason, resolved_reason, resolution, latitude, longitude
            ) = ticket

            complaint_type = f"{cat1} > {cat2} > {cat3}"
            soln = " | ".join(filter(None, [closed_reason, resolved_reason, resolution]))

            msg = (
                f"🎫 Ticket ID       : {ticket_id}\n"
                f"🙋 Customer        : {customer}\n"
                f"📂 *Complaint Type : {complaint_type}\n"
                f"📌 Status          : {status}\n"
                f"✅ Solution        : {soln or 'Not provided'}\n"
            )

            if latitude is not None and longitude is not None:
               dispatcher.utter_message(text=msg,metadata={"ticket_location": {"ticket_id": ticket_id, "lat": float(latitude), "lon": float(longitude)}}
                )
            else:
                dispatcher.utter_message(text=msg)

        except psycopg2.Error as e:
            print(f"❌ Database Error: {e}")
            dispatcher.utter_message(text="Something went wrong when accessing the ticket info.")
        finally:
            if connection:
                cursor.close()
                connection.close()

        return []
    
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
        print("DEBUG >> latest_message:", tracker.latest_message)
        print("DEBUG >> extracted cell_id:", cell_id)    
        
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
            query_check = """SELECT EXISTS (SELECT 1 FROM public."OSS_data" WHERE "CELL_ID" ILIKE %s)"""
            cursor.execute(query_check, (cell_id,))
            if not cursor.fetchone()[0]:
                dispatcher.utter_message(text=f"Cell ID '{cell_id}' does not exist in the database.")
                return [SlotSet("awaiting_cell_id", False), SlotSet("cell_id", None)]

            # Rest of your existing database query code...
            start_date, end_date = datetime(2024, 9, 21), datetime(2025, 2, 28)
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
        """
        Extracts the cell ID from user input. Supports only new format (e.g., 2376A).
        """
        # Check if entity exists in the latest message
        entity_cell_id = next(
            (e["value"] for e in tracker.latest_message.get("entities", []) if e["entity"] == "cell_id"),
            None
        )
        if entity_cell_id:
            return entity_cell_id

        # Extract Cell ID from text input (New format: letters + numbers, 3+ characters)
        message_text = tracker.latest_message.get("text", "").strip()

        # New regex: Matches ONLY the new format (letters & numbers, min 3 characters)
        cell_id_match = re.search(r'\b[A-Z0-9]{3,}\b', message_text)

        if cell_id_match:
            return cell_id_match.group()

        return None


class ActionGetSiteSignalStats(Action):
    def name(self) -> Text:
        return "action_get_site_signal_stats"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        site_id = None

        # First, try extracting from entity
        for entity in tracker.latest_message.get('entities', []):
            if entity['entity'] == 'siteid':
                site_id = entity['value']
                break

        # If not found, try regex from text
        if not site_id:
            message_text = tracker.latest_message.get('text', '')
            match = re.search(r'\b[A-Z0-9_-]{4,}\b', message_text)
            if match:
                site_id = match.group()

        if not site_id:
            dispatcher.utter_message(text="Please provide a valid Site ID.")
            return []

        # Clean the input
        site_id = site_id.strip().upper()
        print("DEBUG >> cleaned site_id:", site_id)

        try:
            connection = psycopg2.connect(
                host="localhost",
                database="chatbot_gis",
                user="rasa_user",
                password="123456"
            )
            cursor = connection.cursor()

            # Validate siteid
            cursor.execute("SELECT EXISTS (SELECT 1 FROM public.ookla_kepong WHERE siteid ILIKE %s)", (site_id,))
            site_exists = cursor.fetchone()[0]
            print(f"DEBUG >> siteid {site_id} exists:", site_exists)

            if not site_exists:
                dispatcher.utter_message(text=f"Site ID '{site_id}' does not exist in the database.")
                return []

            # Query averages
            cursor.execute("""
                SELECT 
                    COALESCE(AVG(val_signal_rsrq_db), 0),
                    COALESCE(AVG(val_signal_rsrp_dbm), 0),
                    COUNT(*)
                FROM public.ookla_kepong
                WHERE siteid = %s
            """, (site_id,))
            avg_rsrq, avg_rsrp, count = cursor.fetchone()

            response = (
                f"Signal statistics for Site ID {site_id}:\n"
                f"• Average RSRQ: {avg_rsrq:.2f} dB\n"
                f"• Average RSRP: {avg_rsrp:.2f} dBm\n"
                f"(Based on {count} records)"
            )
            dispatcher.utter_message(text=response)

        except psycopg2.Error as e:
            dispatcher.utter_message(text="An error occurred while accessing the database.")
            print(f"Database error: {e}")
        finally:
            if 'connection' in locals():
                cursor.close()
                connection.close()

        return []




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
