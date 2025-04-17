import json
import requests
from typing import Dict, Any, List, Optional, Generator

class OnyxSearchClient:
    """Client for interacting with Onyx's search functionality"""
    
    def __init__(self, base_url: str, api_key: str):
        """Initialize the Onyx search client
        
        Args:
            base_url: The base URL of your Onyx instance (e.g., "http://localhost:8080")
            api_key: Your Onyx API key for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.headers = {
            "Content-Type": "application/json"
        }

    def process_streaming_response(self, response) -> Generator[Dict[str, Any], None, None]:
        """Process streaming response line by line"""
        answer = ""
        documents = []
        citations = {}
        referenced_doc_ids = set()  # Track which documents are referenced
        
        for line in response.iter_lines():
            if not line:
                continue
                
            try:
                line_str = line.decode('utf-8')
                packet = json.loads(line_str)
                
                # Handle different packet types
                if "answer_piece" in packet:
                    answer += packet["answer_piece"]
                    yield {"type": "answer_piece", "content": packet["answer_piece"]}
                elif "top_documents" in packet:
                    documents = packet["top_documents"]
                    # Store all documents but don't create citations yet
                    for doc in documents:
                        doc_id = doc.get('id')
                        if doc_id:
                            citations[doc_id] = {
                                'title': doc.get('semantic_identifier', ''),
                                'link': doc.get('link', ''),
                                'source': doc.get('source', ''),
                                'blurb': doc.get('blurb', '')
                            }
                    yield {"type": "documents", "content": documents}
                elif "citations" in packet:
                    # Track which documents are actually referenced in the answer
                    for citation in packet["citations"]:
                        if isinstance(citation, list) and len(citation) == 2:
                            doc_id, citation_text = citation
                            referenced_doc_ids.add(doc_id)
                            if doc_id in citations:
                                citations[doc_id]['citation_text'] = citation_text
                    # Don't filter citations here, just yield them all
                    yield {"type": "citations", "content": citations}
                elif "error" in packet:
                    yield {"type": "error", "content": packet["error"]}
                
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON: {e}")

    def search_with_answer(
        self, 
        query: str,
        stream: bool = False,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any] | Generator[Dict[str, Any], None, None]:
        """Perform a document search and get an AI-generated answer"""
        
        # Create a chat session first
        session_endpoint = f"{self.base_url}/chat/create-chat-session"
        session_data = {"description": "New chat session"}
        session_response = requests.post(
            session_endpoint, 
            headers=self.headers,
            json=session_data
        )
        session_id = session_response.json()["chat_session_id"]

        # Send the message
        endpoint = f"{self.base_url}/chat/send-message"
        data = {
            "message": query,
            "chat_session_id": session_id,
            "parent_message_id": None,
            "prompt_id": None,
            "file_descriptors": [],
            "search_doc_ids": None,
            "retrieval_options": {
                "run_search": "always",
                "filters": filters or {}
            }
        }

        try:
            response = requests.post(
                endpoint,
                headers=self.headers,
                json=data,
                stream=True  # Enable streaming
            )
            response.raise_for_status()

            if stream:
                # Return generator for streaming response
                return self.process_streaming_response(response)
            else:
                # Collect all streaming data into single response
                answer = ""
                documents = []
                citations = {}
                error = None
                citation_details = []

                for packet in self.process_streaming_response(response):
                    if packet["type"] == "answer_piece":
                        answer += packet["content"]
                    elif packet["type"] == "documents":
                        documents = packet["content"]
                    elif packet["type"] == "citations":
                        citations = packet["content"]
                        # Only add citation details for referenced documents
                        citation_details = [
                            {
                                'title': info.get('title', ''),
                                'link': info.get('link', ''),
                                'source': info.get('source', ''),
                                'blurb': info.get('blurb', ''),
                                'citation_text': info.get('citation_text', '')
                            }
                            for info in citations.values()
                        ]
                    elif packet["type"] == "error":
                        error = packet["content"]

                return {
                    "answer": answer,
                    "documents": documents,
                    "citations": citations,
                    "citation_details": citation_details,
                    "error": error
                }

        except requests.exceptions.RequestException as e:
            raise OnyxSearchException(f"Search request failed: {str(e)}")

    def search(
        self, 
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """Perform a document search"""
        endpoint = f"{self.base_url}/query/document-search"
        
        # Match the DocumentSearchRequest model exactly
        data = {
            "message": query,
            "search_type": "keyword",
            "retrieval_options": {
                "filters": filters or {},
                "run_search": "always",
                "real_time": True,
                "enable_auto_detect_filters": False,
                "offset": (page - 1) * page_size,
                "limit": page_size
            },
            "recency_bias_multiplier": 1.0,  # Added from model
            "evaluation_type": "skip",  # Changed to lowercase
            "rerank_settings": None  # Added from model
        }
        
        try:
            response = requests.post(
                endpoint,
                headers=self.headers,
                json=data
            )
            # Print more details about the response
            print(f"Status Code: {response.status_code}")
            print(f"Response Headers: {response.headers}")
            print(f"Response Text: {response.text[:1000]}")  # Print first 1000 chars only
            
            response.raise_for_status()
            if not response.text:
                raise OnyxSearchException("Empty response received from server")
            return response.json()
        except requests.exceptions.RequestException as e:
            raise OnyxSearchException(f"Search request failed: {str(e)}")

    def get_document(self, document_id: str) -> Dict[str, Any]:
        """Retrieve a specific document by ID"""
        # Remove /api prefix
        endpoint = f"{self.base_url}/query/document/{document_id}"
        
        try:
            response = requests.get(
                endpoint,
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise OnyxSearchException(f"Document retrieval failed: {str(e)}")

    def health_check(self) -> bool:
        """Check if the Onyx server is healthy"""
        try:
            # Add /health-check instead of /health
            response = requests.get(f"{self.base_url}/health")
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False


class OnyxSearchException(Exception):
    """Custom exception for Onyx search client errors"""
    pass


# Usage example
if __name__ == "__main__":
    # Initialize client
    client = OnyxSearchClient(
        base_url="http://localhost:8080",
        api_key="your-api-key"
    )
    
    try:
        # Check if server is healthy
        if not client.health_check():
            print("Warning: Onyx server appears to be down")
            
        # Non-streaming example
        print("\nComplete response:")
        result = client.search_with_answer(
            query="What instance should i use for my homework?",
            stream=False
        )
        
        # Create a mapping of citation numbers to details
        citation_map = {}
        for i, citation in enumerate(result["citation_details"], 1):
            citation_id = f"[[{i}]]"  # Match the format in the answer text
            citation_map[citation_id] = citation
        
        # Replace citation placeholders in the answer with proper links
        answer = result["answer"]
        for citation_id, citation in citation_map.items():
            link = citation.get('link', '#')
            # Replace [[N]]() with [[N]](link)
            answer = answer.replace(f"{citation_id}()", f"{citation_id}({link})")
        
        # Print answer with citations
        print("Answer:", answer)
        print("\nSources:")
        for i, citation in enumerate(result["citation_details"], 1):
            print(f"\n[{i}]")
            print(f"  Title: {citation['title']}")
            if citation.get('link'):
                print(f"  Link: {citation['link']}")
            if citation.get('source'):
                print(f"  Source: {citation['source']}")
            if citation.get('citation_text'):
                print(f"  Relevant text: {citation['citation_text']}")
            print(f"  Preview: {citation['blurb'][:100]}...")
        
    except OnyxSearchException as e:
        print(f"Error: {e}") 