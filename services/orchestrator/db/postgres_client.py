"""
PostgreSQL client for Intent Detection Agents
Replaces Neo4j + Qdrant with a single relational database
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager

try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
except ImportError:
    raise ImportError(
        "psycopg2-binary is required. Install with: pip install psycopg2-binary"
    )

from services.classifier.classifier_types import ClassifiedSignal, FitScore

# Logging
logger = logging.getLogger("postgres_client")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Database configuration
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_KAO6Lsh7YlWN@ep-mute-dust-ahzf2sw4-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
)

# Connection pool
_connection_pool = None


def get_connection_pool():
    """Get or create connection pool"""
    global _connection_pool
    if _connection_pool is None:
        try:
            _connection_pool = pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=DATABASE_URL
            )
            logger.info(f"✅ PostgreSQL connection pool created: {DATABASE_URL.split('@')[-1]}")
        except Exception as e:
            logger.error(f"❌ Failed to create connection pool: {e}")
            raise
    return _connection_pool


@contextmanager
def get_connection():
    """Context manager for database connections"""
    conn_pool = get_connection_pool()
    conn = conn_pool.getconn()
    try:
        yield conn
    finally:
        conn_pool.putconn(conn)


def init_database():
    """Create tables and indexes if they don't exist"""
    logger.info("🔧 Initializing PostgreSQL database schema...")

    with get_connection() as conn:
        cursor = conn.cursor()

        # Create companies table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                domain TEXT,
                industry TEXT,
                geo TEXT,
                fit_score REAL,
                fit_reasons JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create signals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id TEXT PRIMARY KEY,
                company_id TEXT NOT NULL,
                type TEXT,
                action TEXT,
                title TEXT,
                text TEXT,
                source TEXT,
                url TEXT,
                host TEXT,
                sentiment TEXT,
                confidence REAL,
                published_at TIMESTAMP,
                detected_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
            )
        """)

        # Create indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_signals_company_id ON signals(company_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_signals_published_at ON signals(published_at DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_companies_fit_score ON companies(fit_score DESC)
        """)

        conn.commit()
        logger.info("✅ Database schema initialized successfully")


# --- WRITE OPERATIONS ---

