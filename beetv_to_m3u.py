#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
beetv_to_m3u.py
Попытка извлечь каналы и потоки со страницы collection Beetv и собрать .m3u.
Запускай локально на Mac. Требует requests и beautifulsoup4 (pip install requests bs4).
"""

import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# измените на нужную страницу коллекции
PAGE_URL = "https://beetv.kz/ru-KZ/collections/besplatnye-top-kanaly-klientam-beeline"
OUTPUT_FILE = "beetv_free.m3u"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
}

# Популярные возможные API-путёвки (скрипт будет пробовать их)
API_CANDIDATES = [
    "https://api.beetv.kz/channels/{id}",
    "https://api.beetv.kz/content/channels/{id}",
    "https://api.beetv.kz/v1/channels/{id}",
    "https://api.beetv.kz/v2/channels/{id}",
    "https://api.beetv.kz/media/channels/{id}",
    "https://api.beetv.kz/players/{id}",       # иногда плейер в отдельном endpoint
    "https://api.beetv.kz/playlist/{id}",
]

def get_page_html(url):
    print("GET page:", url)
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.text

def extract_ssr_cache(html):
    """
    Ищем в HTML JS-переменную window._SSR_CACHE_ или похожую JSON-структуру.
    Возвращает parsed JSON or None.
    """
    # Попробуем найти window._SSR_CACHE_ = { ... };
    m = re.search(r'window\._SSR_CACHE_\s*=\s*({.*?});', html, flags=re.S)
    if not m:
        # Иногда JSON может быть вложен в <script> … </script> в другом формате
        soup = BeautifulSoup(html, "html.parser")
        scripts = soup.find_all("script")
        for s in scripts:
            txt = s.string
            if not txt:
                continue
            if "window._SSR_CACHE_" in txt:
                mm = re.search(r'window\._SSR_CACHE_\s*=\s*({.*?});', txt, flags=re.S)
                if mm:
                    m = mm
                    break
    if not m:
        return None
    raw = m.group(1)
    # Бывают неэкранированные слэши — попытаемся безопасно распарсить
    try:
        data = json.loads(raw)
        return data
    except Exception:
        # Попытка почистить: заменить одиночные ключи и т.п.
        try:
            # убираем js-стиль комментариев и т.д.
            clean = re.sub(r'//.*?\n', '', raw)
            data = json.loads(clean)
            return data
        except Exception:
            print("Не удалось распарсить window._SSR_CACHE_ как JSON.")
            return None

def find_channel_refs_from_ssr(ssr_json):
    """
    Ищем в ssr_json ключ card_collection и вытаскиваем объекты с resource_type == 'channel'
    Возвращаем список dict с полями name, resource_id, uri, deeplink, images.
    """
    results = []
    if not isinstance(ssr_json, dict):
        return results
    # Ищем ключ 'card_collection' внутри любого уровня
    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "card_collection" and isinstance(v, dict):
                    for coll_name, arr in v.items():
                        # arr: список записей (каждая — объект с response->data)
                        for item in arr:
                            try:
                                resp = item.get("response", {}).get("data", {})
                                # в resp внутри может быть структура с карточками
                                # ищем карточки внутри resp
                                if isinstance(resp, dict):
                                    # если это сама коллекция — в ней могут быть карточки где-то глубже
                                    # но часто там есть 'cards' / 'items' / 'data' keys. Попробуем рекурсивно
                                    pass
                            except Exception:
                                pass
                else:
                    walk(v)
        elif isinstance(obj, list):
            for el in obj:
                walk(el)
    # Простая (эффективная) стратегия: поиск по шаблону 'resource_type": "channel"' в сериализованном JSON
    txt = json.dumps(ssr_json)
    for match in re.finditer(r'\{[^}]{0,8000}?"resource_type"\s*:\s*"(channel|channel_group)"[^}]*\}', txt):
        jsn = match.group(0)
        try:
            dd = json.loads(jsn)
            name = dd.get("name") or dd.get("additional_name") or dd.get("title") or dd.get("card_collection", {}).get("name")
            resource_id = dd.get("resource_id") or dd.get("resourceId") or dd.get("id")
            uri = dd.get("uri")
            deeplink = dd.get("deeplink")
            results.append({"name": name, "resource_id": resource_id, "uri": uri, "deeplink": deeplink, "raw": dd})
        except Exception:
            continue
    # Уберём дубликаты по resource_id
    uniq = {}
    for r in results:
        rid = r.get("resource_id") or r.get("uri") or r.get("deeplink") or json.dumps(r.get("raw", {}))
        uniq[rid] = r
    return list(uniq.values())

def try_api_for_channel(resource_id):
    """
    Попробуем запросить несколько candidate API endpoints и найти в ответе поля со ссылками на потоки.
    Возвращаем список найденных ссылок (можно пустой).
    """
    found = []
    for tmpl in API_CANDIDATES:
        url = tmpl.format(id=resource_id)
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                # print("  ->", url, "status", r.status_code)
                continue
            j = None
            try:
                j = r.json()
            except Exception:
                # если не JSON, то посмотрим текст на наличие m3u8
                text = r.text
                for m in re.findall(r'https?://[^\s"\']+\.m3u8[^\s"\']*', text):
                    found.append(m)
                continue
            # ищем в JSON ключи с возможными URL-ами
            txt = json.dumps(j)
            # 1) явные .m3u8
            for m in re.findall(r'https?://[^\s"\']+\.m3u8[^\s"\']*', txt):
                if m not in found:
                    found.append(m)
            # 2) url fields like "streamUrl", "url", "playlist", "sources"
            candidates = []
            if isinstance(j, dict):
                # поиск по ключам
                def walk(obj):
                    if isinstance(obj, dict):
                        for k, v in obj.items():
                            if isinstance(v, str):
                                if v.startswith("http"):
                                    candidates.append(v)
                            else:
                                walk(v)
                    elif isinstance(obj, list):
                        for el in obj:
                            walk(el)
                walk(j)
            for c in candidates:
                if (".m3u8" in c or "/live/" in c or c.endswith(".ts") or c.endswith(".mp4")) and c not in found:
                    found.append(c)
            # если нашлось — возвращаем (но продолжаем другие endpoints, чтобы собрать вариации)
        except Exception as e:
            # print("err", e)
            continue
    return found

def main():
    html = get_page_html(PAGE_URL)
    ssr = extract_ssr_cache(html)
    channels = []
    if ssr:
        channels = find_channel_refs_from_ssr(ssr)
        print(f"Найдено каналов в SSR_CACHE: {len(channels)}")
    else:
        print("Не найдено window._SSR_CACHE_ — попытаемся простой парсинг HTML элементов.")
        # fallback: парсим <a href="/channels/..." />
        soup = BeautifulSoup(html, "html.parser")
        links = soup.select("a[href^='/channels/']")
        for a in links:
            href = a.get("href")
            txt = a.get_text(strip=True)
            channels.append({"name": txt, "uri": href, "resource_id": None, "deeplink": None})
    # Для отладки: выведем первые 20 каналов
    for i, ch in enumerate(channels[:50], 1):
        print(f"{i}. {ch.get('name')!s} id={ch.get('resource_id')!s} uri={ch.get('uri')!s} deeplink={ch.get('deeplink')!s}")

    # Попытка опроса API для каждого найденного resource_id (если resource_id нет, можно разобрать uri)
    playlist_entries = []
    for ch in channels:
        rid = ch.get("resource_id")
        title = ch.get("name") or ch.get("uri") or ch.get("deeplink") or "Unknown"
        urls = []
        if rid:
            print("Пытаюсь API по id:", rid)
            urls = try_api_for_channel(rid)
        if not urls and ch.get("uri"):
            # Если uri выглядит как '/channels/<slug>' — попробуем получить slug и вызвать API с ним
            slug = ch.get("uri").strip("/").split("/")[-1]
            print("Пытаюсь API по slug:", slug)
            # попробуем несколько candidate endpoints с slug
            for tmpl in ("https://api.beetv.kz/channels/slug/{s}", "https://api.beetv.kz/channels/{s}", "https://api.beetv.kz/content/channels/slug/{s}"):
                url = tmpl.format(s=slug)
                try:
                    r = requests.get(url, headers=HEADERS, timeout=8)
                    if r.status_code == 200:
                        # поиск ссылок в тексте/JSON
                        txt = r.text
                        for m in re.findall(r'https?://[^\s"\']+\.m3u8[^\s"\']*', txt):
                            if m not in urls:
                                urls.append(m)
                except Exception:
                    pass
        # финальная попытка: поиск m3u8 прямо в HTML-странице канала
        if not urls and ch.get("uri"):
            page_url = urljoin(PAGE_URL, ch.get("uri"))
            try:
                r = requests.get(page_url, headers=HEADERS, timeout=8)
                # на странице канала могут быть прямые ссылки или JSON с плейлистом
                for m in re.findall(r'https?://[^\s"\']+\.m3u8[^\s"\']*', r.text):
                    if m not in urls:
                        urls.append(m)
            except Exception:
                pass

        if urls:
            for u in urls:
                playlist_entries.append({"title": title, "url": u})
                print("  -> найден поток:", u)
        else:
            print("  -> не найдено потоков для", title)

    # Записываем m3u
    if playlist_entries:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for e in playlist_entries:
                # простая запись; при желании можно добавить tvg-id, group-title и т.д.
                f.write(f"#EXTINF:-1,{e['title']}\n")
                f.write(e['url'] + "\n")
        print("Плейлист записан в", OUTPUT_FILE, "с", len(playlist_entries), "записями.")
    else:
        print("Не удалось найти ни одного потока. См. логи выше для диагностики.")

if __name__ == "__main__":
    main()
