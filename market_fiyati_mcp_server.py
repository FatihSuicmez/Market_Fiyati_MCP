# market_fiyati_mcp_server.py (Tüm Düzeltmeler Uygulanmış Son Hali)
import os
from dotenv import load_dotenv
load_dotenv()   
import asyncio
import atexit
import click
import jwt
import json
from collections import namedtuple
from typing import Dict, Any, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import Field

# Yerel modüllerimizi import ediyoruz
from client import MarketFiyatApiClient
from models import ProductSearchResult
from utils.logging import setup_logger # TÜİK projesindeki logger'ı varsayıyoruz

# --- YENİ EKLENEN BÖLÜM: Kaynak Yönetimi ---
# Sunucu başladığında API istemcisini bir kez oluşturuyoruz.
# Bu, her istekte tekrar tekrar Playwright başlatmayı önler.
print("MarketFiyatApiClient başlatılıyor (Playwright)...")
api_client = MarketFiyatApiClient()

def cleanup():
    """Sunucu kapandığında Playwright oturumunu temizler."""
    print("\nSunucu kapatılıyor, Playwright kaynakları temizleniyor...")
    # atexit senkron çalıştığı için asenkron fonksiyonu bu şekilde çalıştırmalıyız.
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            loop.create_task(api_client.close_client_session())
        else:
            asyncio.run(api_client.close_client_session())
    except RuntimeError: # Hiç event loop yoksa
        asyncio.run(api_client.close_client_session())

# Program ne şekilde kapanırsa kapansın, cleanup fonksiyonunun çalışmasını garantile
atexit.register(cleanup)


# --- GÜVENLİK BİLEŞENLERİ (TÜİK projesinden uyarlandı) ---
PUBLIC_KEY_FILE = "public_key.pem"
# DÜZELTME 1: ISSUER_URL, token'ı üreten dashboard'un adresiyle (8050) aynı olmalıdır.
ISSUER_URL = os.getenv("DASHBOARD_ISSUER_URL")
AUDIENCE = os.getenv("DASHBOARD_AUDIENCE") # Projeye özel yeni bir audience

AuthInfo = namedtuple("AuthInfo", ["claims", "expires_at", "scopes", "client_id"])

class SimpleBearerAuthProvider:
    def __init__(self, public_key: bytes, issuer: str, audience: str):
        self.public_key = public_key
        self.issuer = issuer
        self.audience = audience
        self.logger = setup_logger(__name__)

    async def verify_token(self, token: str) -> Dict[str, Any]:
        try:
            decoded_token = jwt.decode(
                token, self.public_key, algorithms=["RS256"],
                audience=self.audience, issuer=self.issuer,
            )
            client_id = decoded_token.get("sub")
            return AuthInfo(claims=decoded_token, expires_at=decoded_token.get("exp"), scopes=[], client_id=client_id)
        except jwt.PyJWTError as e:
            self.logger.error(f"Token verification failed: {e}")
            raise Exception("Invalid token")

class ConfigurationError(Exception):
    pass

# --- ANA SUNUCU SINIFI (TÜİK projesindeki yapıya benzetildi) ---
class MarketMCPServer:
    def __init__(self, host: str, port: int, transport: str):
        self.logger = setup_logger(__name__)
        self.host = host
        self.port = port
        self.transport = transport
        self.mcp = None

    async def initialize(self) -> FastMCP:
        self.logger.info("Initializing MCP server")
        
        auth_provider = None
        if self.transport == 'sse':
            self.logger.info("SSE transport: setting up Simple Bearer authentication.")
            try:
                with open(PUBLIC_KEY_FILE, "rb") as f:
                    public_key = f.read()
                auth_provider = SimpleBearerAuthProvider(
                    public_key=public_key, issuer=ISSUER_URL, audience=AUDIENCE
                )
                self.logger.info("Authentication provider loaded.")
            except FileNotFoundError:
                self.logger.warning(f"'{PUBLIC_KEY_FILE}' not found. Server running in insecure mode.")

        auth_config = None
        if auth_provider:
            # DÜZELTME 2: FastMCP'nin yeni versiyonları 'resource_server_url' alanını zorunlu kılıyor.
            auth_config = {
                "issuer_url": ISSUER_URL,
                "resource_server_url": f"http://{self.host}:{self.port}"
            }

        self.mcp = FastMCP(
            name="MarketFiyatiMCP",
            instructions="Türkiye'deki zincir marketlerde (A101, BİM, Migros vb.) ürün fiyatlarını bulan bir asistan. Kullanıcının konumuna en yakın marketlerdeki en ucuz ürünleri bulabilir.",
            host=self.host, port=self.port,
            token_verifier=auth_provider,
            auth=auth_config,
        )
        
        self._register_tools()
        return self.mcp
        
    def _register_tools(self):
        @self.mcp.tool()
        async def find_cheapest_product(
            product_name: str = Field(..., description="Aranacak ürünün adı. Örnek: 'süt', 'bebek bezi', 'domates'."),
            latitude: float = Field(..., description="Kullanıcının enlem (latitude) koordinatı."),
            longitude: float = Field(..., description="Kullanıcının boylam (longitude) koordinatı."),
            radius_km: int = Field(default=1, description="Arama yapılacak kilometre cinsinden yarıçap. Varsayılan 1 km'dir.")
        ) -> ProductSearchResult:
            """
            Belirtilen coğrafi koordinatların etrafındaki belirli bir yarıçap içinde
            bir ürün için en ucuz fiyatı bulur. Marketleri ve fiyatları listeleyerek döndürür.
            """
            self.logger.info(f"Tool 'find_cheapest_product' called with: {product_name}")
            try:
                # API istemcisi zaten başta oluşturulduğu için tekrar başlatmaya gerek yok.
                result = await api_client.search_prices(
                    product_name=product_name,
                    latitude=latitude,
                    longitude=longitude,
                    radius_km=radius_km
                )
                if not result.results and not result.error_message:
                    result.error_message = "Belirtilen kriterlere uygun ürün bulunamadı."
                return result
            except Exception as e:
                self.logger.exception("Araç çalıştırılırken hata oluştu.")
                return ProductSearchResult(
                    search_query=product_name,
                    results=[],
                    error_message=f"Teknik bir hata oluştu: {str(e)}"
                )

# --- SUNUCUYU BAŞLATAN BÖLÜM (TÜİK projesindeki gibi 'click' ile) ---
@click.command()
@click.option('--host', default='0.0.0.0', help='Server host')
@click.option('--port', default=int(os.getenv("MCP_SERVER_PORT", 8071)), help='Server port')# Çakışmaması için farklı bir port
@click.option('--transport', default='sse', help='Transport type (sse veya stdio)')
def main(host, port, transport):
    """Start the Market Fiyatı MCP server."""
    logger = setup_logger(__name__)
    
    async def _run():
        server = MarketMCPServer(host=host, port=port, transport=transport)
        mcp = await server.initialize()
        logger.info("MCP server initialized successfully")
        return mcp
    
    try:
        mcp = asyncio.run(_run())
        logger.info(f"Starting server on {host}:{port} with {transport} transport...")
        mcp.run(transport=transport)
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")

if __name__ == "__main__":
    main()