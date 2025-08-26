import requests
from bs4 import BeautifulSoup
import re
import os
from urllib.parse import urljoin
from typing import Optional

URL = "https://tonkiang.us"
CHANNEL = "ТНТ +2"
OUTPUT_FILE = "test.m3u"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible)"}


def fetch_page():
    r = requests.get(URL, timeout=30, headers=HEADERS)
    r.raise_for_status()
    return r.text


def extract_candidate_urls(html: str):
    soup = BeautifulSoup(html, "html.parser")

    candidates = set()

    # 1) Все <a href="...">
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href:
            continue
        full = urljoin(URL, href)
        candidates.add((full, a.get_text(strip=True) or ""))

    # 2) Все URL *.m3u8 в тексте страницы (включая скрипты/data-атрибуты)
    found = re.findall(r'https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*', html, flags=re.IGNORECASE)
    for u in found:
        candidates.add((u.strip(), ""))

    # 3) (редко) — ссылки, которые выглядят как udp:// или rtsp:// и т.п., если есть
    found2 = re.findall(r'(?:https?|rtsp|rtmp|udp)://[^\s"\'<>]+', html, flags=re.IGNORECASE)
    for u in found2:
        if ".m3u8" in u.lower():
            candidates.add((u.strip(), ""))

    # возвращаем список (url, text)
    return list(candidates)


def score_url(url: str, text: str) -> int:
    u = url.lower()
    t = text.lower()

    score = 0
    # строгое совпадение с искомым идентификатором канала
    if "ch_tnt_2" in u or "ch-tnt-2" in u or "ch+tnt+2" in u or "ch_tnt+2" in u:
        score += 50
    # явное упоминание tnt в урле или тексте
    if re.search(r'\btnt\b', u) or re.search(r'\btnt\b', t):
        score += 10
    # приоритет доменам провайдера/iptv.rt.ru
    if "iptv.rt.ru" in u or "svc.iptv" in u or "iptv.rt" in u:
        score += 30
    # hls / hlsstr в урле
    if "hls" in u or "hlsstr" in u:
        score += 5
    # обязательно m3u8
    if u.endswith(".m3u8") or ".m3u8" in u:
        score += 8

    # чуть повышаем для http/https
    if u.startswith("http://") or u.startswith("https://"):
        score += 1

    return score


def find_best_m3u8(candidates):
    best = None
    best_score = -1
    for url, text in candidates:
        sc = score_url(url, text)
        # print debug — можно раскомментировать при отладке
        # print("CAND:", sc, url, repr(text))
        if sc > best_score:
            best_score = sc
            best = url
    # если ничего с положительным баллом — попробуем любой .m3u8
    if best_score <= 0:
        for url, text in candidates:
            if ".m3u8" in url.lower():
                return url
        return None
    return best


def is_url_line(s: str) -> bool:
    s = s.strip()
    return bool(re.match(r'^(?:https?|rtsp|udp|srt)://', s, re.IGNORECASE))


def ensure_header(lines):
    if not lines or not lines[0].strip().upper().startswith("#EXTM3U"):
        return ["#EXTM3U\n"] + lines
    return lines


def write_or_update(channel_url: Optional[str]):
    # Если файла нет — создаём корректно
    if not os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            f.write(f"#EXTINF:-1,{CHANNEL}\n")
            if channel_url:
                f.write(channel_url + "\n")
        print("Создан новый test.m3u")
        if channel_url:
            print("Записан URL:", channel_url)
        else:
            print("URL для канала не найден.")
        return

    # Читаем файл
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    lines = ensure_header(lines)

    # Находим все теги #EXTINF с нашим каналом (без учета пробелов и регистра)
    extinf_indexes = [i for i, line in enumerate(lines)
                      if line.startswith("#EXTINF") and re.search(rf",\s*{re.escape(CHANNEL)}\s*$", line.strip(), flags=re.IGNORECASE)]

    # Если дублей — оставляем первый, удаляем остальные и их URL-строки
    if len(extinf_indexes) > 1:
        keep = extinf_indexes[0]
        for idx in reversed(extinf_indexes[1:]):
            del lines[idx]
            if idx < len(lines) and not lines[idx].startswith("#"):
                del lines[idx]
        extinf_indexes = [keep]

    # Если тег есть — обновляем/вставляем URL после него
    if extinf_indexes:
        i = extinf_indexes[0]
        if channel_url:
            if i + 1 < len(lines) and is_url_line(lines[i + 1]):
                lines[i + 1] = channel_url + "\n"
            else:
                lines.insert(i + 1, channel_url + "\n")
    else:
        # Тега нет — добавим в конец
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(f"#EXTINF:-1,{CHANNEL}\n")
        if channel_url:
            lines.append(channel_url + "\n")

    # Записываем обратно
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print("test.m3u обновлён.")
    if channel_url:
        print("Использован URL:", channel_url)
    else:
        print("URL для канала не найден; файл оставлен без изменения для ссылки.")


if __name__ == "__main__":
    html = fetch_page()
    candidates = extract_candidate_urls(html)
    best = find_best_m3u8(candidates)
    write_or_update(best)