def merge_signals(signals: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Insert companies and signals from Perplexity web search
    Returns: {"companies": int, "signals": int}
    """
    if not signals:
        return {"companies": 0, "signals": 0}

    companies_created = 0
    signals_created = 0

    with get_connection() as conn:
        cursor = conn.cursor()

        for sig in signals:
            try:
                # Extract company info
                company_domain = sig.get("companyInfo", {}).get("companyDomain", "").strip()
                company_name = sig.get("companyInfo", {}).get("companyName", "").strip()

                # Extract signal info
                signal_id = sig.get("signalInfo", {}).get("signalId", "").strip()
                signal_type = sig.get("signalInfo", {}).get("type", "other")
                signal_action = sig.get("signalInfo", {}).get("action", "")
                signal_title = sig.get("signalInfo", {}).get("title", "")
                signal_snippet = sig.get("signalInfo", {}).get("snippet", "")
                signal_primary_time = sig.get("signalInfo", {}).get("primaryTime", "")
                signal_detected_at = sig.get("signalInfo", {}).get("detectedAt", datetime.utcnow().isoformat())

                # Extract source info
                source_url = sig.get("sourceInfo", {}).get("sourceUrl", "")
                source_type = sig.get("sourceInfo", {}).get("sourceType", "news")
                source_host = sig.get("sourceInfo", {}).get("host", "")

                # Extract enrichment info
                geo = sig.get("enrichmentInfo", {}).get("geo")
                industry = sig.get("enrichmentInfo", {}).get("industry")
                confidence = sig.get("enrichmentInfo", {}).get("confidence", 0.7)

                if not company_domain or not signal_id:
                    continue

                # Insert or update company
                cursor.execute("""
                    INSERT INTO companies (id, name, domain, industry, geo, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE SET
                        name = COALESCE(EXCLUDED.name, companies.name),
                        domain = COALESCE(EXCLUDED.domain, companies.domain),
                        industry = COALESCE(EXCLUDED.industry, companies.industry),
                        geo = COALESCE(EXCLUDED.geo, companies.geo),
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING (xmax = 0) AS is_new
                """, (company_domain, company_name, company_domain, industry, geo))

                result = cursor.fetchone()
                if result and result[0]:  # is_new = True
                    companies_created += 1

                # Insert signal (ignore if duplicate)
                cursor.execute("""
                    INSERT INTO signals
                    (id, company_id, type, action, title, text, source, url, host,
                     confidence, published_at, detected_at, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO NOTHING
                    RETURNING id
                """, (signal_id, company_domain, signal_type, signal_action, signal_title,
                      signal_snippet, source_type, source_url, source_host, confidence,
                      signal_primary_time or None, signal_detected_at))

                if cursor.fetchone():
                    signals_created += 1

            except Exception as e:
                logger.warning(f"Failed to process signal: {e}")
                continue

        conn.commit()

    logger.info(f"✅ Merged {companies_created} companies, {signals_created} signals")
    return {"companies": companies_created, "signals": signals_created}


def write_signal_classification(signal: ClassifiedSignal) -> None:
    """Update signal with classification results from OpenAI"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE signals
            SET type = %s, sentiment = %s, confidence = %s
            WHERE id = %s
        """, (signal.type, signal.sentiment, signal.confidence, signal.id))

        if cursor.rowcount == 0:
            logger.warning(f"No signal matched for id={signal.id} (classification not written)")
        else:
            logger.debug(f"Classified signal: {signal.id} -> {signal.type}")

        conn.commit()


def write_fit_score(score: FitScore) -> None:
    """Update company with fit score"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE companies
            SET fit_score = %s, fit_reasons = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (score.score, json.dumps(score.reasons), score.companyId))

        conn.commit()
        logger.info(f"✅ FitScore written: {score.companyId} -> {score.score:.2f}")


# --- READ OPERATIONS ---

def get_signal_text(signal_id: str) -> str:
    """Fetch signal text by ID for classification"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT text FROM signals WHERE id = %s", (signal_id,))
        row = cursor.fetchone()

        return row[0] if row else ""


def get_recent_signals(company_id: str, limit: int = 20) -> List[str]:
    """Get recent signal IDs for a company"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id FROM signals
            WHERE company_id = %s
            ORDER BY published_at DESC NULLS LAST, detected_at DESC
            LIMIT %s
        """, (company_id, limit))

        rows = cursor.fetchall()
        return [row[0] for row in rows]


def get_company_signal_stats(company_id: str) -> Dict[str, float]:
    """
    Get aggregated signal statistics for fit score calculation
    Returns signal counts by type and sentiment
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN type = 'hiring' THEN 1 ELSE 0 END) as hiring,
                SUM(CASE WHEN type = 'funding' THEN 1 ELSE 0 END) as funding,
                SUM(CASE WHEN type = 'tech' THEN 1 ELSE 0 END) as tech,
                SUM(CASE WHEN type = 'exec' THEN 1 ELSE 0 END) as exec_change,
                SUM(CASE WHEN type = 'launch' THEN 1 ELSE 0 END) as launch,
                SUM(CASE WHEN sentiment = 'pos' THEN 1 ELSE 0 END) as pos
            FROM signals
            WHERE company_id = %s AND type IS NOT NULL
        """, (company_id,))

        row = cursor.fetchone()

        if not row or row[0] == 0:
            return {
                "total": 0, "hiring": 0, "funding": 0,
                "tech": 0, "exec_change": 0, "launch": 0,
                "pos": 0, "sentimentPos": 0.0
            }

        total = row[0]
        pos = row[6]
        sentiment_pos = (pos / total) if total > 0 else 0.0

        return {
            "total": float(total),
            "hiring": float(row[1] or 0),
            "funding": float(row[2] or 0),
            "tech": float(row[3] or 0),
            "exec_change": float(row[4] or 0),
            "launch": float(row[5] or 0),
            "pos": float(pos or 0),
            "sentimentPos": float(sentiment_pos),
        }


def close():
    """Close connection pool"""
    global _connection_pool
    if _connection_pool:
        _connection_pool.closeall()
        logger.info("Closed PostgreSQL connection pool")
