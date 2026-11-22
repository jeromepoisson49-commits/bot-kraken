
import requests
import json
import os
from datetime import datetime, timezone

CAPITAL_INITIAL = 500.0
FICHIER = "portefeuille.json"
HISTORIQUE = "transactions.json"

FRAIS = 0.004
MISE_MAX = 50.0
MAX_POSITIONS = 2

CRYPTOS = ["XBTEUR", "ETHEUR", "SOLEUR", "XRPEUR", "ADAEUR"]

def charger_json(fichier, defaut):
    if os.path.exists(fichier):
        with open(fichier, "r") as f:
            return json.load(f)
    return defaut

def sauvegarder_json(fichier, donnees):
    with open(fichier, "w") as f:
        json.dump(donnees, f, indent=4)

def obtenir_prix():
    url = "https://api.kraken.com/0/public/Ticker"
    r = requests.get(
        url,
        params={"pair": ",".join(CRYPTOS)},
        timeout=20
    )
    r.raise_for_status()
    data = r.json()

    if data["error"]:
        raise Exception(data["error"])

    return {
        paire: float(valeurs["c"][0])
        for paire, valeurs in data["result"].items()
    }

def enregistrer_transaction(historique, transaction):
    transaction["date"] = datetime.now(timezone.utc).isoformat()
    historique.append(transaction)

def main():
    p = charger_json(FICHIER, {
        "euros": CAPITAL_INITIAL,
        "positions": {},
        "derniers_prix": {}
    })

    historique = charger_json(HISTORIQUE, [])
    prix = obtenir_prix()

    print("\n--- SIMULATEUR KRAKEN ---")
    print(f"Euros disponibles : {p['euros']:.2f} €")

    for paire, cours in prix.items():
        position = p["positions"].get(paire)
        ancien = p["derniers_prix"].get(paire)

        print(f"{paire} : {cours:.6f} €")

        if position:
            achat = position["prix_achat"]

            if cours >= achat * 1.015 or cours <= achat * 0.99:
                brut = position["quantite"] * cours
                frais = brut * FRAIS
                net = brut - frais

                cout_achat = position.get(
                    "cout_total",
                    position["quantite"] * achat
                )

                gain = net - cout_achat
                p["euros"] += net

                enregistrer_transaction(historique, {
                    "type": "VENTE",
                    "crypto": paire,
                    "quantite": position["quantite"],
                    "prix_achat": achat,
                    "prix_vente": cours,
                    "montant_eur": round(net, 2),
                    "frais_eur": round(frais, 2),
                    "gain_perte": round(gain, 2)
                })

                del p["positions"][paire]
                print(f"VENTE SIMULEE : {paire} | Gain/perte : {gain:.2f} €")

        elif (
            ancien
            and cours <= ancien * 0.995
            and p["euros"] >= MISE_MAX
            and len(p["positions"]) < MAX_POSITIONS
        ):
            mise = MISE_MAX
            frais = mise * FRAIS
            quantite = (mise - frais) / cours

            p["euros"] -= mise

            p["positions"][paire] = {
                "quantite": quantite,
                "prix_achat": cours,
                "cout_total": mise
            }

            enregistrer_transaction(historique, {
                "type": "ACHAT",
                "crypto": paire,
                "quantite": quantite,
                "prix_achat": cours,
                "montant_eur": round(mise, 2),
                "frais_eur": round(frais, 2)
            })

            print(f"ACHAT SIMULE : {paire} pour {mise:.2f} €")

        p["derniers_prix"][paire] = cours

    total = p["euros"]

    for paire, position in p["positions"].items():
        total += position["quantite"] * prix[paire]

    print(f"\nValeur totale : {total:.2f} €")
    print(f"Gain/perte total : {total - CAPITAL_INITIAL:.2f} €")
    print(f"Transactions enregistrées : {len(historique)}")

    sauvegarder_json(FICHIER, p)
    sauvegarder_json(HISTORIQUE, historique)

if __name__ == "__main__":
    main()
