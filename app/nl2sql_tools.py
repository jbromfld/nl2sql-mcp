"""
MCP Server Tools for NL2SQL

Two-phase approach:
1. nl2sql_prepare: Extract slots, check cache, fetch schema if needed
2. nl2sql_execute: Execute generated SQL and cache on success

Uses PostgreSQL for distributed caching across multiple developers.
"""

import json
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, List, Any, Optional
from datetime import datetime
from contextlib import contextmanager

# Import the slot filler (assuming it's in the same package)
from app.slot_filler import extract_slots, validate_slots, ExtractedSlots, TimeRange


class PostgreSQLCache:
    """PostgreSQL-backed cache for SQL queries (distributed-safe)"""
    
    def __init__(self, connection_string: str):
        """
        Args:
            connection_string: PostgreSQL connection string
                e.g., "postgresql://user:password@host:port/dbname"
        """
        self.connection_string = connection_string
        self._ensure_cache_table()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = psycopg2.connect(self.connection_string)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _ensure_cache_table(self):
        """Create cache table if it doesn't exist"""
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS nl2sql_cache (
                        cache_key VARCHAR(500) PRIMARY KEY,
                        sql_query TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        use_count INTEGER DEFAULT 1,
                        created_by VARCHAR(100),
                        metadata JSONB
                    )
                """)
                
                # Create index for faster lookups
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_nl2sql_cache_last_used 
                    ON nl2sql_cache(last_used)
                """)
    
    def get(self, key: str) -> Optional[str]:
        """Get SQL from cache and update usage statistics"""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    UPDATE nl2sql_cache 
                    SET last_used = CURRENT_TIMESTAMP,
                        use_count = use_count + 1
                    WHERE cache_key = %s
                    RETURNING sql_query
                """, (key,))
                
                result = cursor.fetchone()
                return result['sql_query'] if result else None
    
    def set(self, key: str, sql: str, created_by: Optional[str] = None, 
            metadata: Optional[Dict] = None):
        """Store SQL in cache with metadata"""
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO nl2sql_cache 
                        (cache_key, sql_query, created_by, metadata)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (cache_key) 
                    DO UPDATE SET 
                        sql_query = EXCLUDED.sql_query,
                        last_used = CURRENT_TIMESTAMP,
                        metadata = EXCLUDED.metadata
                """, (key, sql, created_by, json.dumps(metadata) if metadata else None))
    
    def delete(self, key: str) -> bool:
        """Delete a specific cache entry"""
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM nl2sql_cache WHERE cache_key = %s
                """, (key,))
                return cursor.rowcount > 0
    
    def clear_all(self):
        """Clear entire cache (use with caution!)"""
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM nl2sql_cache")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_entries,
                        SUM(use_count) as total_hits,
                        AVG(use_count) as avg_uses_per_query,
                        MAX(last_used) as last_cache_hit,
                        COUNT(DISTINCT created_by) as unique_users
                    FROM nl2sql_cache
                """)
                stats = cursor.fetchone()
                
                # Get top cached queries
                cursor.execute("""
                    SELECT cache_key, use_count, last_used
                    FROM nl2sql_cache
                    ORDER BY use_count DESC
                    LIMIT 10
                """)
                top_queries = cursor.fetchall()
                
                return {
                    **dict(stats),
                    "top_queries": [dict(q) for q in top_queries]
                }
    
    def list_keys(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List cached keys with metadata"""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT cache_key, created_at, last_used, use_count, created_by
                    FROM nl2sql_cache
                    ORDER BY last_used DESC
                    LIMIT %s
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]
    
    def cleanup_old_entries(self, days_old: int = 90):
        """Remove cache entries not used in N days"""
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM nl2sql_cache
                    WHERE last_used < CURRENT_TIMESTAMP - INTERVAL '%s days'
                """, (days_old,))
                return cursor.rowcount


