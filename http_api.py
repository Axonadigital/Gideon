import asyncio
import os
from aiohttp import web
import json

class GideonHTTPAPI:
    """HTTP API för Siri Shortcuts och externa integrationer"""

    def __init__(self, get_claude_session_func, api_key):
        """
        Args:
            get_claude_session_func: Funktion för att hämta Claude session
            api_key: API key för autentisering
        """
        self.get_claude_session = get_claude_session_func
        self.api_key = api_key
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self):
        """Sätt upp HTTP routes"""
        self.app.router.add_post('/api/ask', self.handle_ask)
        self.app.router.add_get('/api/health', self.handle_health)

    async def handle_health(self, request):
        """Health check endpoint"""
        return web.json_response({
            'status': 'ok',
            'service': 'Gideon API'
        })

    async def handle_ask(self, request):
        """
        Hantera /api/ask requests från Siri Shortcuts

        Request body:
        {
            "message": "Din fråga här",
            "api_key": "din-api-key",
            "user_id": "optional-user-id"
        }

        Response:
        {
            "response": "Gideons svar",
            "success": true
        }
        """
        try:
            # Läs request body
            data = await request.json()

            # Validera API key
            if data.get('api_key') != self.api_key:
                return web.json_response({
                    'error': 'Invalid API key',
                    'success': False
                }, status=401)

            # Hämta message
            message = data.get('message', '').strip()
            if not message:
                return web.json_response({
                    'error': 'Message is required',
                    'success': False
                }, status=400)

            # Hämta user_id (default till 'siri' om inte angivet)
            user_id = data.get('user_id', 'siri_user')

            # Få Claude session
            claude = self.get_claude_session(user_id)

            # Använd timeout för att förhindra långsamma requests
            try:
                response = await asyncio.wait_for(
                    claude.ask(message, user_name='Siri'),
                    timeout=120.0
                )
            except asyncio.TimeoutError:
                return web.json_response({
                    'error': 'Request timeout',
                    'success': False
                }, status=504)

            # Returnera svar
            return web.json_response({
                'response': response,
                'success': True
            })

        except json.JSONDecodeError:
            return web.json_response({
                'error': 'Invalid JSON',
                'success': False
            }, status=400)
        except Exception as e:
            print(f"❌ API Error: {e}")
            return web.json_response({
                'error': str(e),
                'success': False
            }, status=500)

    async def start(self, port=8080):
        """Starta HTTP server"""
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        print(f"🌐 HTTP API startad på port {port}")
        print(f"📱 Siri Shortcuts endpoint: POST /api/ask")
        return runner
