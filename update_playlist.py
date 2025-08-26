import requests
import re
import os

# raw-ссылка на исходный плейлист
SOURCE_URL = "https://raw.githubusercontent.com/blackbirdstudiorus/LoganetXIPTV/main/LoganetXAll.m3u"
# локальный файл (в твоём репо он называется test.m3u)
TARGET_FILE = "test.m3u"

# какие каналы ищем
CHANNEL_TAGS = ["ТНТ +2"]

def download_source():
    resp = requests.get(SOURCE_URL)
    resp.raise_for_status()
    return resp.text

def parse_channels(m3u_text):
    """Парсим все каналы из исходного .m3u"""
    lines = m3u_text.splitlines()
    channels = []
    current_info = None
    for line in lines:
        if line.startswith("#EXTINF"):
            current_info = line
        elif line.startswith("http"):
            if current_info:
                channels.append((current_info, line.strip()))
                current_info = None
    return channels

def filter_channels(channels, tags):
    """Фильтруем каналы по списку тегов"""
    result = []
    for info, url in channels:
        for tag in tags:
            if tag.lower() in info.lower():
                result.append((info, url))
    return result

def save_playlist(channels, target_file):
    """Сохраняем новый .m3u"""
    with open(target_file, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for info, url in channels:
            f.write(info + "\n")
            f.write(url + "\n")

def main():
    text = download_source()
    all_channels = parse_channels(text)
    wanted = filter_channels(all_channels, CHANNEL_TAGS)

    if not wanted:
        print("❌ Каналы не найдены")
        return

    save_playlist(wanted, TARGET_FILE)
    print(f"✅ Обновлено {len(wanted)} канал(ов) в {TARGET_FILE}")

if __name__ == "__main__":
    main()
