import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import calendar
from database import DatabaseManager, QueryLog
from sqlalchemy.sql.expression import text

logger = logging.getLogger(__name__)

class QueryParser:
    """Parse natural language queries and execute them against the database."""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        logger.info("Initialized Query Parser")
    
    def execute_query(self, query_info: Dict[str, Any]) -> Any:
        query_type = query_info.get('query_type')
        keywords = query_info.get('keywords', [])
        try:
            if query_type == 'date':
                return self._execute_project_date_search(keywords)
            elif query_type == 'name':
                return self._execute_project_name_search(keywords)
            elif query_type == 'engineer':
                return self._execute_project_engineer_search(keywords)
            else:
                return "no query type"
        except Exception as e:
            logger.error(f"Query execution failed: {str(e)}")
            raise
    
    
    def _execute_count_query(self, query_info: Dict) -> Dict:
        session = self.db_manager.get_session()
        try:
            count = session.query(QueryLog).count()
            return {
                'type': 'count',
                'count': count,
                'filters': query_info
            }
        finally:
            session.close()
    
    
    def _execute_manager_query(self, query_info: Dict) -> Dict:
        session = self.db_manager.get_session()
        if not session:
            return {'type': 'manager', 'found': False, 'logs': [], 'filters': query_info}
        try:
            employee_name = query_info.get('employee_name')
            if not employee_name:
                raise ValueError("Employee name is required for manager queries")
            logs = session.query(QueryLog).filter(QueryLog.query.ilike(f"%{employee_name}%")).all()
            return {
                'type': 'manager',
                'found': bool(logs),
                'logs': [log.query for log in logs],
                'filters': query_info
            }
        finally:
            session.close()
    

    
    def _execute_search_query(self, query_info: Dict) -> Dict:
        session = self.db_manager.get_session()
        try:
            logs = session.query(QueryLog).all()
            return {
                'type': 'search',
                'results': [log.query for log in logs],
                'count': len(logs),
                'filters': query_info
            }
        finally:
            session.close()

    def _execute_project_date_search(self, keywords: list) -> dict:
        # expects keywords = [project_id, 'start'] or ['start', project_id]
        session = self.db_manager.get_session()
        try:
            project_id = None
            for k in keywords:
                if k.isdigit():
                    project_id = k
            if project_id:
                rows = session.execute(text('SELECT id, date_start FROM project_project WHERE id = :pid'), {'pid': project_id}).fetchall()
            else:
                rows = session.execute(text('SELECT id, date_start FROM project_project LIMIT 10')).fetchall()
            results = [dict(row._mapping) for row in rows]
            return {'type': 'project_date_search', 'results': results}
        finally:
            session.close()

    def _execute_project_name_search(self, keywords: list) -> dict:
        # expects keywords = [project_id, 'project'] or [engineer_id, 'project'] or [start_date, 'project']
        session = self.db_manager.get_session()
        try:
            project_id = None
            for k in keywords:
                if k.isdigit():
                    project_id = k
            if project_id:
                rows = session.execute(text('SELECT id, name FROM project_project WHERE id = :pid'), {'pid': project_id}).fetchall()
                #print(rows)
            else:
                rows = session.execute(text('SELECT id, name FROM project_project LIMIT 10')).fetchall()
            results = [dict(row._mapping) for row in rows]
            return {'type': 'project_name_search', 'results': results}
        finally:
            session.close()

    def _execute_project_engineer_search(self, keywords: list) -> dict:
        # expects keywords = [project_id, 'who']
        session = self.db_manager.get_session()
        try:
            project_id = None
            for k in keywords:
                if k.isdigit():
                    project_id = k
            if project_id:
                rows = session.execute(text('SELECT id, project_eng_id FROM project_project WHERE id = :pid'), {'pid': project_id}).fetchall()
                #print(rows)
            else:
                rows = session.execute(text('SELECT id, project_eng_id FROM project_project WHERE project_eng_id IS NOT NULL LIMIT 10')).fetchall()
            results = [dict(row._mapping) for row in rows]
            #print(results)
            return {'type': 'project_engineer_search', 'results': results}
        finally:
            session.close()
    
    def _build_domain(self, query_info: Dict) -> List:
        """Build Odoo domain from query information."""
        domain = [['active', '=', True]]
        
        # Add name filter
        if query_info.get('employee_name'):
            domain.append(['name', 'ilike', query_info['employee_name']])
        
        # Add date filters
        if query_info.get('date_from'):
            domain.append(['joining_date', '>=', query_info['date_from']])
        
        if query_info.get('date_to'):
            domain.append(['joining_date', '<=', query_info['date_to']])
        
        # Add additional filters
        additional_filters = query_info.get('additional_filters', {})
        for key, value in additional_filters.items():
            if key in ['gender', 'employee_type']:
                domain.append([key, '=', value])
            elif key in ['job_title']:
                domain.append([key, 'ilike', value])
        
        return domain
    
    def _parse_relative_date(self, date_string: str) -> Optional[str]:
        """Parse relative date strings to actual dates."""
        if not date_string:
            return None
        
        date_string = date_string.lower().strip()
        today = datetime.now().date()
        
        try:
            # Handle "after January 2023" type formats
            if 'january' in date_string and '2023' in date_string:
                return '2023-01-01'
            elif 'january' in date_string and '2024' in date_string:
                return '2024-01-01'
            
            # Handle "this month"
            if 'this month' in date_string:
                return today.replace(day=1).isoformat()
            
            # Handle "last month"
            if 'last month' in date_string:
                first_day_current = today.replace(day=1)
                last_month = first_day_current - timedelta(days=1)
                return last_month.replace(day=1).isoformat()
            
            # Handle "next month"
            if 'next month' in date_string:
                if today.month == 12:
                    return today.replace(year=today.year + 1, month=1, day=1).isoformat()
                else:
                    return today.replace(month=today.month + 1, day=1).isoformat()
            
            # Handle year patterns
            import re
            year_match = re.search(r'\b(20\d{2})\b', date_string)
            if year_match:
                year = int(year_match.group(1))
                if 'after' in date_string or 'since' in date_string:
                    return f'{year}-01-01'
                elif 'before' in date_string:
                    return f'{year-1}-12-31'
            
            # Try to parse as direct date
            if '-' in date_string and len(date_string) == 10:
                datetime.strptime(date_string, '%Y-%m-%d')
                return date_string
                
        except Exception as e:
            logger.warning(f"Could not parse date string '{date_string}': {str(e)}")
        
        return None
