from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from config import PROXY_URL

class ParserDiagnosticError(Exception):
    pass

def ensure_sorted_by_date(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    params["s"] = ["104"]
    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))

async def fetch_ads(url: str) -> list[dict]:
    target_url = ensure_sorted_by_date(url)
    proxies = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None

    try:
        async with AsyncSession(impersonate="chrome120", proxies=proxies, timeout=20) as session:
            response = await session.get(target_url)
    except Exception as e:
        raise ParserDiagnosticError(
            f"❌ Ошибка сети или прокси: не удалось подключиться к Авито.\n"
            f"Проверьте баланс/работоспособность прокси. Детали: {e}"
        )

    if response.status_code in (403, 429):
        raise ParserDiagnosticError(
            f"🚫 Авито временно ограничил доступ (код {response.status_code}).\n"
            f"Решение: смените IP на мобильном прокси или проверьте настройки ротации."
        )
    elif response.status_code != 200:
        raise ParserDiagnosticError(
            f"⚠️ Авито вернул нестандартный ответ (код {response.status_code})."
        )

    soup = BeautifulSoup(response.text, "html.parser")
    items = soup.select('[data-marker="item"]')

    if not items:
        raise ParserDiagnosticError(
            "⚠️ Страница Авито загрузилась, но объявлений найдено 0.\n"
            "Возможные причины: по ссылке действительно нет товаров, вылезла капча, "
            "или Авито обновил верстку сайта (требуется обновление парсера)."
        )

    ads = []
    for item in items:
        ad_id = item.get("data-item-id")
        if not ad_id:
            continue

        title_el = item.select_one('[itemprop="name"]')
        title = title_el.get_text(strip=True) if title_el else "Без названия"

        price_el = item.select_one('[itemprop="price"]')
        price = price_el.get("content") if price_el else None
        price_text = f"{int(price):,} ₽".replace(",", " ") if price and price.isdigit() else "Цена не указана"

        link_el = item.select_one('a[data-marker="item-title"]')
        href = link_el.get("href", "") if link_el else ""
        full_url = f"https://avito.ru{href}" if href.startswith("/") else href

        img_el = item.select_one("img")
        photo = img_el.get("src") if img_el else None

        ads.append({
            "id": str(ad_id),
            "title": title,
            "price": price_text,
            "url": full_url,
            "photo": photo
        })
    return ads
