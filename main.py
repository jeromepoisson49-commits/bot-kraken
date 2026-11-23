
import requests
import json
import os
import time
from datetime import datetime, timezone

CAPITAL_INITIAL = 500.0
FICHIER = "portefeuille.json"
HISTORIQUE = "transactions.json"

FRAIS = 0.0
MISE_MAX = 10.0
MAX_POSITIONS = 4
INTERVALLE_SECONDES = 60
BAISSE_ACHAT = 0.001  # 0,10 %

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


def executer_cycle(p, historique):
    prix = obtenir_prix()

    print("\n--- SIMULATEUR KRAKEN | CYCLE 1 MINUTE ---")
    print(f"Euros disponibles : {p['euros']:.2f} €")
    print(f"Positions ouvertes : {len(p['positions'])}/{MAX_POSITIONS}")

    for paire, cours in prix.items():
        position = p["positions"].get(paire)
        ancien = p["derniers_prix"].get(paire)

        print(f"{paire} : {cours:.6f} €")

        # GESTION DES VENTES
        if position:
            achat = position["prix_achat"]

            if cours >= achat * 1.015 or cours <= achat * 0.99:
                montant_vente = position["quantite"] * cours
                cout_achat = position.get(
                    "cout_total",
                    position["quantite"] * achat
                )
                gain = montant_vente - cout_achat

                p["euros"] += montant_vente

                enregistrer_transaction(historique, {
                    "type": "VENTE",
                    "crypto": paire,
                    "quantite": position["quantite"],
                    "prix_achat": achat,
                    "prix_vente": cours,
                    "montant_eur": round(montant_vente, 2),
                    "frais_eur": 0.0,
                    "gain_perte": round(gain, 2)
                })

                del p["positions"][paire]

                print(
                    f"VENTE SIMULEE : {paire} "
                    f"| Gain/perte : {gain:.2f} €"
                )

        # GESTION DES ACHATS
        elif (
            ancien is not None
            and cours <= ancien * (1 - BAISSE_ACHAT)
            and p["euros"] >= MISE_MAX
            and len(p["positions"]) < MAX_POSITIONS
        ):
            mise = MISE_MAX
            quantite = mise / cours

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
                "frais_eur": 0.0
            })

            print(f"ACHAT SIMULE : {paire} pour {mise:.2f} €")

        p["derniers_prix"][paire] = cours

    # CALCUL DU PORTEFEUILLE
    total = p["euros"]

    for paire, position in p["positions"].items():
        if paire in prix:
            total += position["quantite"] * prix[paire]

    print(f"\nValeur totale : {total:.2f} €")
    print(f"Gain/perte total : {total - CAPITAL_INITIAL:.2f} €")
    print(f"Transactions enregistrées : {len(historique)}")

    sauvegarder_json(FICHIER, p)
    sauvegarder_json(HISTORIQUE, historique)



def main():
    p = charger_json(FICHIER, {
        "euros": CAPITAL_INITIAL,
        "positions": {},
        "derniers_prix": {}
    })

    p.setdefault("positions", {})
    p.setdefault("derniers_prix", {})

    historique = charger_json(HISTORIQUE, [])

    print("Démarrage du simulateur Kraken.")
    print("Frais simulés : 0 €.")
    print("Aucun ordre réel ne sera envoyé.")

    try:
        executer_cycle(p, historique)
        print("Cycle terminé avec succès.")
    except Exception as erreur:
        print(f"Erreur : {erreur}")
        raise


if __name__ == "__main__":
    main()

