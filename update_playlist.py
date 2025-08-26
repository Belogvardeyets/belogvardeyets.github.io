import requests
from bs4 import BeautifulSoup
import re
import os

URL = "https://tonkiang.us"
CHANNELS = ["ТНТ +2"]  # теги для поиска каналов

OUTPUT_FILE = "test.m3u"


def fetch_channels():
    response = requests.get(URL, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    links = [a["href"] for a in soup.find_all("a", href=True)]
    return links


def filter_channels(links, channels):
    found = {}
    for ch in channels:
        regex = re.compile(ch, re.IGNORECASE)
        for link in links:
            if regex.search(link):
                found[ch] = link
                break  # берём первую найденную ссылку
    return found


def write_or_update(found):
    if not os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            for ch in CHANNELS:
                url = found.get(ch, "")
                if url:
                    f.write(f"#EXTINF:-1,{ch}\n{url}\n")
        print("Создан новый test.m3u")
        return

    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#EXTINF") and "ТНТ +2" in line:
            new_lines.append(line)
            if "ТНТ +2" in found and i + 1 < len(lines):
                new_lines.append(found["ТНТ +2"] + "\n")
                i += 2
                continue
        new_lines.append(line)
        i += 1

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print("Обновлён test.m3u")


if __name__ == "__main__":
    links = fetch_channels()
    found = filter_channels(links, CHANNELS)
    write_or_update(found)
