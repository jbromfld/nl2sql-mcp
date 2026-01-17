# nl2sql-mcp
NL to SQL MCP tool
user query
var extraction/slot filler (use small model, or just slot logic)
if query w/var extraction not in cache:
    table extraction?
    fetch schema (schema manager seems fragile)
    send schema + query back? (already using CP/CC)
    construct sql
else:
    fetch sql
send sql to source
return results
cache query w/slots on positive feedback



User: "Show me deployments for frontend in the last week"
    ↓
IDE Agent calls MCP tool: nl2sql_query
    ↓
Your MCP server:
  1. Extract slots (fast, deterministic)
     → {app: "frontend", time_range: {value: 1, unit: "weeks"}, ...}
  
  2. Generate cache key from slots
     → "SELECT:deployment_data:frontend:*:weeks:1:*"
  
  3. Check cache with slotted key
     ┌─ Cache HIT ──────────────────────────────────┐
     │ - Fetch cached SQL                           │
     │ - Substitute any dynamic values (dates)      │
     │ - Execute SQL                                │
     │ - Return results directly                    │
     └──────────────────────────────────────────────┘
     
     ┌─ Cache MISS ─────────────────────────────────┐
     │ 4. Identify relevant tables from slots       │
     │    → table_hint: "deployment_data"           │
     │                                              │
     │ 5. Fetch schema for relevant table(s)       │
     │    → Query information_schema                │
     │    → Get columns, types, constraints         │
     │                                              │
     │ 6. Return context to IDE agent:              │
     │    {                                         │
     │      "slots": {...},                         │
     │      "schemas": [...],                       │
     │      "cache_key": "...",                     │
     │      "instruction": "Generate SQL"           │
     │    }                                         │
     └──────────────────────────────────────────────┘
    ↓
IDE Agent receives context (cache miss only)
  - Uses Claude to generate SQL with schema
  - Calls MCP tool: execute_sql_and_cache
    ↓
Your MCP server:
  - Executes SQL
  - IF successful AND user confirms → Cache {key: SQL}
  - Return results



Developer's IDE (Local)
    ↓
MCP Client (query_cicd_prepare/execute)
    ↓
    ↓ HTTPS
    ↓
Remote API Server (Flask)
    ↓
    ├─→ PostgreSQL Cache Table (distributed)
    └─→ PostgreSQL Data Tables (deployment_data, test_data)



nl2sql-system/
├── slot_filler.py              # Slot extraction logic
├── nl2sql_tools.py             # Core NL2SQL tools
├── api_server.py               # Flask API endpoints
├── mcp_tool.py                 # MCP tool registration
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variables template
├── docker-compose.yml          # Docker deployment (optional)
└── README.md                   # This file


  -- Most popular queries
SELECT cache_key, use_count, created_by, last_used
FROM nl2sql_cache
ORDER BY use_count DESC
LIMIT 10;

-- Cache by user
SELECT created_by, COUNT(*) as queries_created, SUM(use_count) as total_uses
FROM nl2sql_cache
GROUP BY created_by
ORDER BY total_uses DESC;

-- Stale entries
SELECT cache_key, last_used, 
       EXTRACT(DAY FROM (CURRENT_TIMESTAMP - last_used)) as days_since_use
FROM nl2sql_cache
WHERE last_used < CURRENT_TIMESTAMP - INTERVAL '30 days'
ORDER BY last_used;