# nl2sql-mcp

Natural Language to SQL conversion tool with intelligent caching, exposed via Model Context Protocol (MCP).




## 🎯 What Is This?

A specialized MCP server that converts natural language questions into SQL queries against your CI/CD database. It features:

- **Smart Slot Extraction**: Fast, deterministic parameter extraction (app names, environments, time ranges)
- **Intelligent Caching**: Query patterns are cached for instant responses on subsequent similar queries
- **Two-Step Process**: Prepare (check cache + provide context) → Execute (run SQL + cache result)
- **Dynamic Values**: Handles time-based queries with dynamic date substitution
- **Zero-Cost Cached Queries**: Once cached, queries return instantly without LLM overhead

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL with CI/CD data
- Environment variables configured (see `.env.template`)

### Installation

```bash
# 1. Clone and setup
cd nl2sql-mcp
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.template .env
# Edit .env with your database connection details

# 3. Initialize database
docker-compose up -d
python scripts/reset_db.py

# 4. Start the MCP server
python app/api_server.py
```

The server will start on the port specified in your `.env` file (default: 8081).

---

## 🔧 How It Works

### Query Flow

```
User: "Show me deployments for frontend in the last week"
    ↓
MCP Client calls: query_cicd_prepare
    ↓
Server:
  1. Extract slots (fast, deterministic)
     → {app: "frontend", time_range: {value: 1, unit: "weeks"}}
  
  2. Generate cache key from slots
     → "SELECT:deployment_data:frontend:*:weeks:1:*"
  
  3. Check cache with slotted key
     
     ┌─ Cache HIT ──────────────────────────────┐
     │ • Fetch cached SQL                       │
     │ • Substitute dynamic values (dates)      │
     │ • Execute SQL                            │
     │ • Return formatted results               │
     └──────────────────────────────────────────┘
     
     ┌─ Cache MISS ────────────────────────────┐
     │ • Identify relevant tables from slots   │
     │ • Fetch schema for those tables         │
     │ • Return context to MCP client:         │
     │   {                                     │
     │     "slots": {...},                     │
     │     "schemas": [...],                   │
     │     "cache_key": "...",                 │
     │     "instruction": "Generate SQL"       │
     │   }                                     │
     └─────────────────────────────────────────┘
    ↓
MCP Client (on cache miss):
  • Uses LLM to generate SQL with provided schema
  • Calls: query_cicd_execute
    ↓
Server:
  • Executes SQL
  • Returns formatted results
  • Caches {cache_key: SQL} for future queries
```

### Architecture

```
Developer's IDE (VS Code, Cursor, IntelliJ)
    ↓
MCP Client (query_cicd_prepare / query_cicd_execute)
    ↓ HTTP/HTTPS
    ↓
MCP Server (Flask API)
    ↓
    ├─→ PostgreSQL Cache Table (nl2sql_cache)
    └─→ PostgreSQL Data Tables (deployment_data, test_data, etc.)
```

---

## 📋 MCP Tools

### 1. `query_cicd_prepare`
Prepares a CI/CD database query from natural language.

**Parameters:**
- `question` (string): Natural language query

**Returns:**
- If cached: Complete formatted results
- If not cached: Schema + instructions for SQL generation

**Example:**
```json
{
  "question": "What was the last deployment for frontend to prod?"
}
```

### 2. `query_cicd_execute`
Executes generated SQL and caches the result.

**Parameters:**
- `sql` (string): The SQL query to execute
- `cache_key` (string): Cache key from prepare step
- `confirm_cache` (boolean): Whether to cache this query pattern

**Returns:**
- Formatted query results with metadata

**Example:**
```json
{
  "sql": "SELECT * FROM deployment_data WHERE app_name = 'frontend' ORDER BY timestamp DESC LIMIT 1",
  "cache_key": "SELECT:deployment_data:frontend:prod:*",
  "confirm_cache": true
}
```

---

## 💡 Example Queries

### Deployment Queries
```
"What was the last deployment for frontend to prod?"
"Show me all deployments to staging in the last week"
"List deployments for api-gateway today"
```

### Test Queries
```
"How many tests ran for frontend yesterday?"
"Show me test failures in the last 24 hours"
"What's the test pass rate for backend this week?"
```

### Failure Analysis
```
"Show me all deployment failures in the last month"
"Which apps have the most test failures?"
"List failed deployments for prod environment"
```

---

## 🗂️ Project Structure

```
nl2sql-mcp/



nl2sql-mcp/
├── app/
│   ├── __init__.py
│   ├── api_server.py           # Flask API endpoints
│   ├── nl2sql_tools.py         # Core NL2SQL tools
│   └── slot_filler.py          # Slot extraction logic
├── scripts/
│   └── reset_db.py             # Database reset utility
├── sql/
│   ├── cache.sql               # Cache table schema
│   └── sample_db_schema.sql    # Sample CI/CD schema
├── .env.template               # Environment variables template
├── .mcp.json                   # MCP configuration for VS Code
├── docker-compose.yml          # Docker deployment
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

---

## 🔍 Cache Management

### View Cache Statistics

```sql
-- Most popular queries
SELECT cache_key, use_count, created_by, last_used
FROM nl2sql_cache
ORDER BY use_count DESC
LIMIT 10;