class SchemaFetcher:
    """Fetch database schema information from PostgreSQL"""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = psycopg2.connect(self.connection_string)
        try:
            yield conn
        finally:
            conn.close()
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get comprehensive table information"""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                # Get column information from information_schema
                cursor.execute("""
                    SELECT 
                        column_name,
                        data_type,
                        is_nullable,
                        column_default
                    FROM information_schema.columns
                    WHERE table_name = %s
                    ORDER BY ordinal_position
                """, (table_name,))
                
                columns = [
                    {
                        "name": row["column_name"],
                        "type": row["data_type"],
                        "nullable": row["is_nullable"] == "YES",
                        "default": row["column_default"]
                    }
                    for row in cursor.fetchall()
                ]
                
                if not columns:
                    raise ValueError(f"Table '{table_name}' not found")
                
                # Get sample values for key columns
                sample_data = self._get_sample_values(table_name, cursor)
                
                return {
                    "table_name": table_name,
                    "columns": columns,
                    "sample_data": sample_data
                }
    
    def _get_sample_values(self, table_name: str, cursor) -> Dict[str, List[Any]]:
        """Get sample values for important columns"""
        key_columns = ["app_name", "deploy_env", "app_version"]
        samples = {}
        
        for col in key_columns:
            try:
                cursor.execute(f"""
                    SELECT DISTINCT {col} 
                    FROM {table_name} 
                    WHERE {col} IS NOT NULL 
                    LIMIT 10
                """)
                samples[col] = [row[col] for row in cursor.fetchall()]
            except psycopg2.Error:
                # Column doesn't exist in this table
                continue
        
        return samples
    
    def get_available_tables(self) -> List[str]:
        """Get list of all available tables"""
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """)
                return [row[0] for row in cursor.fetchall()]


class SQLExecutor:
    """Execute SQL queries safely on PostgreSQL"""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = psycopg2.connect(self.connection_string)
        try:
            yield conn
        finally:
            conn.close()
    
    def execute(self, sql: str) -> Dict[str, Any]:
        """Execute SQL and return results"""
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    # Execute query
                    cursor.execute(sql)
                    
                    # Fetch results (if SELECT query)
                    if cursor.description:
                        rows = cursor.fetchall()
                        results = [dict(row) for row in rows]
                    else:
                        results = []
                    
                    return {
                        "success": True,
                        "results": results,
                        "row_count": len(results)
                    }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }


