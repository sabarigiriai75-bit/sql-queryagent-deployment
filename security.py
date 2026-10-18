import re

# Dangerous SQL keywords to block
BLOCKED_KEYWORDS = [
    "DROP", "DELETE", "TRUNCATE", "ALTER",
    "INSERT", "UPDATE", "GRANT", "REVOKE",
    "EXEC", "EXECUTE", "--", ";--", "/*"
]

def validate_query(query: str) -> dict:
    """Check if query is safe before sending to AI"""
    
    query_upper = query.upper()
    
    # Check for dangerous keywords
    for keyword in BLOCKED_KEYWORDS:
        if keyword in query_upper:
            return {
                "safe": False,
                "reason": f"Blocked keyword detected: {keyword}"
            }
    
    # Check query length
    if len(query) > 500:
        return {
            "safe": False,
            "reason": "Query too long"
        }
    
    # Check for special characters
    if re.search(r"[;'\"]", query):
        return {
            "safe": False,
            "reason": "Special characters not allowed"
        }
    
    return {"safe": True, "reason": "OK"}