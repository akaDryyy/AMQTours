def getTourlist(TOURLIST_PATH):
    tourlist = []
    with open(TOURLIST_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            url = line.strip()
            if url not in tourlist:
                tourlist.append(url)
    return tourlist