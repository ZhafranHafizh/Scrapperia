import re
from ai_engine import AIEngine

class OSINTAnalyzer:
    """Analyze text for OSINT entities (Emails, Phone, Links, Crypto) using Regex + Groq AI."""
    
    def __init__(self):
        self.ai = AIEngine()
        
    def extract_entities_regex(self, text: str) -> dict:
        """Extract basic entities using Regex."""
        entities = {
            "emails": list(set(re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text))),
            "phones": list(set(re.findall(r'(?:\+?62|0)[2-9]\d{7,11}', text))), # Basic ID phone
            "links": list(set(re.findall(r'(https?://[^\s]+)', text))),
        }
        
        # Filter out common noise from links (e.g. image extensions)
        clean_links = []
        for link in entities["links"]:
            if not any(ext in link.lower() for ext in ['.jpg', '.png', '.css', '.js', '.woff']):
                clean_links.append(link)
        entities["links"] = clean_links
        
        return entities

    def analyze_profile(self, target_name: str, results: list[dict]) -> dict:
        """Use AI (Groq) to build a profile summary from search results."""
        if not results:
            return {"profile": "No data found"}
            
        context = ""
        for i, r in enumerate(results[:15]): # Limit to top 15 for context length
            context += f"Result {i+1}:\nTitle: {r.get('title')}\nURL: {r.get('link')}\nDesc: {r.get('description')}\n---\n"
            
        prompt = f"""
You are an expert OSINT analyst. Analyze these search results about the target: '{target_name}'.
Extract a concise but comprehensive profile summary.
Focus on: Job/Role, Affiliations/Organizations, Known locations, and Key activities.
Do NOT make up information. If something is unknown, leave it out.

Search Results:
{context}

Respond in JSON format:
{{
  "profile_summary": "Paragraph summarizing who they are based on results",
  "affiliations": ["org1", "org2"],
  "locations": ["loc1"],
  "associated_usernames": ["user1"]
}}
"""
        return self.ai.generate_json(prompt, prefer_groq=True)

    def generate_dork(self, natural_query: str) -> str:
        """Use AI to convert natural query to Google/DDG Dork string."""
        prompt = f"""
You are an OSINT search expert. Convert this natural query into a highly effective DuckDuckGo / Google search Dork.
Natural Query: "{natural_query}"

Rules for Dork:
1. ALWAYS use exact quotes if the query is a person's name with spaces (e.g. "John Doe").
2. If looking for documents, append filetype:pdf OR filetype:xls etc if relevant.
3. If tracking a person, include typical social footprints (site:linkedin.com | site:twitter.com | site:instagram.com).
4. Keep it concise but highly targeted. Include the exact name inside quotes at the beginning.

Respond ONLY with a JSON object containing the dork string. Example:
{{"dork": "\\"target name\\" (site:linkedin.com | site:twitter.com)"}}
"""
        res = self.ai.generate_json(prompt, prefer_groq=True)
        return res.get("dork", natural_query)
