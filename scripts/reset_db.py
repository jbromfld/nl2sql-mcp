#!/usr/bin/env python3
"""
Database Reset Script for NL2SQL MCP Service
Cleans up and reinitializes the CI/CD database using configuration from .env
"""

import os
import sys
import psycopg2
from pathlib import Path
from dotenv import load_dotenv


def load_sql_file(file_path: Path) -> str:
    """Load SQL file content"""
    with open(file_path, 'r') as f:
        return f.read()


def execute_sql(conn, sql: str, description: str):
    """Execute SQL commands"""
    print(f"\n{'='*60}")
    print(f"Executing: {description}")
    print(f"{'='*60}")
    
    try:
        with conn.cursor() as cur:
            # Split by semicolons for multiple statements
            statements = [s.strip() for s in sql.split(';') if s.strip()]
            for stmt in statements:
                if stmt:
                    cur.execute(stmt)
            conn.commit()
            print(f"✓ {description} completed successfully")
    except Exception as e:
        conn.rollback()
        print(f"✗ Error executing {description}: {e}")
        raise


def main():
    # Load environment variables
    env_path = Path(__file__).parent.parent / '.env'
    if not env_path.exists():
        print(f"Error: .env file not found at {env_path}")
        sys.exit(1)
    
    load_dotenv(env_path)
    
    # Get database configuration from .env
    db_config = {
        'host': os.getenv('POSTGRES_SCRIPT_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_SCRIPT_PORT', '5432')),
        'database': os.getenv('POSTGRES_DB', 'cicd_service'),
        'user': os.getenv('POSTGRES_USER', 'testuser'),
        'password': os.getenv('POSTGRES_PASSWORD', 'testpass')
    }
    
    print("\n" + "="*60)
    print("NL2SQL MCP Database Reset Script")
    print("="*60)
    print(f"Host: {db_config['host']}:{db_config['port']}")
    print(f"Database: {db_config['database']}")
    print(f"User: {db_config['user']}")
    print("="*60)
    
    # Confirm before proceeding
    response = input("\n⚠️  This will DELETE ALL DATA in the database. Continue? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("Aborted.")
        sys.exit(0)
    
    # Path to SQL files
    sql_dir = Path(__file__).parent.parent / 'sql'
    sample_schema_sql = sql_dir / 'sample_db_schema.sql'
    cache_sql = sql_dir / 'cache.sql'
    
    # Verify SQL files exist
    for sql_path in [sample_schema_sql, cache_sql]:
        if not sql_path.exists():
            print(f"Error: SQL file not found: {sql_path}")
            sys.exit(1)
    
    # Connect to database
    try:
        print("\nConnecting to database...")
        conn = psycopg2.connect(**db_config)
        print("✓ Connected successfully")
        
        # Step 1: Initialize schema with sample data
        # Note: sample_db_schema.sql already includes DROP TABLE statements
        schema_sql = load_sql_file(sample_schema_sql)
        execute_sql(conn, schema_sql, "Database Schema & Sample Data")
        
        # Step 2: Ensure cache table exists (redundant but safe)
        cache_table_sql = load_sql_file(cache_sql)
        execute_sql(conn, cache_table_sql, "NL2SQL Cache Table")
        
        # Verify setup
        print("\n" + "="*60)
        print("Verifying Database Setup")
        print("="*60)
        
        with conn.cursor() as cur:
            # Check tables
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """)
            tables = [row[0] for row in cur.fetchall()]
            print(f"\n✓ Tables created: {len(tables)}")
            for table in tables:
                print(f"  - {table}")
            
            # Check deployment data
            cur.execute("SELECT COUNT(*) FROM deployment_data")
            deployment_count = cur.fetchone()[0]
            print(f"\n✓ Deployment records: {deployment_count}")
            
            # Check test data
            cur.execute("SELECT COUNT(*) FROM test_data")
            test_count = cur.fetchone()[0]
            print(f"✓ Test records: {test_count}")
            
            # Check cache
            cur.execute("SELECT COUNT(*) FROM nl2sql_cache")
            cache_count = cur.fetchone()[0]
            print(f"✓ Cache entries: {cache_count}")
            
            # Show recent deployments summary
            print("\n" + "-"*60)
            print("Recent Activity Summary:")
            print("-"*60)
            cur.execute("""
                SELECT 
                    app_name,
                    COUNT(*) as total_deployments,
                    SUM(CASE WHEN deploy_result = 'SUCCESS' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN deploy_result = 'FAILURE' THEN 1 ELSE 0 END) as failed
                FROM deployment_data
                GROUP BY app_name
                ORDER BY app_name
            """)
            for app_name, total, success, failed in cur.fetchall():
                print(f"  {app_name}: {total} deployments ({success} success, {failed} failed)")
            
            # Show environments
            print("\n" + "-"*60)
            print("Environments:")
            print("-"*60)
            cur.execute("""
                SELECT DISTINCT deploy_env, COUNT(*) 
                FROM deployment_data 
                GROUP BY deploy_env 
                ORDER BY deploy_env
            """)
            for env, count in cur.fetchall():
                print(f"  {env}: {count} deployments")
        
        print("\n" + "="*60)
        print("✓ Database reset completed successfully!")
        print("="*60)
        
        conn.close()
        
    except psycopg2.Error as e:
        print(f"\n✗ Database error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
