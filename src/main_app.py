#!/usr/bin/env python3
"""
Main application for AI-Powered HR Query System
This system provides a chatbox interface for querying employee information from Odoo.
"""

import os
import sys
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
import uuid

# Import our custom modules
from rasa_nlp import RasaNLPProcessor
from odoo_client import OdooClient
from middleware import Middleware
import summary_report
from database import DatabaseManager


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('hr_chatbot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class HRChatbot:
    """
    Main chatbot class that integrates all components.
    """
    
    def __init__(self):
        """Initialize the HR chatbot with all components."""
        self.session_id = str(uuid.uuid4())
        self.start_time = datetime.utcnow()
        self.odoo_client = OdooClient()
        self.middleware = Middleware(self.odoo_client)
        self.db = DatabaseManager()   
        
        # Initialize components
        
        self.nlp_processor = RasaNLPProcessor()  # New Rasa-based NLP processor
        
        # Audit‐trail (uncomment / adjust to your DBManager choice)
        self.db_available = True


        # Test connections
        self._test_connections()
        
        logger.info(f"HR Chatbot initialized with session ID: {self.session_id}")
    
    def _test_connections(self):
        """Test all component connections."""
        logger.info("Testing component connections...")

        db_ok = self.odoo_client.test_connection()
        logger.info(f"Odoo Database: {'✓' if db_ok else '✗'}")
        
        # Test NLP processor
        nlp_ok = self.nlp_processor.test_connection()
        logger.info(f"NLP Processor: {'✓' if nlp_ok else '✗'}")
        
        return nlp_ok
    
    def process_query(self, user_input: str) -> Dict[str, Any]:
        """
        Process a user query through the complete pipeline.
        
        Args:
            user_input (str): User's natural language query
            
        Returns:
            Dict[str, Any]: Complete response with data and metadata
        """
        start_time = time.time()
        
        try:
            # Step 1: Parse the query using NLP
            logger.info(f"Processing query: {user_input}")
            parsed_query = self.nlp_processor.parse_query(user_input)
            print('Raw RasaNLP API response:', parsed_query)#for debugging
            
            # --- Middleware step 2 ---
            odoo_result = self.middleware.process(parsed_query)

            
            # Step 3: Calculate processing time
            processing_time = int((time.time() - start_time) * 1000)  # milliseconds
            
            result= {
                'success': odoo_result.get('success', True),
                'data': odoo_result.get('result'),
                'response': odoo_result.get('response'),
                'parsed_query': parsed_query,
                'processing_time': processing_time,
                'session_id': self.session_id
            }

            # --- Audit Trail ---
            self._log_query(
                user_input=user_input,
                parsed_query=parsed_query,
                query_result=odoo_result,
                response_text=result['response'],
                processing_time=processing_time,
                success=result['success']
            )

            return result
            
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}")
            processing_time = int((time.time() - start_time) * 1000)
            
            return {
                'success': False,
                'response': f"I apologize, but I encountered an error: {str(e)}",
                'error': str(e),
                'processing_time': processing_time,
                'session_id': self.session_id
            }


    def _log_query(self, user_input: str, parsed_query: Dict, query_result: Dict, 
                   response_text: str, processing_time: int, success: bool = True):
        """Log query to database."""
        try:
            if self.db:
                self.db.log_query(
                id=None,  # let DB autogen if primary key is autoincrement
                session_id=self.session_id,
                query=user_input,
                query_type=parsed_query.get('query_type', 'unknown'),
                response=response_text,
                user_session=self.session_id,
                timestamp=datetime.utcnow(),
                success=success,
                processing_time=processing_time
            )
                
                # Update session
                self.db.update_user_session(
                    session_id=self.session_id,
                    ai_service=self.nlp_processor.service_name
                )
        except Exception as e:
            logger.error(f"Failed to log query: {str(e)}")
    
    def get_analytics(self) -> Dict[str, Any]:
        """Get system analytics."""
        if not self.db_available:
            return {'error': 'Database not available'}
        
        try:
            if not self.db:
                return {'error': 'Database manager not available'}
                
            analytics = self.db.get_query_analytics(days=7)
            popular_queries = self.db.get_popular_queries(limit=5)
            
            return {
                'analytics': analytics,
                'popular_queries': popular_queries,
                'session_duration': (datetime.utcnow() - self.start_time).total_seconds()
            }
        except Exception as e:
            logger.error(f"Failed to get analytics: {str(e)}")
            return {'error': str(e)}
        return {'error': 'Database not available'}


