
import json, requests

class SongCategory:
    UNKNOWN = 0
    INSTRUMENTAL = 1
    CHANTING = 2
    CHARACTER = 3
    STANDARD = 4

def main():
    print("Fetching library...")
    r = requests.get("https://animemusicquiz.com/libraryMasterList")

    if not r.ok:
        print(f"Failed to request master list from AMQ: {r.status_code}")
        return

    print("Decoding library...")
    library = r.json()
    results = []

    print("Finding songs...")
    for song_id in library['songMap']:
        if library['songMap'][song_id]['category'] == SongCategory.CHANTING:
            results.append(song_id)

    print("Writing output...")
    with open("chanting.txt", 'w') as f:
        f.write('\n'.join(results))

    print("Done!")

if __name__ == "__main__":
    main()
