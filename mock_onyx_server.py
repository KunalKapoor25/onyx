from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class MockOnyxHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Handle POST requests (create connector)"""
        if self.path == "/manage/connector":
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "id": 123,
                "name": "Test GDrive",
                "source": "google_drive"
            }
            self.wfile.write(json.dumps(response).encode())

    def do_GET(self):
        """Handle GET requests (OAuth flows)"""
        if "/connector/oauth/authorize/" in self.path:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "redirect_url": "https://mock-google-auth.com/auth?state=test_state"
            }
            self.wfile.write(json.dumps(response).encode())
            
        elif "/connector/oauth/callback/" in self.path:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "credential_id": 456
            }
            self.wfile.write(json.dumps(response).encode())

    def do_PUT(self):
        """Handle PUT requests (create CC pair)"""
        if "/manage/connector/" in self.path and "/credential/" in self.path:
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                "id": 789,
                "success": True
            }
            self.wfile.write(json.dumps(response).encode())

if __name__ == "__main__":
    server = HTTPServer(('localhost', 8080), MockOnyxHandler)
    print("Mock Onyx server running on http://localhost:8080")
    server.serve_forever() 