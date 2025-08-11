# client.py (AttributeError Hatası Düzeltilmiş Final Versiyon)

import os
import asyncio
import httpx
from dotenv import load_dotenv
from typing import List, Optional, Dict, Any

# .env dosyasındaki değişkenleri yükle
load_dotenv()

# Gerekli modelleri import ediyoruz
# Not: models.py dosyasında bir değişiklik gerekmiyor.
from models import ApiSearchResponse, DetailedProductPrice

class MarketFiyatApiClient:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        
        self.nearest_url = os.getenv("NEAREST_API_URL")
        self.search_url = os.getenv("SEARCH_API_URL")
        
        if not self.nearest_url or not self.search_url:
            raise ValueError(".env dosyasında NEAREST_API_URL ve SEARCH_API_URL tanımlanmalıdır.")

    async def find_products_in_shopping_list(
        self, product_names: List[str], latitude: float, longitude: float, radius_km: int
    ) -> List[DetailedProductPrice]:
        # ADIM 1: Yarıçap İçindeki Marketleri Bul
        try:
            nearest_payload = {"latitude": latitude, "longitude": longitude, "distance": radius_km}
            response_nearest = await self.client.post(self.nearest_url, json=nearest_payload)
            response_nearest.raise_for_status()
            nearby_stores: List[Dict[str, Any]] = response_nearest.json()

            if not nearby_stores:
                print("Belirtilen alanda hiç market bulunamadı.")
                return []
            
            store_details_map = {store["id"]: store for store in nearby_stores}
            depot_ids = list(store_details_map.keys())

        except Exception as e:
            print(f"En yakın marketler aranırken hata oluştu: {e}")
            return []

        # ADIM 2: Bulunan Marketlerde Ürünleri Paralel Olarak Ara
        async def _search_one_product(product_name: str) -> Optional[ApiSearchResponse]:
            payload = {"keywords": product_name, "depots": depot_ids, "size": 20}
            try:
                response = await self.client.post(self.search_url, json=payload)
                response.raise_for_status()
                return ApiSearchResponse.model_validate(response.json())
            except Exception as e:
                print(f"'{product_name}' ürünü aranırken hata: {e}")
                return None
        
        tasks = [_search_one_product(name) for name in product_names]
        api_responses = await asyncio.gather(*tasks)

        all_found_prices: List[DetailedProductPrice] = []
        for response in api_responses:
            if response and response.content:
                for item in response.content:
                    for depot_info in item.product_depot_info_list:
                        # HATA BURADAYDI, ŞİMDİ DÜZELTİLDİ
                        # Pydantic nesnesinden veriye nokta ile erişiyoruz.
                        depot_id = depot_info.depot_id 
                        store_details = store_details_map.get(depot_id)
                        
                        if store_details:
                            distance_in_km = store_details.get("distance", 0) / 1000.0
                            
                            detailed_price = DetailedProductPrice(
                                product_title=item.title,
                                product_quantity=item.refined_quantity_unit,
                                price=depot_info.price,
                                unit_price=depot_info.unit_price,
                                market_name=depot_info.market_adi,
                                distance_km=distance_in_km
                            )
                            all_found_prices.append(detailed_price)
                            
        return all_found_prices

    async def close_client(self):
        await self.client.aclose()