import json
import os
import subprocess
import sys
import time

import requests

# La bibliothèque vinted-scraper est installée automatiquement si besoin.
try:
    from vinted_scraper import VintedScraper
except ImportError:
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--quiet", "vinted-scraper"]
    )
    from vinted_scraper import VintedScraper

# Le lien du webhook Discord est lu depuis un secret, jamais écrit ici.
WEBHOOK = os.environ.get("DISCORD_WEBHOOK", "")

DOMAIN = "https://www.vinted.fr"
SEEN_FILE = "seen.json"

# Ta liste de recherches (les doublons sont retirés automatiquement)
SERIES = [
    # Moonlight Act
    "moonlight act", "moonlight-act",
    # Kurosagi
    "kurosagi", "kurosagi livraison de cadavres",
    # Inspecteur Kurokôchi
    "inspecteur kurokochi", "kurokochi", "kurokouchi", "kurokôchi",
    # Ki-itchi
    "ki itchi", "ki-itchi", "kiitchi", "ki-ichi", "kiichi",
    # Bokurano
    "bokurano", "bokurano ours",
    # Ultra Heaven
    "ultra heaven",
    # Karakuri Circus
    "karakuri circus", "karakuri",
    # Sôbôtei
    "sou bou tei", "soubou tei", "soubôtei", "sôbôtei", "soubotei",
    # L'Habitant de l'infini
    "l'habitant de l'infini", "habitant de l'infini", "mugen no juunin",
    # Mai Wai
    "mai wai", "maiwai",
    # Gokusen
    "gokusen",
    # Gantz
    "gantz",
    # Homunculus
    "homunculus",
    # Green Blood
    "green blood",
    # MPD Psycho
    "mpd psycho", "mpd-psycho", "multiple personality detective psycho",
    # Bestiarius
    "bestiarius", "bestiarus",
    # Ichi the Killer
    "ichi the killer", "koroshiya ichi", "koroshiya 1",
    # I Am a Hero
    "i am a hero", "i'm a hero manga",
    # Divers
    "rainbow manga",
    "integral manga", "intégrale manga",
    "catalogue angouleme", "catalogue angoulême",
    "freesia",
    # Atsushi Kaneko
    "atsushi kaneko", "kaneko atsushi",
]


def g(obj, name, default=None):
    """Lit un champ, que l'objet soit un dictionnaire ou un objet."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def search(scraper, query):
    items = scraper.search(
        {"search_text": query, "order": "newest_first", "per_page": 30}
    )
    return list(items or [])


def price_of(item):
    p = g(item, "price")
    if p is None:
        return "?"
    if isinstance(p, (str, int, float)):
        return f"{p} €"
    amount = g(p, "amount", "?")
    cur = g(p, "currency_code", "€")
    return f"{amount} {cur}"


def item_url(item):
    url = g(item, "url") or ""
    if url.startswith("/"):
        url = DOMAIN + url
    return url or f"{DOMAIN}/items/{g(item, 'id')}"


def send_discord(query, item):
    photo = g(item, "photo")
    photo_url = g(photo, "url") or g(photo, "full_size_url")
    embed = {
        "title": g(item, "title", "Annonce"),
        "url": item_url(item),
        "description": f"Recherche : **{query}**\nPrix : **{price_of(item)}**",
        "color": 0x09B1BA,
    }
    size = g(item, "size_title")
    status = g(item, "status")
    if size:
        embed["description"] += f"\nTaille/info : {size}"
    if status:
        embed["description"] += f"\nÉtat : {status}"
    if photo_url:
        embed["thumbnail"] = {"url": photo_url}

    for _ in range(3):
        r = requests.post(WEBHOOK, json={"embeds": [embed]}, timeout=20)
        if r.status_code == 429:
            time.sleep(float(r.json().get("retry_after", 2)) + 0.5)
            continue
        break
    time.sleep(1)


def main():
    if not WEBHOOK:
        print("Le secret DISCORD_WEBHOOK est vide.")
        sys.exit(1)

    seen = {}
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, encoding="utf-8") as f:
            seen = json.load(f)

    queries = list(dict.fromkeys(q.strip().lower() for q in SERIES))

    try:
        scraper = VintedScraper(DOMAIN)
    except Exception as e:
        print(f"Impossible de se connecter à Vinted : {e}")
        sys.exit(1)

    ok, failed = 0, 0
    notified = set()

    for q in queries:
        try:
            items = search(scraper, q)
        except Exception as e:
            print(f"Échec pour '{q}' : {e}")
            failed += 1
            time.sleep(3)
            continue
        ok += 1

        ids = [str(g(i, "id")) for i in items]
        if q not in seen:
            # Première fois pour cette recherche : on mémorise sans notifier
            seen[q] = ids
        else:
            known = set(seen[q])
            for item in reversed(items):
                iid = str(g(item, "id"))
                if iid not in known and iid not in notified:
                    notified.add(iid)
                    send_discord(q, item)
            seen[q] = list(dict.fromkeys(ids + seen[q]))[:300]
        time.sleep(3)

    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen, f, ensure_ascii=False)

    print(f"Terminé : {ok} recherches réussies, {failed} échecs.")
    if ok == 0:
        # GitHub t'enverra un e-mail si tout échoue (ex. blocage par Vinted)
        sys.exit(1)


if __name__ == "__main__":
    main()
