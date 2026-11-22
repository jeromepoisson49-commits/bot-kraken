import requests
import json
import os

CAPITAL_INITIAL = 500.0
FICHIER = "portefeuille.json"
FRAIS = 0.004
MISE_MAX = 50.0
MAX_POSITIONS = 2

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

def sauvegarder(p):
    with open(FICHIER, "w") as f:
        json.dump(p, f, indent=4)

def obtenir_prix():
    url = "https://api.kraken.com/0/public/Ticker"
    r = requests.get(url, params={"pair": ",".join(CRYPTOS)}, timeout=20)
    r.raise_for_status()
    data = r.json()

    if data["error"]:
        raise Exception(data["error"])

    return {
        paire: float(valeurs["c"][0])
        for paire, valeurs in data["result"].items()
    }

def main():
    p = charger()
    prix = obtenir_prix()

    print("\n--- SIMULATEUR KRAKEN ---")
    print(f"Euros disponibles : {p['euros']:.2f} €")

    for paire, cours in prix.items():
        position = p["positions"].get(paire)
        ancien = p["derniers_prix"].get(paire)

        print(f"{paire} : {cours:.6f} €")

        if position:
            achat = position["prix_achat"]

            if cours >= achat * 1.03 or cours <= achat * 0.97:
                montant = position["quantite"] * cours * (1 - FRAIS)
                p["euros"] += montant
                del p["positions"][paire]
                print(f"VENTE SIMULEE : {paire}")

        elif (
            ancien
            and cours <= ancien * 0.995
            and p["euros"] >= MISE_MAX
            and len(p["positions"]) < MAX_POSITIONS
        ):
            mise = MISE_MAX
            quantite = mise * (1 - FRAIS) / cours

            p["euros"] -= mise
            p["positions"][paire] = {
                "quantite": quantite,
                "prix_achat": cours
            }
            print(f"ACHAT SIMULE : {paire}")

        p["derniers_prix"][paire] = cours

    total = p["euros"]

    for paire, position in p["positions"].items():
        total += position["quantite"] * prix[paire]

    print(f"\nValeur totale : {total:.2f} €")
    print(f"Gain/perte : {total - CAPITAL_INITIAL:.2f} €")

    sauvegarder(p)

if __name__ == "__main__":
    main()