class NL2SQLTools:
    """MCP tools for NL2SQL functionality with distributed PostgreSQL caching"""
    
    def __init__(self, db_connection_string: str, user_id: Optional[str] = None):
        """
        Args:
            db_connection_string: PostgreSQL connection string
            user_id: Identifier for the current user (for cache attribution)
        """
        self.cache = PostgreSQLCache(db_connection_string)
        self.schema_fetcher = SchemaFetcher(db_connection_string)
        self.executor = SQLExecutor(db_connection_string)
        self.user_id = user_id or "unknown"
        
        # Get known apps for better slot extraction
        self.known_apps = self._get_known_apps()
    
    def _get_known_apps(self) -> List[str]:
        """Get list of known apps from database"""
        try:
            result = self.executor.execute("""
                SELECT DISTINCT app_name 
                FROM deployment_data 
                WHERE app_name IS NOT NULL
                UNION
                SELECT DISTINCT app_name 
                FROM test_data 
                WHERE app_name IS NOT NULL
            """)
            if result["success"]:
                return [row["app_name"] for row in result["results"]]
        except Exception:
            pass
        return []
    
    def nl2sql_prepare(self, query: str) -> Dict[str, Any]:
        """
        Phase 1: Extract slots, check cache, prepare for SQL generation
        
        This tool ALWAYS runs first and handles:
        - Slot extraction
        - Cache lookup (distributed across all users)
        - Schema fetching (if cache miss)
        
        Returns either:
        - Direct results (cache hit)
        - Context for SQL generation (cache miss)
        """
        # Extract slots
        slots = extract_slots(query, known_apps=self.known_apps)
        
        # Validate slots
        valid_apps = self.known_apps
        valid_envs = ['PROD', 'STAGING', 'DEV', 'QA']
        validation = validate_slots(slots, valid_apps=valid_apps, valid_envs=valid_envs)
        
        if not validation["is_valid"]:
            return {
                "status": "error",
                "message": "Query validation failed",
                "warnings": validation["warnings"],
                "suggestions": validation["suggestions"]
            }
        
        # Generate cache key
        cache_key = slots.to_cache_key()
        
        # Check distributed cache
        cached_sql = self.cache.get(cache_key)
        
        if cached_sql:
            # Cache hit - substitute dynamic values and execute
            sql = self._substitute_dynamic_values(cached_sql, slots)
            result = self.executor.execute(sql)
            
            return {
                "status": "success",
                "cached": True,
                "sql": sql,
                "cache_key": cache_key,
                **result
            }
        
        # Cache miss - prepare for SQL generation
        # Fetch schema for relevant table(s)
        table_name = slots.table_hint or "deployment_data"
        
        try:
            schema = self.schema_fetcher.get_table_info(table_name)
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to fetch schema: {str(e)}"
            }
        
        # Return context for IDE agent to generate SQL
        return {
            "status": "needs_generation",
            "cached": False,
            "query": query,
            "slots": slots.to_dict(),
            "schema": schema,
            "cache_key": cache_key,
            "validation": validation,
            "instruction": self._generate_sql_instruction(slots, schema)
        }
    
    def _substitute_dynamic_values(self, sql_template: str, slots: ExtractedSlots) -> str:
        """Substitute dynamic values (like current date) into cached SQL"""
        # For now, SQL is already concrete
        # In future, could use placeholders like {CURRENT_DATE}
        
        # If time range uses relative dates, the SQL already handles it with INTERVAL
        return sql_template
    
    def _generate_sql_instruction(self, slots: ExtractedSlots, schema: Dict) -> str:
        """Generate instruction for IDE agent to create SQL"""
        instruction = f"""Generate a PostgreSQL query based on the following:

**User Query**: {slots.raw_query}

**Extracted Information**:
- App Name: {slots.app_name or 'Any'}
- Environment: {slots.environment or 'Any'}
- Time Range: {self._format_time_range(slots.time_range)}
- Specific Date: {slots.specific_date or 'None'}
- Limit: {slots.limit or 'No limit'}
- Operation: {slots.operation_type}

**Database Schema**:
Table: {schema['table_name']}
Columns: {', '.join([f"{col['name']} ({col['type']})" for col in schema['columns']])}

**Sample Data**:
{json.dumps(schema['sample_data'], indent=2)}

**Requirements**:
1. Generate a SELECT query for the {schema['table_name']} table
2. Filter by app_name if specified: '{slots.app_name}'
3. Filter by deploy_env if specified: '{slots.environment}'
4. {self._get_time_filter_instruction(slots)}
5. Order by date DESC
6. {f"Limit to {slots.limit} results" if slots.limit else "No limit"}

Return ONLY the PostgreSQL query, no explanation or markdown formatting.
Use PostgreSQL syntax (e.g., CURRENT_DATE, INTERVAL).
"""
        return instruction
    
    def _format_time_range(self, time_range: Optional[TimeRange]) -> str:
        """Format time range for display"""
        if not time_range:
            return "None"
        return f"{time_range.value} {time_range.unit.value}"
    
    def _get_time_filter_instruction(self, slots: ExtractedSlots) -> str:
        """Get time filter instruction for SQL generation"""
        if slots.specific_date:
            return f"Filter by date = '{slots.specific_date}'"
        elif slots.time_range:
            unit = slots.time_range.unit.value.rstrip('s')  # Remove 's' from 'days'
            return f"Filter by date >= CURRENT_DATE - INTERVAL '{slots.time_range.value} {unit}'"
        else:
            return "No time filter needed"
    
    def nl2sql_execute(self, sql: str, cache_key: str, confirm_cache: bool = True) -> Dict[str, Any]:
        """
        Phase 2: Execute generated SQL and optionally cache it
        
        Args:
            sql: The SQL query to execute
            cache_key: The cache key to store this SQL under
            confirm_cache: Whether to cache this SQL (default True)
        
        Returns:
            Execution results
        """
        # Execute the SQL
        result = self.executor.execute(sql)
        
        if not result["success"]:
            return {
                "status": "error",
                "message": "SQL execution failed",
                **result
            }
        
        # Cache the SQL if successful and confirmed
        if confirm_cache:
            metadata = {
                "result_count": result["row_count"],
                "timestamp": datetime.now().isoformat()
            }
            self.cache.set(cache_key, sql, created_by=self.user_id, metadata=metadata)
        
        return {
            "status": "success",
            "cached": confirm_cache,
            "cache_key": cache_key,
            "sql": sql,
            **result
        }
    
    def nl2sql_cache_stats(self) -> Dict[str, Any]:
        """Get distributed cache statistics"""
        return self.cache.get_stats()
    
    def nl2sql_cache_list(self, limit: int = 50) -> Dict[str, Any]:
        """List cached queries"""
        keys = self.cache.list_keys(limit=limit)
        return {
            "cached_queries": keys,
            "total_shown": len(keys)
        }
    
    def nl2sql_cache_delete(self, cache_key: str) -> Dict[str, Any]:
        """Delete a specific cache entry"""
        deleted = self.cache.delete(cache_key)
        return {
            "status": "success" if deleted else "not_found",
            "message": f"Cache entry {'deleted' if deleted else 'not found'}"
        }
    
    def nl2sql_cache_clear(self) -> Dict[str, str]:
        """Clear the entire cache (admin only)"""
        self.cache.clear_all()
        return {"status": "success", "message": "Cache cleared"}
    
    def nl2sql_cache_cleanup(self, days_old: int = 90) -> Dict[str, Any]:
        """Remove old cache entries"""
        deleted_count = self.cache.cleanup_old_entries(days_old)
        return {
            "status": "success",
            "deleted_count": deleted_count,
            "message": f"Removed {deleted_count} entries older than {days_old} days"
        }


