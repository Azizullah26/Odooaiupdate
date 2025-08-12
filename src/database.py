import os
import logging
from datetime import datetime, date
from typing import Dict, List, Optional
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func


logger = logging.getLogger(__name__)

Base = declarative_base()


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(Integer, primary_key=True)
    # Use the same format you create in main_app.py: str(uuid.uuid4()) → 36 chars
    session_id = Column(String(36), unique=True, index=True, nullable=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_activity = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    total_queries = Column(Integer, default=0, nullable=False)
    odoo_connected = Column(Boolean, default=False, nullable=False)
    ai_service = Column(String(50))


class QueryLog(Base):
    __tablename__ = "query_logs"

    id = Column(Integer, primary_key=True)
    # Index + (optional) FK to the unique session_id in user_sessions
    session_id = Column(
        String(36),
        ForeignKey("user_sessions.session_id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    user_query = Column(Text, nullable=False)
    query_type = Column(String(64))  # intent or type label

    # Flexible blobs
    parsed_query = Column(JSONB, default=dict)   # NLP parse dict
    odoo_result = Column(JSONB, default=dict)    # raw Odoo payload

    response_text = Column(Text)                 # final string sent to user
    success = Column(Boolean, default=False, nullable=False)
    processing_time_ms = Column(Integer, default=0, nullable=False)
    error_message = Column(Text)

    created_at = Column(DateTime, server_default=func.now(), index=True, nullable=False)


class SystemMetrics(Base):
    """Table to store system performance metrics."""
    __tablename__ = 'system_metrics'

    id = Column(Integer, primary_key=True)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(String(500))
    timestamp = Column(DateTime, default=datetime.utcnow)
    category = Column(String(50))


class DatabaseManager:
    """Manages database connections and operations."""

    def __init__(self):
        """Initialize database connection."""
        self.database_url = os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable not set")

        self.engine = create_engine(
            self.database_url,
            pool_pre_ping=True,
            pool_size=3,
            max_overflow=3,
        )
        self.SessionLocal = sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=self.engine)

        # Create tables
        self.create_tables()
        logger.info("Database manager initialized successfully")

    def create_tables(self):
        """Create database tables if they don't exist."""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created/verified")
        except Exception as e:
            logger.error(f"Failed to create tables: {str(e)}")
            raise

    def get_session(self):
        """Get a database session."""
        return self.SessionLocal()

    def log_query(self, id: int, session_id: str,
                  query: str,
                  query_type: str,
                  response: str,
                  user_session: str,
                  timestamp: date,
                  success: bool = True,
                  error_message: str | None = None,
                  processing_time: int | None = None):
        """Log a user query and response."""
        session = self.get_session()
        try:
            query_log = QueryLog(id=id, session_id=session_id,
                                query=query,
                                 query_type=query_type,
                                 response=response,
                                 user_session=user_session,
                                 timestamp = timestamp,
                                 success=success,
                                 error_message=error_message,
                                 processing_time=processing_time)
            session.add(query_log)
            session.commit()
            logger.info(f"Query logged: {query_type}")
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Failed to log query: {str(e)}")
        finally:
            session.close()

    def update_user_session(self,
                            session_id: str,
                            odoo_connected: bool = False,
                            ai_service: str = "DeepSeek"):
        """Update or create user session."""
        session = self.get_session()
        try:
            user_session = session.query(UserSession).filter_by(
                session_id=session_id).first()

            if user_session:
                user_session.last_activity = datetime.utcnow()  # type: ignore
                user_session.total_queries = user_session.total_queries + 1  # type: ignore
                user_session.odoo_connected = odoo_connected  # type: ignore
                user_session.ai_service = ai_service  # type: ignore
                
            else:
                user_session = UserSession(session_id=session_id,
                                           total_queries=1,
                                           odoo_connected=odoo_connected,
                                           ai_service=ai_service)
                session.add(user_session)

            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Failed to update user session: {str(e)}")
        finally:
            session.close()

    def log_system_metric(self,
                          metric_name: str,
                          metric_value: str,
                          category: str = "general"):
        """Log system performance metrics."""
        session = self.get_session()
        try:
            metric = SystemMetrics(metric_name=metric_name,
                                   metric_value=metric_value,
                                   category=category)
            session.add(metric)
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Failed to log metric: {str(e)}")
        finally:
            session.close()

    def get_query_analytics(self, days: int = 7) -> Dict:
        """Get query analytics for the last N days."""
        session = self.get_session()
        try:
            from datetime import timedelta
            since_date = datetime.utcnow() - timedelta(days=days)

            queries = session.query(QueryLog).filter(
                QueryLog.timestamp >= since_date).all()

            analytics = {
                'total_queries': len(queries),
                'successful_queries': len([q for q in queries if q.success is True]),
                'failed_queries': len([q for q in queries if q.success is False]),
                'query_types': {},
                'avg_processing_time': 0
            }

            # Calculate query type distribution
            for query in queries:
                query_type = query.query_type or 'unknown'
                analytics[
                    'query_types'][query_type] = analytics['query_types'].get(
                        query_type, 0) + 1

            # Calculate average processing time
            processing_times = [
                q.processing_time for q in queries if q.processing_time is not None
            ]
            if processing_times:
                analytics['avg_processing_time'] = sum(processing_times) / len(
                    processing_times)

            return analytics
        except SQLAlchemyError as e:
            logger.error(f"Failed to get analytics: {str(e)}")
            return {}
        finally:
            session.close()

    def get_popular_queries(self, limit: int = 10) -> List[Dict]:
        """Get most popular query patterns."""
        session = self.get_session()
        try:
            from sqlalchemy import func

            popular = session.query(
                QueryLog.query_type,
                func.count(QueryLog.id).label('count')).group_by(
                    QueryLog.query_type).order_by(
                        func.count(QueryLog.id).desc()).limit(limit).all()

            return [{
                'query_type': item[0],
                'count': item[1]
            } for item in popular]
        except SQLAlchemyError as e:
            logger.error(f"Failed to get popular queries: {str(e)}")
            return []
        finally:
            session.close()

    def test_connection(self) -> bool:
        """Test database connection."""
        try:
            session = self.get_session()
            session.execute("SELECT 1")  # type: ignore
            session.close()
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {str(e)}")
            print("DB ERROR:", e)
            return False
