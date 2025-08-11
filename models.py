# models.py (Tüm Düzeltmeleri İçeren Final Versiyon)

from pydantic import BaseModel, Field
from typing import List, Optional

# ==============================================================================
# BÖLÜM 1: API Yanıt Modelleri
# Bu modeller, marketfiyati.org.tr API'sinden gelen JSON verisini birebir karşılar.
# ==============================================================================

class ProductDepotInfo(BaseModel):
    """
    API'den gelen, bir ürünün tek bir marketteki fiyat ve konum bilgisidir.
    """
    # DÜZELTME: API'den gelen 'depotId' (camelCase) alanını Python'daki
    # 'depot_id' (snake_case) özelliğine bağlamak için alias eklendi.
    depot_id: str = Field(..., alias="depotId")
    
    price: float
    unit_price: Optional[str] = Field(None, alias="unitPrice")
    market_adi: str = Field(..., alias="marketAdi")
    latitude: float
    longitude: float

class ContentItem(BaseModel):
    """
    API'den gelen, bir ürünün genel bilgilerini ve tüm marketlerdeki 
    fiyatlarını içeren ana model.
    """
    title: str
    brand: Optional[str] = None
    refined_quantity_unit: Optional[str] = Field(None, alias="refinedQuantityUnit")
    product_depot_info_list: List[ProductDepotInfo] = Field(..., alias="productDepotInfoList")

class ApiSearchResponse(BaseModel):
    """
    API'nin /search uç noktasından dönen tüm yanıtı kapsayan üst model.
    """
    content: List[ContentItem]


# ==============================================================================
# BÖLÜM 2: İç İşlem Modeli
# API'den alınan veriyi işleyip, mesafe gibi ek bilgilerle zenginleştirdiğimiz model.
# ==============================================================================

class DetailedProductPrice(BaseModel):
    """
    Tüm marketlerden toplanan, mesafe bilgisi eklenmiş, temiz ve detaylı 
    ürün fiyatı modeli. Client'tan server'a bu formatta veri aktarılır.
    """
    product_title: str
    product_quantity: Optional[str] = None
    price: float
    unit_price: Optional[str] = None
    market_name: str
    distance_km: Optional[float] = None


# ==============================================================================
# BÖLÜM 3: Araç Çıktı Modeli
# MCP aracımızın n8n Agent'ına döndürdüğü nihai sonuç modeli.
# ==============================================================================

class ShoppingListResult(BaseModel):
    """
    'find_shopping_list_prices' aracının çıktısını tanımlar. Bu çıktı, 
    insan tarafından okunabilir bir özet veya bir hata mesajı içerir.
    """
    summary: Optional[str] = Field(None, description="Bulunan ürünlerin özetlendiği, formatlanmış metin.")
    found_prices_count: int = Field(description="Bulunan toplam fiyat sayısı.")
    error_message: Optional[str] = Field(None, description="Bir hata oluştuysa veya hiçbir ürün bulunamadıysa hata mesajı.")