-- Cache by user
SELECT created_by, 
       COUNT(*) as queries_created, 
       SUM(use_count) as total_uses
FROM nl2sql_cache
GROUP BY created_by
ORDER BY total_uses DESC;

-- Cache hit rate
SELECT 
  COUNT(*) as total_cached_queries,
  SUM(use_count) as total_cache_hits,
  AVG(use_count) as avg_reuse_rate
FROM nl2sql_cache;
```

### Clean Up Stale Entries

```sql
-- Find stale entries (not used in 30+ days)
SELECT cache_key, last_used, 
       EXTRACT(DAY FROM (CURRENT_TIMESTAMP - last_used)) as days_since_use
FROM nl2sql_cache
WHERE last_used < CURRENT_TIMESTAMP - INTERVAL '30 days'
ORDER BY last_used;

-- Delete stale entries
DELETE FROM nl2sql_cache
WHERE last_used < CURRENT_TIMESTAMP - INTERVAL '90 days';
```

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file from `.env.template`:

```bash
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=cicd_db
DB_USER=your_user
DB_PASSWORD=your_password

# Server Configuration
API_PORT=8081
API_HOST=0.0.0.0

# Cache Settings
CACHE_ENABLED=true
CACHE_TTL_DAYS=90
```

### MCP Configuration

For VS Code, the included `.mcp.json` file configures the server. Update the URL if needed:

```json
{
  "servers": {
    "nl2sql-mcp": {
      "url": "http://localhost:8081/mcp",
      "type": "sse",
      "description": "Natural Language to SQL MCP server"
    }
  }
}
```

---

## 🐳 Docker Deployment

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Restart with fresh database
docker-compose down -v
docker-compose up -d
```

---

## 🧪 Testing

### Manual Testing

```bash
# Test prepare endpoint (cache miss)
curl -X POST http://localhost:8081/query/prepare \
  -H "Content-Type: application/json" \
  -d '{"question": "Show me last 5 deployments for frontend"}'

# Test execute endpoint
curl -X POST http://localhost:8081/query/execute \
  -H "Content-Type: application/json" \
  -d '{
    "sql": "SELECT * FROM deployment_data WHERE app_name='\''frontend'\'' ORDER BY timestamp DESC LIMIT 5",
    "cache_key": "SELECT:deployment_data:frontend:*:*:5",
    "confirm_cache": true
  }'

# Test prepare endpoint (cache hit)
curl -X POST http://localhost:8081/query/prepare \
  -H "Content-Type: application/json" \
  -d '{"question": "Show me last 5 deployments for frontend"}'
```

---

## 📈 Performance

### Cache Benefits

| Scenario | Time | Cost | Notes |
|----------|------|------|-------|
| **Cache Hit** | ~50ms | $0 | Instant SQL retrieval + execution |
| **Cache Miss** | ~2-5s | ~$0.01 | Schema fetch + LLM generation + execution |
| **After 10 uses** | - | ~$0.001/query | Amortized cost drops significantly |

### Optimization Tips

1. **Use consistent query patterns** - "last N deployments" patterns cache well
2. **Leverage time ranges** - "last week", "today", "last 24 hours" are dynamically substituted
3. **Review cache statistics** - Identify and optimize frequently-used query patterns
4. **Set appropriate TTL** - Balance cache freshness with reuse benefits

---

## 🤝 Integration with kbsearch-mcp

This tool can be used alongside [kbsearch-mcp](../kbsearch-mcp) for a complete developer experience:

- **kbsearch-mcp**: RAG search for documentation and knowledge base
- **nl2sql-mcp**: SQL queries for CI/CD data and metrics

Both expose MCP tools that work seamlessly together in your IDE.

---

## 🔒 Security Notes

- Always use environment variables for credentials
- Consider using connection pooling for production
- Implement rate limiting for public deployments
- Review and sanitize generated SQL before caching
- Use read-only database users when possible

---

## 🛠️ Troubleshooting

### Server Won't Start

```bash
# Check if port is in use
lsof -i :8081

# View detailed logs
python app/api_server.py --debug

# Verify database connection
psql -h $DB_HOST -U $DB_USER -d $DB_NAME
```

### Cache Not Working

```bash
# Verify cache table exists
psql -d cicd_db -c "SELECT COUNT(*) FROM nl2sql_cache;"

# Check cache_key generation
# Enable debug logging in app/nl2sql_tools.py
```

### SQL Generation Issues

- Ensure schema is properly loaded
- Check slot extraction logic in `app/slot_filler.py`
- Verify table hints match actual table names
- Review LLM prompt templates

---

## 📄 License

MIT License

---

**Questions or Issues?** Open an issue in the repository.

**Last Updated**: January 2026
