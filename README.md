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