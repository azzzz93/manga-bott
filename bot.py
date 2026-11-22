import json
import os
import sys
import time

import requests

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


def make_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "fr-FR,fr;q=0.9",
    })
    # Une première visite pour récupérer les cookies de session
    s.get(DOMAIN, timeout=20)
    return s


def search(session, query):
    r = session.get(
        f"{DOMAIN}/api/v2/catalog/items",
        params={"search_text": query, "order": "newest_first", "per_page": 30},
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("items", [])


def price_of(item):
    p = item.get("price")
    if isinstance(p, dict):
        return f"{p.get('amount', '?')} {p.get('currency_code', '€')}"
    return f"{p} €" if p is not None else "?"


def send_discord(query, item):
    photo = (item.get("photo") or {}).get("url")
    embed = {
        "title": item.get("title", "Annonce"),
        "url": item.get("url") or f"{DOMAIN}/items/{item['id']}",
        "description": f"Recherche : **{query}**\nPrix : **{price_of(item)}**",
        "color": 0x09B1BA,
    }
    if item.get("size_title"):
        embed["description"] += f"\nTaille/info : {item['size_title']}"
    if item.get("status"):
        embed["description"] += f"\nÉtat : {item['status']}"
    if photo:
        embed["thumbnail"] = {"url": photo}

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
    session = make_session()
    ok, failed = 0, 0
    notified = set()

    for q in queries:
        try:
            items = search(session, q)
        except Exception as e:
            print(f"Échec pour '{q}' : {e}")
            failed += 1
            time.sleep(3)
            continue
        ok += 1

        ids = [str(i["id"]) for i in items]
        if q not in seen:
            # Première fois pour cette recherche : on mémorise sans notifier
            seen[q] = ids
        else:
            known = set(seen[q])
            for item in reversed(items):
                iid = str(item["id"])
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