# MCP Server Integration
def register_nl2sql_tools(mcp_server, db_connection_string: str, user_id: Optional[str] = None):
    """Register NL2SQL tools with MCP server"""
    tools = NL2SQLTools(db_connection_string, user_id=user_id)
    
    @mcp_server.tool()
    def nl2sql_prepare(query: str) -> dict:
        """
        Prepare natural language query for SQL generation.
        
        Extracts slots, checks distributed cache, and either returns results 
        directly (cache hit) or provides context for SQL generation (cache miss).
        """
        return tools.nl2sql_prepare(query)
    
    @mcp_server.tool()
    def nl2sql_execute(sql: str, cache_key: str, confirm_cache: bool = True) -> dict:
        """
        Execute SQL query and optionally cache it in distributed cache.
        
        Args:
            sql: The SQL query to execute
            cache_key: The cache key from nl2sql_prepare
            confirm_cache: Whether to cache this SQL for future use by all users
        """
        return tools.nl2sql_execute(sql, cache_key, confirm_cache)
    
    @mcp_server.tool()
    def nl2sql_cache_stats() -> dict:
        """Get distributed cache statistics"""
        return tools.nl2sql_cache_stats()
    
    @mcp_server.tool()
    def nl2sql_cache_list(limit: int = 50) -> dict:
        """List cached queries from distributed cache"""
        return tools.nl2sql_cache_list(limit)
    
    @mcp_server.tool()
    def nl2sql_cache_delete(cache_key: str) -> dict:
        """Delete a specific cache entry"""
        return tools.nl2sql_cache_delete(cache_key)
    
    @mcp_server.tool()
    def nl2sql_cache_clear() -> dict:
        """Clear the entire distributed cache (use with caution)"""
        return tools.nl2sql_cache_clear()
    
    @mcp_server.tool()
    def nl2sql_cache_cleanup(days_old: int = 90) -> dict:
        """Remove cache entries not used in N days"""
        return tools.nl2sql_cache_cleanup(days_old)


# Example usage (for testing)
if __name__ == "__main__":
    import os
    
    # Get connection string from environment
    DB_CONNECTION = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/deployments")
    
    # Initialize tools
    tools = NL2SQLTools(DB_CONNECTION, user_id="test_user")
    
    # Test queries
    test_queries = [
        "Show me deployments for frontend in the last week",
        "How many tests ran for api-gateway this month",
        "List deployments on 2024-01-15",
        "Get the last 5 deployments to prod",
    ]
    
    print("=" * 80)
    print("NL2SQL DISTRIBUTED CACHE TESTING")
    print("=" * 80)
    
    for query in test_queries:
        print(f"\n{'='*80}")
        print(f"Query: {query}")
        print(f"{'='*80}")
        
        # Phase 1: Prepare
        result = tools.nl2sql_prepare(query)
        
        if result["status"] == "success" and result["cached"]:
            print("✓ CACHE HIT (from distributed cache)")
            print(f"SQL: {result['sql']}")
            print(f"Rows: {result['row_count']}")
        
        elif result["status"] == "needs_generation":
            print("✗ CACHE MISS - SQL generation needed")
            print(f"\nCache Key: {result['cache_key']}")
            print(f"\nExtracted Slots:")
            for key, value in result['slots'].items():
                if not key.startswith('_'):
                    print(f"  {key}: {value}")
        
        elif result["status"] == "error":
            print(f"✗ ERROR: {result['message']}")
