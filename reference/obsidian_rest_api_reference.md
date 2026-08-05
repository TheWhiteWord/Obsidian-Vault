# Obsidian Local REST API Reference

Version: 5.0.3 | Plugin: obsidian-local-rest-api | Obsidian: 1.13.4

## Base URL
`https://127.0.0.1:27124/`

## Authentication
All requests require a Bearer token in the Authorization header:
```
Authorization: Bearer <your-api-key>
```

## SSL
Self-signed certificate. Download from: `https://127.0.0.1:27124/obsidian-local-rest-api.crt`
The cert is valid for 1 year and should be passed to httpx as `verify: /path/to/cert.pem`.

## Endpoints

### Root
`GET /`
Returns server manifest + versions:
```json
{
    "status": "OK",
    "manifest": {"id": "obsidian-local-rest-api", "version": "5.0.3"},
    "versions": {"obsidian": "1.13.4", "self": "5.0.3"},
    "authenticated": false
}
```

### Vault Listing
`GET /vault/[path]`
Lists files and subdirectories in a vault path. Directories end with `/`.
```json
{"files": ["CREATIVE/", "INDEX.md", "RESEARCH/", "SYSTEM/"]}
```

### Read a Note
`GET /vault/path/to/note.md`
Returns the raw markdown content with frontmatter.

### Patch Operations
`PATCH /vault/path/to/note.md`

**JSON instruction format:**
```json
{
    "targetType": "<type>",
    "target": <target>,
    "operation": "<op>",
    "value": <payload>
}
```

**targetType options:**
- `"heading"` — targets by heading name (target is array of heading strings)
- `"block"` — targets by block reference
- `"frontmatter"` — targets by frontmatter key (target is string key name)

**operation options:**
- `"append"` — append content
- `"replace"` — replace target
- `"delete"` — delete target

**Examples:**

Append to frontmatter tags (frontmatter target):
```json
{
    "targetType": "frontmatter",
    "target": "tags",
    "operation": "append",
    "value": ["new-tag"]
}
```

Append to a heading (heading target):
```json
{
    "targetType": "heading",
    "target": ["My Section"],
    "operation": "append",
    "content": "New line content"
}
```

Key learnings:
- For `frontmatter` targets, use `value` (not `content`) for the payload
- For `frontmatter` targets, `target` is a string (the key name), not an array
- For `heading` targets, `target` is an array of heading path components

### Search (Simple)
`POST /vault/search/simple`
Content-Type: `text/plain`
Body: the search query string
Returns: array of `{filename, score, matches}`

### Search (JsonLogic)
`POST /vault/search/query`
Content-Type: `application/json`
Body: JsonLogic query object evaluated against a NoteJson:
```json
{
    "path": "journal/2024-01-15.md",
    "content": "# My note\n...",
    "tags": ["tag1", "tag2"],
    "frontmatter": {"type": "note"}
}
```

Example query to scope to a folder:
```json
{
    "and": [
        {"var": "path"},
        {"regex": "^SYSTEM/.*"}
    ]
}
```

### MCP Endpoint
`https://127.0.0.1:27124/mcp/`
Streamable HTTP MCP transport. Requires same Bearer token auth via headers.
Accepts both `application/json` and `text/event-stream` content types.

### HTTP Fallback
`http://127.0.0.1:27123/mcp/`
Same MCP endpoint over plain HTTP (no TLS). Enable under Settings → Local REST API → Enable HTTP server.
