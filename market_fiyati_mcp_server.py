# market_fiyati_mcp_server.py (Tüm Güncellemeleri İçeren Final Versiyon)

import os
import re
import asyncio
import atexit
import logging
from typing import List, Dict, Any, Optional
from collections import namedtuple

# 3. parti kütüphaneler
import click
import jwt
from dotenv import load_dotenv
from pydantic import Field
from mcp.server.fastmcp import FastMCP

# Kendi modüllerimiz
from client import MarketFiyatApiClient
from models import ShoppingListResult
from utils.logging import setup_logger

# .env dosyasındaki değişkenleri yükle
load_dotenv()

# --- Yardımcı Fonksiyonlar ---
def parse_unit_price(unit_price_str: Optional[str]) -> float:
    """'101,37 ₺/kg' gibi bir metni 101.37 sayısına çevirir."""
    if not unit_price_str:
        return float('inf')  # Eğer birim fiyat yoksa sıralamada en sona gitsin
    try:
        # Sadece sayıları ve virgülü al, virgülü noktaya çevir
        cleaned_str = re.sub(r'[^\d,]', '', unit_price_str).replace(',', '.')
        return float(cleaned_str)
    except (ValueError, TypeError):
        return float('inf')

# --- Loglama ve Kaynak Yönetimi ---
logger = setup_logger("MCP_Server")

logger.info("MarketFiyatApiClient başlatılıyor...")
api_client = MarketFiyatApiClient()

def cleanup():
    """Uygulama kapandığında tüm kaynakları temizler."""
    logger.info("\nSunucu kapatılıyor, API istemci oturumu temizleniyor...")
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            loop.create_task(api_client.close_client())
        else:
            asyncio.run(api_client.close_client())
    except RuntimeError:
        asyncio.run(api_client.close_client())

atexit.register(cleanup)

# --- Güvenlik Bileşenleri ---
PUBLIC_KEY_FILE = "public_key.pem"
ISSUER_URL = os.getenv("DASHBOARD_ISSUER_URL")
AUDIENCE = os.getenv("DASHBOARD_AUDIENCE")
AuthInfo = namedtuple("AuthInfo", ["claims", "expires_at", "scopes", "client_id"])

class SimpleBearerAuthProvider:
    def __init__(self, public_key: bytes, issuer: str, audience: str):
        self.public_key = public_key
        self.issuer = issuer
        self.audience = audience
        self.logger = setup_logger(self.__class__.__name__)

    async def verify_token(self, token: str) -> Dict[str, Any]:
        try:
            decoded_token = jwt.decode(
                token, self.public_key, algorithms=["RS256"],
                audience=self.audience, issuer=self.issuer,
            )
            client_id = decoded_token.get("sub")
            return AuthInfo(claims=decoded_token, expires_at=decoded_token.get("exp"), scopes=[], client_id=client_id)
        except jwt.PyJWTError as e:
            self.logger.error(f"Token doğrulama hatası: {e}")
            raise Exception("Geçersiz token")

