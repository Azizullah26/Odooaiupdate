import requests
import re

#from sqlalchemy.processors import to_str

class RasaNLPProcessor:
    def __init__(self, rasa_url="http://localhost:5005/model/parse"):
        
        self.rasa_url = rasa_url
        self.service_name = "RasaNLP"

    def test_connection(self) -> bool:
        try:
            response = requests.get("http://localhost:5005")
            return response.status_code == 200
        except:
            return False

    def find_WO_id(text):
        match = re.search(r'(?:project\s*id|wo\s*number|work\s*order\s*number|wo)\s*(\d+)', text)
        if not match:
            match = re.search(r'id\s*(\d+)', text)
        return match.group(1) if match else None

    def parse_query(self, query: str) -> dict:
        try:
            
            response = requests.post(self.rasa_url, json={"text": query})
            data = response.json()

            #gets the top intent and if its confidence is less that 0.8 is it assigned as unknown
            top_intent = data.get('intent', {})
            intent_name = top_intent.get('name', 'unknown')
            confidence = top_intent.get('confidence', 0.0)

            if confidence < 0.80:
                intent_name = "unknown"

            entities = {e['entity']: e['value'] for e in data.get('entities', [])}
            return {
                "intent": intent_name,
                "entities": entities,                 # ✅ new: keep as dict
                "original_query": query
            }
        except Exception as e:
            return {
                "intent": "unknown",
                "entities": [],
                "original_query": query,
                "error": str(e)
            }

    def generate_response(self, parsed_query, query_result):
        if not query_result or not query_result.get('success'):
            return query_result.get('error', "No results found.")

        data = query_result.get('data', {})
        header = data.get('project_header', {})
        pos    = data.get('purchase_orders', [])
        exp    = data.get('petty_cash', 0.0)
        ts     = data.get('timesheet_hours', 0.0)

        # Build a little report
        lines = [
            f"Project: {header.get('name')} (ID {header.get('id')})",
            f"  Created: {header.get('create_date')} by {header.get('create_uid')}",
            f"  WO Amount: {header.get('wo_amount')} for client {header.get('client_name')}",
            "",
            "Purchase Orders:"
        ]

        if not pos:
            lines.append("  – None found")
        else:
            for po in pos:
                lines.append(f"  • (ID {po['order_id']}) – Total: {po['price_total']}")


        lines += [
        "",
        f"Petty Cash Total (DONE): {exp:.2f}",
        "",
        f"Total Timesheet Amount: {ts:.2f}",
        ""
        ]

        return lines