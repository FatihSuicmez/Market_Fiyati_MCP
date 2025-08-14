# models.py (Resim gösterme özelliği için güncellenmiş Final Versiyon)

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
    # GÜNCELLEME: API'den gelen resim adresini yakalamak için eklendi.
    image_url: Optional[str] = Field(None, alias="imageUrl")
    refined_quantity_unit: Optional[str] = Field(None, alias="refinedQuantityUnit")
    product_depot_info_list: List[ProductDepotInfo] = Field(..., alias="productDepotInfoList")

class ApiSearchResponse(BaseModel):
    """
    API'nin /search uç noktasından dönen tüm yanıtı kapsayan üst model.
    """
    content: List[ContentItem]


# ==============================================================================
# BÖLÜM 2: İç İşlem Modeli
# API'den alınan veriyi işleyip, mesafe ve resim gibi ek bilgilerle zenginleştirdiğimiz model.
# ==============================================================================

class DetailedProductPrice(BaseModel):
    """
    Tüm marketlerden toplanan, mesafe ve resim bilgisi eklenmiş, temiz ve detaylı 
    ürün fiyatı modeli. Bu yapı n8n'e gönderilecek.
    """
    product_title: str
    product_quantity: Optional[str] = None
    price: float
    unit_price: Optional[str] = None
    market_name: str
    distance_km: Optional[float] = None
    # GÜNCELLEME: Resim bilgisini n8n'e taşımak için eklendi.
    image_url: Optional[str] = None


# ==============================================================================
# BÖLÜM 3: Araç Çıktı Modeli
# MCP aracımızın n8n Agent'ına döndürdüğü nihai sonuç modeli.
# ==============================================================================

class ShoppingListResult(BaseModel):
    """
    'find_shopping_list_prices' aracının çıktısını tanımlar. Bu çıktı,
    n8n'in işleyeceği bir ürün listesi veya bir hata mesajı içerir.
    """
    # GÜNCELLEME: 'summary' alanı kaldırıldı, yerine 'products' listesi geldi.
    products: List[DetailedProductPrice] = Field(description="Bulunan ürünlerin detaylı listesi.")
    found_prices_count: int = Field(description="Bulunan toplam fiyat sayısı.")
    error_message: Optional[str] = Field(None, description="Bir hata oluştuysa veya hiçbir ürün bulunamadıysa hata mesajı.")