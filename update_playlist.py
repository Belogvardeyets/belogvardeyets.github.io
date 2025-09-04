import requests
import os

# список raw-ссылок на исходные плейлисты
SOURCE_URLS = [
    "https://raw.githubusercontent.com/blackbirdstudiorus/LoganetXIPTV/main/LoganetXAll.m3u",
    # можно добавить ещё ссылки сюда
    "https://smolnp.github.io/IPTVru//IPTVru.m3u",
    "https://iptv-org.github.io/iptv/index.m3u",
    # "https://example.com/playlist3.m3u",
]

# локальный файл (куда сохраняем результат)
TARGET_FILE = "test.m3u"

# какие каналы ищем (через запятую)
CHANNEL_TAGS = ["ТНТ", "первый канал"]

def download_source(url):
    """Скачиваем плейлист по ссылке"""
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.text

def parse_channels(m3u_text):
    """Парсим все каналы из .m3u"""
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
                break  # чтобы один канал не дублировался, если подходит под несколько тегов
    return result

def save_playlist(channels, target_file):
    """Сохраняем новый .m3u"""
    with open(target_file, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for info, url in channels:
            f.write(info + "\n")
            f.write(url + "\n")

def main():
    all_channels = []

    # собираем все каналы со всех плейлистов
    for url in SOURCE_URLS:
        try:
            text = download_source(url)
            all_channels.extend(parse_channels(text))
            print(f"📥 Загружено из {url}")
        except Exception as e:
            print(f"⚠️ Ошибка загрузки {url}: {e}")

    # фильтруем только нужные
    wanted = filter_channels(all_channels, CHANNEL_TAGS)

    if not wanted:
        print("❌ Каналы не найдены")
        return

    # сохраняем в файл
    save_playlist(wanted, TARGET_FILE)
    print(f"✅ Обновлено {len(wanted)} канал(ов) в {TARGET_FILE}")

if __name__ == "__main__":
    main()
