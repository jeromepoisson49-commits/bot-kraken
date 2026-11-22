import requests
import json
import os

CAPITAL_INITIAL = 500.0
FICHIER = "portefeuille.json"

CRYPTOS = ["XBTEUR", "ETHEUR", "SOLEUR", "XRPEUR", "ADAEUR"]

def charger():
    if os.path.exists(FICHIER):
        with open(FICHIER, "r") as f:
            return json.load(f)

    return {
        "euros": CAPITAL_INITIAL,
        "positions": {},
        "derniers_prix": {}
    }

def sauvegarder(portefeuille):
    with open(FICHIER, "w") as f:
        json.dump(portefeuille, f, indent=4)

def obtenir_prix():
    url = "https://api.kraken.com/0/public/Ticker"
    reponse = requests.get(
        url,
        params={"pair": ",".join(CRYPTOS)},
        timeout=20
    )
    reponse.raise_for_status()
    donnees = reponse.json()

    if donnees["error"]:
        raise Exception(donnees["error"])

    prix = {}
    for paire, valeurs in donnees["result"].items():
        prix[paire] = float(valeurs["c"][0])

    return prix

def valeur_portefeuille(p, prix):
    total = p["euros"]
    for paire, position in p["positions"].items():
        total += position["quantite"] * prix[paire]
    return total

def main():
    p = charger()
    prix = obtenir_prix()

    print("\n--- SIMULATEUR KRAKEN ---")
    print(f"Euros disponibles : {p['euros']:.2f} €")

    for paire, cours in prix.items():
        print(f"{paire} : {cours:.6f} €")

        position = p["positions"].get(paire)
        ancien = p["derniers_prix"].get(paire)

        if position:
            prix_achat = position["prix_achat"]

            if cours >= prix_achat * 1.03:
                montant = position["quantite"] * cours
                p["euros"] += montant
                del p["positions"][paire]
                print(f"VENTE SIMULEE : {paire} pour {montant:.2f} €")

        elif ancien and cours <= ancien * 0.97 and p["euros"] >= 50:
            mise = min(50, p["euros"])
            quantite = mise / cours

            p["euros"] -= mise
            p["positions"][paire] = {
                "quantite": quantite,
                "prix_achat": cours
            }
            print(f"ACHAT SIMULE : {paire} pour {mise:.2f} €")

        p["derniers_prix"][paire] = cours

    total = valeur_portefeuille(p, prix)
    print(f"\nValeur totale : {total:.2f} €")
    print(f"Gain/perte : {total - CAPITAL_INITIAL:.2f} €")

    sauvegarder(p)

if __name__ == "__main__":
    main()