def display_welcome_message():
    """Display welcome message and usage instructions."""
    print("\n" + "="*60)
    print("🤖 HR AI Assistant - Employee Information System")
    print("="*60)
    print("\nWelcome! I can help you find information about employees, projects, and managers.")
    print("\nCommands:")
    print("• 'analytics' - Show system usage statistics")
    print("• 'help' - Show this help message")
    print("• 'quit' or 'exit' - End the session")
    print("\n" + "="*60)


def display_analytics(chatbot: HRChatbot):
    """Display system analytics."""
    print("\n📊 System Analytics")
    print("-" * 30)
    
    analytics = chatbot.get_analytics()
    
    if 'error' in analytics:
        print(f"❌ Error: {analytics['error']}")
        return
    
    # Display query analytics
    if 'analytics' in analytics:
        stats = analytics['analytics']
        print(f"📈 Total Queries (7 days): {stats.get('total_queries', 0)}")
        print(f"✅ Successful: {stats.get('successful_queries', 0)}")
        print(f"❌ Failed: {stats.get('failed_queries', 0)}")
        print(f"⏱️  Avg Processing Time: {stats.get('avg_processing_time', 0):.0f}ms")
        
        # Display query types
        if stats.get('query_types'):
            print("\n🔍 Query Types:")
            for query_type, count in stats['query_types'].items():
                print(f"   • {query_type}: {count}")
    
    # Display popular queries
    if 'popular_queries' in analytics and analytics['popular_queries']:
        print("\n🔥 Popular Queries:")
        for query in analytics['popular_queries']:
            print(f"   • {query['query_type']}: {query['count']} times")
    
    # Display session info
    if 'session_duration' in analytics:
        duration = analytics['session_duration']
        print(f"\n⏰ Session Duration: {duration:.0f} seconds")


def main():
    """Main function to run the HR chatbot."""
    try:
        # Initialize the chatbot
        print("🚀 Initializing HR AI Assistant...")
        chatbot = HRChatbot()
        
        # Display welcome message
        display_welcome_message()
        
        print(f"\n💬 Session started. Type your query or 'help' for assistance.")
        print(f"Session ID: {chatbot.session_id[:8]}...")
        
        # Main chat loop
        while True:
            try:
                # Get user input
                user_input = input("\n👤 You: ").strip()
                
                # Handle special commands
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Thank you for using HR AI Assistant. Goodbye!")
                    break
                
                elif user_input.lower() == 'help':
                    display_welcome_message()
                    continue
                
                elif user_input.lower() == 'analytics':
                    display_analytics(chatbot)
                    continue
                
                elif not user_input:
                    continue
                
                # Process the query
                print("🤖 Assistant: Processing your query...")
                result = chatbot.process_query(user_input)
                
                # Display response
                if result['success']:
                    print(f"\n🤖 Assistant:\n")
                    print(result['response'])
                    
                else:
                    print(f"\n❌ Error: {result['response']}")
                
            except KeyboardInterrupt:
                print("\n\n👋 Session interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Unexpected error: {str(e)}")
                logger.error(f"Unexpected error in main loop: {str(e)}")
        
    except Exception as e:
        logger.error(f"Failed to initialize chatbot: {str(e)}")
        print(f"❌ Failed to initialize system: {str(e)}")
        print("Please check your configuration and try again.")
        return 1
    
    return 0


if __name__ == "__main__":
    # Run the main function
    exit_code = main()
    sys.exit(exit_code)
