def extract_candidate_urls(html: str):
    soup = BeautifulSoup(html, "html.parser")

    candidates = set()

    # только ссылки содержащие .m3u8
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href:
            continue
        if ".m3u8" not in href.lower():
            continue
        if " " in href:  # отбрасываем кривые ссылки с пробелами
            continue
        full = urljoin(URL, href)
        candidates.add((full, a.get_text(strip=True) or ""))

    # ищем все .m3u8 прямо в тексте страницы
    found = re.findall(r'https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*', html, flags=re.IGNORECASE)
    for u in found:
        if " " in u:
            continue
        candidates.add((u.strip(), ""))

    return list(candidates)
