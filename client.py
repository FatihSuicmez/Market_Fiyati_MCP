# client.py (Kesin ve Düzeltilmiş Versiyon)
import os
from dotenv import load_dotenv
load_dotenv()
import asyncio
from playwright.async_api import async_playwright
from typing import List

# Modellerimizi import ediyoruz
from models import MarketInfo, ProductPrice, ProductSearchResult

class MarketFiyatApiClient:
    def __init__(self):
        self.playwright = None
        self.api_context = None # Bu değişkeni geri getirdik, çünkü doğru kullanım için gerekli.

    async def initialize_client(self):
        """Playwright'i ve API isteği bağlamını doğru şekilde başlatır."""
        if not self.playwright:
            print("Playwright başlatılıyor...")
            self.playwright = await async_playwright().start()
            # DOĞRU KULLANIM: İstekler için yeni bir bağlam (context) oluşturuyoruz.
            self.api_context = await self.playwright.request.new_context()

    async def search_prices(self, product_name: str, latitude: float, longitude: float, radius_km: int) -> ProductSearchResult:
        """
        Önce en yakın marketleri bulur, sonra o marketlerde ürün fiyatlarını arar ve en ucuzunu döndürür.
        """
        await self.initialize_client()

        # --- 1. ADIM: En Yakın Marketleri Bul ---
        try:
            NEAREST_API_URL = os.getenv("NEAREST_API_URL")
            nearest_payload = {"latitude": latitude, "longitude": longitude, "distance": radius_km}
            
            print(f"-> Adım 1: En yakın marketler için API'a istek atılıyor...")
            # DÜZELTME: İstek oluşturduğumuz api_context üzerinden yapılıyor.
            response_nearest = await self.api_context.post(NEAREST_API_URL, data=nearest_payload)
            
            if not response_nearest.ok:
                raise Exception(f"Nearest API hatası: {response_nearest.status}")
            
            nearby_stores_data = await response_nearest.json()
            if not nearby_stores_data:
                return ProductSearchResult(search_query=product_name, results=[], error_message="Yakınlarda market bulunamadı.")
            
            print(f"   {len(nearby_stores_data)} adet market bulundu.")
            
            depot_ids = [store.get("id") for store in nearby_stores_data]
            store_details_map = {store.get("id"): store for store in nearby_stores_data}

        except Exception as e:
            return ProductSearchResult(search_query=product_name, results=[], error_message=f"Marketleri bulurken hata: {e}")

        # --- 2. ADIM: Bulunan Marketlerde Ürün Fiyatlarını Ara ---
        try:
            SEARCH_API_URL = os.getenv("SEARCH_API_URL")
            search_payload = {
                "keywords": product_name, "depots": depot_ids, "distance": radius_km,
                "latitude": latitude, "longitude": longitude, "pages": 0, "size": 50
            }

            print(f"-> Adım 2: '{product_name}' için fiyatlar API'dan isteniyor...")
            # DÜZELTME: İstek oluşturduğumuz api_context üzerinden yapılıyor.
            response_search = await self.api_context.post(SEARCH_API_URL, data=search_payload)
            
            if not response_search.ok:
                raise Exception(f"Search API hatası: {response_search.status}")

            product_search_results = await response_search.json()
            
            all_results: List[ProductPrice] = []
            
            for product_data in product_search_results.get("content", []):
                for price_info in product_data.get("productDepotInfoList", []):
                    depot_id = price_info.get("depotId")
                    store_details = store_details_map.get(depot_id)

                    if store_details:
                        market_info = MarketInfo(
                            name=store_details.get("sellerName"), address=None,
                            distance_km=store_details.get("distance", 0) / 1000
                        )
                        product_price = ProductPrice(
                            product_name=product_data.get("title"), price=price_info.get("price"),
                            market=market_info
                        )
                        all_results.append(product_price)
            
            if not all_results:
                return ProductSearchResult(search_query=product_name, results=[], error_message="Bu marketlerde aradığınız ürün bulunamadı.")

            all_results.sort(key=lambda p: p.price)
            print(f"   Toplam {len(all_results)} adet fiyat bilgisi bulundu ve sıralandı.")

            return ProductSearchResult(
                search_query=product_name, results=all_results, cheapest_option=all_results[0]
            )

        except Exception as e:
            return ProductSearchResult(search_query=product_name, results=[], error_message=f"Ürünleri ararken hata: {e}")

    async def close_client_session(self):
        """Playwright oturumunu ve API bağlamını kapatır."""
        # DÜZELTME: Oluşturduğumuz api_context'i de sonlandırmalıyız.
        if self.api_context:
            await self.api_context.dispose()
        if self.playwright:
            await self.playwright.stop()
        print("MarketFiyatApiClient oturumu ve API bağlamı kapatıldı.")


async def main_test():
    print("Genişletilmiş Alan Testi Başlatılıyor...")
    client = MarketFiyatApiClient()
    arama_yarıçapı = 5
    aranan_ürün = "bebek bezi"
    print(f"TEST: {arama_yarıçapı} km alanda en ucuz '{aranan_ürün}' aranıyor...")
    result = await client.search_prices(
        product_name=aranan_ürün, latitude=41.0082, longitude=28.9784, radius_km=arama_yarıçapı
    )
    print("\n--- ARAMA SONUCU ---")
    if result.error_message:
        print(f"Hata: {result.error_message}")
    elif result.cheapest_option:
        cheapest = result.cheapest_option
        print("🎉 En Ucuz Seçenek Bulundu! 🎉")
        print(f"Ürün: {cheapest.product_name}")
        print(f"Fiyat: {cheapest.price} TL")
        print(f"Market: {cheapest.market.name}")
        print(f"Mesafe: {cheapest.market.distance_km:.2f} km")
    else:
        print("Arama sonucunda bir şey bulunamadı.")
    print("--------------------")
    await client.close_client_session()

if __name__ == "__main__":
    asyncio.run(main_test())