# --- Ana Sunucu Sınıfı ---
class MarketMCPServer:
    def __init__(self, host: str, port: int, transport: str):
        self.host = host
        self.port = port
        self.transport = transport
        self.mcp = None

    async def initialize(self) -> FastMCP:
        logger.info("MCP sunucusu hazırlanıyor...")
        auth_provider = None
        if self.transport == 'sse':
            try:
                with open(PUBLIC_KEY_FILE, "rb") as f:
                    public_key = f.read()
                auth_provider = SimpleBearerAuthProvider(
                    public_key=public_key, issuer=ISSUER_URL, audience=AUDIENCE
                )
                logger.info("Yetkilendirme sağlayıcı başarıyla yüklendi.")
            except FileNotFoundError:
                logger.warning(f"'{PUBLIC_KEY_FILE}' bulunamadı. Sunucu güvensiz modda çalışacak.")

        auth_config = {"issuer_url": ISSUER_URL, "resource_server_url": f"http://{self.host}:{self.port}"} if auth_provider else None

        self.mcp = FastMCP(
            name="MarketFiyatiV2",
            instructions="Türkiye'deki zincir marketlerde bir alışveriş listesindeki ürünlerin fiyatlarını bulan gelişmiş bir asistan.",
            host=self.host, port=self.port,
            token_verifier=auth_provider,
            auth=auth_config,
        )
        self._register_tools()
        return self.mcp
        
    def _register_tools(self):
        @self.mcp.tool()
        async def find_shopping_list_prices(
            # ... parametreler aynı kalıyor ...
            product_list: List[str] = Field(..., description="..."),
            latitude: float = Field(..., description="..."),
            longitude: float = Field(..., description="..."),
            radius_km: int = Field(default=1, description="..."),
            limit: Optional[int] = Field(None, description="..."),
            sort_by: str = Field("price", description="...")
        ) -> ShoppingListResult:
            logger.info(f"Araç çağrıldı: products={product_list}, limit={limit}, sort_by={sort_by}")
            try:
                # Client'taki yeni ve doğru mantığa sahip fonksiyonu çağırıyoruz
                found_products = await api_client.find_products_in_shopping_list(
                    product_names=product_list, latitude=latitude, longitude=longitude, radius_km=radius_km
                )

                if not found_products:
                    return ShoppingListResult(found_prices_count=0, error_message="Listenizdeki ürünlerin hiçbiri bu bölgede bulunamadı.")

                # ... Sıralama ve Limitleme mantığı aynı kalıyor ...
                if sort_by.lower() == 'unit_price':
                    found_products.sort(key=lambda p: parse_unit_price(p.unit_price))
                else:
                    found_products.sort(key=lambda p: p.price)

                if limit and limit > 0:
                    found_products = found_products[:limit]
                
                # --- YENİ VE DAHA ŞIK FORMATLAMA BÖLÜMÜ ---
                summary_lines = [f"🛒 Listeniz için {len(found_products)} uygun sonuç bulundu:", ""]
                for i, product in enumerate(found_products, 1):
                    # Satır 1: Ürün Adı
                    summary_lines.append(f"{i}. {product.product_title}")
                    
                    # Satır 2-5: Detaylar (dikey olarak hizalı)
                    market_name = product.market_name.title()
                    distance_str = f"{product.distance_km:.2f} km" if product.distance_km is not None else "N/A"
                    price_str = f"{product.price:.2f} TL"
                    unit_price_str = product.unit_price or "Belirtilmemiş"

                    summary_lines.append(f"   🏪 Market: {market_name}")
                    summary_lines.append(f"   📍 Mesafe: {distance_str}")
                    summary_lines.append(f"   💰 Fiyat: {price_str}")
                    summary_lines.append(f"   ⚖️ Birim Fiyatı: {unit_price_str}")
                    
                    # Her ürün arasına boş bir satır ekle
                    summary_lines.append("")

                return ShoppingListResult(summary="\n".join(summary_lines), found_prices_count=len(found_products))
                
            except Exception as e:
                logger.exception("Araç çalıştırılırken beklenmedik bir hata oluştu.")
                return ShoppingListResult(found_prices_count=0, error_message=f"Teknik bir hata oluştu: {str(e)}")
            
# --- Sunucuyu Başlatan Komut Satırı Arayüzü ---
@click.command()
@click.option('--host', default='0.0.0.0', help='Sunucunun çalışacağı adres.')
@click.option('--port', default=int(os.getenv("MCP_SERVER_PORT", 8071)), help='Sunucunun çalışacağı port.')
@click.option('--transport', default='sse', help='Transport tipi (sse veya stdio).')
def main(host, port, transport):
    """Market Fiyatı MCP sunucusunu başlatır."""
    async def _run():
        server = MarketMCPServer(host=host, port=port, transport=transport)
        mcp = await server.initialize()
        logger.info("MCP sunucusu başarıyla hazırlandı.")
        return mcp
    
    try:
        mcp_instance = asyncio.run(_run())
        logger.info(f"Sunucu {host}:{port} adresinde {transport} transportu ile başlatılıyor...")
        mcp_instance.run(transport=transport)
    except Exception as e:
        logger.error(f"Sunucu başlatılamadı: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()