# models.py
from pydantic import BaseModel, Field
from typing import List, Optional

class MarketInfo(BaseModel):
    """Bir marketin temel bilgilerini içeren model."""
    name: str = Field(..., description="Marketin adı (örn: 'A101', 'BİM').")
    address: Optional[str] = Field(None, description="Marketin açık adresi.")
    distance_km: float = Field(..., description="Kullanıcının konumuna olan uzaklığı (kilometre).")

class ProductPrice(BaseModel):
    """Bir marketteki tek bir ürünün fiyat bilgisini içeren model."""
    product_name: str = Field(..., description="Bulunan ürünün tam adı.")
    price: float = Field(..., description="Ürünün fiyatı (TL).")
    market: MarketInfo = Field(..., description="Bu fiyata sahip olan marketin bilgileri.")

class ProductSearchResult(BaseModel):
    """Bir ürün araması sonucunda döndürülecek tüm verileri kapsayan model."""
    search_query: str = Field(..., description="Araması yapılan orijinal ürün adı.")
    results: List[ProductPrice] = Field(..., description="Bulunan ürün fiyatlarının listesi, en ucuzdan pahalıya sıralı.")
    cheapest_option: Optional[ProductPrice] = Field(None, description="Bulunan en ucuz seçenek.")
    error_message: Optional[str] = Field(None, description="Bir hata oluştuysa hata mesajı.")