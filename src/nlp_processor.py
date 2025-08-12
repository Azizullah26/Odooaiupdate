
import os
import json
import logging
from typing import Dict, List, Optional, Any
from openai import OpenAI
import re
import spacy

logger = logging.getLogger(__name__)

class NLPProcessor:
    """Simple keyword-based processor for HR queries."""
    def __init__(self):
        self.service_name = "KeywordModel"
        self.query_log = []  # Store (query, result) tuples
        os.environ["OPENAI_API_KEY"] = "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"

    def test_connection(self) -> bool:
        return True

    #edit this to use spaCy instead of OpenAI
    def parse_query(self, query: str) -> dict:
        """Parse the query using OpenAI as primary, fallback to rule-based logic if OpenAI fails."""
        # Try OpenAI NLP first
        try:
            openai_result = self._parse_query_openai(query)
            if openai_result:
                self.query_log.append({'query': query, 'result': openai_result.copy()})
                print("hi")
                return openai_result
        except Exception as e:
            logger.error(f"OpenAI NLP failed: {str(e)}")
        # Fallback to rule-based logic
        return self._parse_query_fallback(query)

    def _parse_query_openai(self, query: str) -> dict:
        """Use OpenAI to parse the query. Expects a JSON response with 'query_type' and 'keywords'."""
        client = OpenAI()
        system_prompt = (
            """
            You are an assistant that extracts structured query information from user input for an HR/project system.\n"
            "Given a user query, respond with a JSON object with the following fields:\n"
            "- query_type: (string) The type of query, e.g., 'date', 'engineer', 'name', 'search'.\n"
            "- keywords: (list) The main keywords or IDs extracted from the query.\n"
            "- original_query: (string) The original user query.\n"
            """
        )
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        content = response.choices[0].message.content
        
        if not content:
            raise ValueError("OpenAI response content is empty")
        result = json.loads(content)
        # Ensure required fields
        if 'original_query' not in result:
            result['original_query'] = query
        if 'query_type' not in result:
            result['query_type'] = 'search'
        if 'keywords' not in result:
            result['keywords'] = []
        return result

    def _parse_query_fallback(self, query: str) -> dict:
        """Rule-based query parsing. This is the logic i did as a first try."""
        import re
        q = query.lower()
        q = re.sub(r'[?.,!]', '', q)  # Remove punctuation
        result = {
            'query_type': 'search',
            'keywords': [],
            'original_query': query
        }

        def find_WO_id(text):
            match = re.search(r'(?:project\s*id|wo\s*number|work\s*order\s*number|wo)\s*(\d+)', text)
            if not match:
                match = re.search(r'id\s*(\d+)', text)
            return match.group(1) if match else None
        def find_engineer_id(text):
            match = re.search(r'engineer\s*id\s*(\d+)', text)
            return match.group(1) if match else None
        def find_start_date(text):
            match = re.search(r'start\s*date\s*([\w\-\/]+)', text)
            return match.group(1) if match else None

        wo_number = find_WO_id(q)
        engineer_id = find_engineer_id(q)
        start_date = find_start_date(q)

        try:
            # Rule 1: if when, start/started, look for WO number
            if 'when' in q and (('start' in q) or ('started' in q)) and wo_number:
                result['query_type'] = 'date'
                result['keywords'] = [wo_number, 'start']
                self.query_log.append({'query': query, 'result': result.copy()})
                return result

            # Rule 2: if who, look for WO number
            if 'who' in q and wo_number:
                result['query_type'] = 'engineer'
                result['keywords'] = [wo_number, 'who']
                self.query_log.append({'query': query, 'result': result.copy()})
                return result

            # Rule 3: if what, start/started, WO number
            if 'what' in q and (('start' in q) or ('started' in q)) and wo_number:
                result['query_type'] = 'date'
                result['keywords'] = ['start', wo_number]
                self.query_log.append({'query': query, 'result': result.copy()})
                return result

            # Rule 4: if what, engineer ID, project
            if 'what' in q and engineer_id and 'project' in q:
                result['query_type'] = 'name'
                result['keywords'] = [engineer_id, 'project']
                self.query_log.append({'query': query, 'result': result.copy()})
                return result

            # Rule 5: if what, start date, project
            if 'what' in q and start_date and 'project' in q:
                result['query_type'] = 'name'
                result['keywords'] = [start_date, 'project']
                self.query_log.append({'query': query, 'result': result.copy()})
                return result

            # Rule 6: if what, WO number, project
            if 'what' in q and wo_number and 'project' in q:
                result['query_type'] = 'name'
                result['keywords'] = [wo_number, 'project']
                self.query_log.append({'query': query, 'result': result.copy()})
                return result

        except Exception as e:
            print("Couldn't parse query")

        # If nothing matched, still log the default result
        self.query_log.append({'query': query, 'result': result.copy()})
        return result

    def get_query_log(self):
        """Return the log of all parsed queries and their results."""
        return self.query_log

    def generate_response(self, parsed_query, query_result):
        if not query_result or not query_result.get('results'):
            return "No results found."
        lines = []
        for row in query_result['results']:
            lines.append(str(row))

        #print(lines)
        return '\n'.join(lines)
    
    
    def clarify_ambiguous_query(self, query: str, context: Dict) -> str:
        """Generate clarification questions for ambiguous queries."""
        
        system_prompt = """
        The user's query is ambiguous or unclear. Generate helpful clarification questions
        to better understand what they're looking for.
        
        Be specific and provide examples based on the available context.
        """
        
        user_prompt = f"""
        User query: "{query}"
        Context: {json.dumps(context, default=str)}
        
        Generate 2-3 clarification questions to help the user be more specific.
        """
        
        if not self.client or not self.model:
            return "Could you please be more specific about what employee information you're looking for?"
            
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=200
            )
            
            content = response.choices[0].message.content
            return content if content else "Could you please be more specific about what employee information you're looking for?"
        except Exception as e:
            logger.error(f"Failed to generate clarification: {str(e)}")
            return "Could you please be more specific about what employee information you're looking for?"
    
    def _get_fallback_response(self, query: str) -> Dict[str, Any]:
        """Return a fallback response when AI service is not available."""
        return {
            "query_type": "search",
            "employee_name": None,
            "department": None,
            "date_from": None,
            "date_to": None,
            "fields_requested": [],
            "additional_filters": {},
            "intent_confidence": 0.0,
            "original_query": query,
            "error": "AI service not available"
        }
