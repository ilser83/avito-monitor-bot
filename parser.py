import asyncio
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from config import PROXY_URL, PROXY_ROTATE_URL

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://avito.ru",
}

async def rotate_proxy_ip():
    if not PROXY_ROTATE_URL:
        return False
    try:
        async with AsyncSession(timeout=15) as session:
            await session.get(PROXY_ROTATE_URL)
        await asyncio.sleep(7)
        return True
    except Exception as e:
        print(f"[Rotate IP Error] {e}", flush=True)
        return False

async def fetch_ads(url: str) -> list[dict]:
    proxies = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None
    for attempt in range(2):
        async with AsyncSession(impersonate="chrome124", proxies=proxies, timeout=25) as session:
            resp = await session.get(url, headers=HEADERS)
            if resp.status_code in (403, 429):
                if attempt == 0 and await rotate_proxy_ip():
                    continue
                raise RuntimeError(f"Авито временно ограничил доступ (код {resp.status_code}). Проверьте ротацию IP мобильного прокси.")
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            ads = []
            for item in soup.select("[data-marker=\"item\"]"):
                ad_id = item.get("data-item-id")
                if not ad_id:
                    continue
                title_el = item.select_one("[itemprop=\"name\"], [data-marker=\"item-title\"]")
                price_el = item.select_one("[itemprop=\"price\"]")
                link_el = item.select_one("a[data-marker=\"item-title\"], a[itemprop=\"url\"]")
                img_el = item.select_one("img")
                title = title_el.get_text(strip=True) if title_el else "Без названия"
                price_val = price_el.get("content") if price_el and price_el.get("content") else (price_el.get_text(strip=True) if price_el else "Цена не указана")
                if price_val.isdigit():
                    price_val = f"{int(price_val):,} ₽".replace(",", " ")
                href = link_el.get("href", "") if link_el else ""
                full_url = f"https://avito.ru{href}" if href.startswith("/") else href
                photo = img_el.get("src") or img_el.get("data-src") if img_el else None
                ads.append({"id": str(ad_id), "title": title, "price": price_val, "url": full_url, "photo": photo})
            return ads
    return []
