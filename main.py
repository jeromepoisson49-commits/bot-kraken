
import requests
import json
import os
import time
from datetime import datetime, timezone

# ==========================================
# CONFIGURATION
# ==========================================

CAPITAL_INITIAL = 500.0
MISE_PAR_POSITION = 10.0

FRAIS = 0.0
BAISSE_MIN = 0.001
MULTIPLICATEUR_VOLUME = 1.5
OBJECTIF_VENTE = 0.008

INTERVALLE = 60

FICHIER_PORTEFEUILLE = "portefeuille.json"
FICHIER_HISTORIQUE = "transactions.json"

CRYPTOS = [
    "XBTEUR",
    "ETHEUR",
    "SOLEUR",
    "XRPEUR",
    "ADAEUR"
]

BASE_URL = "https://api.kraken.com/0/public"


# ==========================================
# SAUVEGARDE
# ==========================================

def charger_json(fichier, defaut):
    if os.path.exists(fichier):
        with open(fichier, "r") as f:
            return json.load(f)
    return defaut


def sauvegarder_json(fichier, donnees):
    with open(fichier, "w") as f:
        json.dump(donnees, f, indent=4)


def enregistrer_transaction(historique, transaction):
    transaction["date"] = datetime.now(
        timezone.utc
    ).isoformat()

    historique.append(transaction)


# ==========================================
# DONNEES KRAKEN
# ==========================================

def requete_kraken(endpoint, params):
    reponse = requests.get(
        f"{BASE_URL}/{endpoint}",
        params=params,
        timeout=20
    )

    reponse.raise_for_status()
    donnees = reponse.json()

    if donnees.get("error"):
        raise Exception(str(donnees["error"]))

    return donnees["result"]


def obtenir_bougies(paire):
    result = requete_kraken(
        "OHLC",
        {
            "pair": paire,
            "interval": 1
        }
    )

    cles = [k for k in result if k != "last"]

    if not cles:
        raise Exception(f"Aucune bougie reçue pour {paire}")

    bougies = result[cles[0]]

    # Exclusion de la bougie en cours
    bougies_fermees = bougies[:-1]

    if len(bougies_fermees) < 22:
        raise Exception(
            f"Pas assez de bougies pour {paire}"
        )

    return bougies_fermees


def obtenir_prix_actuel(paire):
    result = requete_kraken(
        "Ticker",
        {"pair": paire}
    )

    cles = list(result.keys())

    if not cles:
        raise Exception(f"Prix indisponible pour {paire}")

    return float(result[cles[0]]["c"][0])


# ==========================================
# SIGNAL D'ACHAT
# ==========================================

def signal_achat(bougies):

    derniere = bougies[-1]
    precedente = bougies[-2]

    volumes_precedents = [
        float(b[6])
        for b in bougies[-21:-1]
    ]

    volume_moyen = (
        sum(volumes_precedents)
        / len(volumes_precedents)
    )

    ouverture = float(derniere[1])
    cloture = float(derniere[4])
    volume = float(derniere[6])

    cloture_precedente = float(precedente[4])

    baisse = (
        cloture_precedente - cloture
    ) / cloture_precedente

    baisse_ok = baisse >= BAISSE_MIN

    volume_ok = (
        volume >= volume_moyen * MULTIPLICATEUR_VOLUME
    )

    rebond_ok = cloture > ouverture

    return {
        "achat": baisse_ok and volume_ok and rebond_ok,
        "baisse": baisse,
        "volume": volume,
        "volume_moyen": volume_moyen,
        "timestamp": int(derniere[0])
    }


# ==========================================
# CYCLE DE TRADING SIMULE
# ==========================================

def executer_cycle(portefeuille, historique):

    print("\n================================")
    print("     BOT KRAKEN - SIMULATION")
    print("================================")

    print(
        f"Solde disponible : "
        f"{portefeuille['euros']:.2f} €"
    )

    print(
        f"Positions ouvertes : "
        f"{len(portefeuille['positions'])}"
    )

    for paire in CRYPTOS:

        try:
            bougies = obtenir_bougies(paire)
            prix = obtenir_prix_actuel(paire)

            signal = signal_achat(bougies)

            position = portefeuille["positions"].get(paire)

            print(f"\n{paire} : {prix:.6f} €")

            # ==================================
            # VENTE A +0,80 %
            # ==================================

            if position:

                prix_achat = position["prix_achat"]

                objectif = prix_achat * (
                    1 + OBJECTIF_VENTE
                )

                if prix >= objectif:

                    montant_vente = (
                        position["quantite"] * prix
                    )

                    gain = (
                        montant_vente
                        - position["cout_total"]
                    )

                    portefeuille["euros"] += montant_vente

                    enregistrer_transaction(
                        historique,
                        {
                            "type": "VENTE",
                            "crypto": paire,
                            "prix_achat": prix_achat,
                            "prix_vente": prix,
                            "quantite": position["quantite"],
                            "montant_eur": montant_vente,
                            "frais_eur": 0.0,
                            "gain_perte": gain
                        }
                    )

                    del portefeuille["positions"][paire]

                    print(
                        f"VENTE SIMULEE : {paire} "
                        f"| Gain : {gain:.4f} €"
                    )

                else:

                    print(
                        f"Position conservée | "
                        f"Objectif : {objectif:.6f} €"
                    )

            # ==================================
            # ACHAT
            # ==================================

            else:

                dernier_timestamp = portefeuille[
                    "dernieres_bougies"
                ].get(paire)

                nouveau_signal = (
                    signal["timestamp"] != dernier_timestamp
                )

                if nouveau_signal:

                    portefeuille[
                        "dernieres_bougies"
                    ][paire] = signal["timestamp"]

                    print(
                        f"Baisse : "
                        f"{signal['baisse'] * 100:.3f} %"
                    )

                    print(
                        f"Volume : {signal['volume']:.4f}"
                    )

                    print(
                        f"Volume moyen : "
                        f"{signal['volume_moyen']:.4f}"
                    )

                    if signal["achat"]:

                        if portefeuille["euros"] >= MISE_PAR_POSITION:

                            quantite = MISE_PAR_POSITION / prix

                            portefeuille["euros"] -= (
                                MISE_PAR_POSITION
                            )

                            portefeuille["positions"][paire] = {
                                "prix_achat": prix,
                                "quantite": quantite,
                                "cout_total": MISE_PAR_POSITION
                            }

                            enregistrer_transaction(
                                historique,
                                {
                                    "type": "ACHAT",
                                    "crypto": paire,
                                    "prix_achat": prix,
                                    "quantite": quantite,
                                    "montant_eur": MISE_PAR_POSITION,
                                    "frais_eur": 0.0
                                }
                            )

                            print(
                                f"ACHAT SIMULE : {paire} "
                                f"pour {MISE_PAR_POSITION} €"
                            )

                        else:

                            print(
                                "Capital insuffisant pour acheter."
                            )

                    else:

                        print("Pas de signal d'achat confirmé.")

            time.sleep(1)

        except Exception as erreur:

            print(f"Erreur {paire} : {erreur}")

    # ======================================
    # BILAN DU PORTEFEUILLE
    # ======================================

    total = portefeuille["euros"]

    for paire, position in portefeuille["positions"].items():

        try:
            prix = obtenir_prix_actuel(paire)
            total += position["quantite"] * prix

        except Exception:
            total += position["cout_total"]

    print("\n------------ BILAN ------------")

    print(
        f"Solde disponible : "
        f"{portefeuille['euros']:.2f} €"
    )

    print(f"Valeur totale : {total:.2f} €")

    print(
        f"Résultat : "
        f"{total - CAPITAL_INITIAL:.2f} €"
    )

    print(
        f"Positions ouvertes : "
        f"{len(portefeuille['positions'])}"
    )

    print(f"Transactions : {len(historique)}")

    print("--------------------------------")

    sauvegarder_json(
        FICHIER_PORTEFEUILLE,
        portefeuille
    )

    sauvegarder_json(
        FICHIER_HISTORIQUE,
        historique
    )


# ==========================================
# DEMARRAGE
# ==========================================

def main():

    portefeuille = charger_json(
        FICHIER_PORTEFEUILLE,
        {
            "euros": CAPITAL_INITIAL,
            "positions": {},
            "dernieres_bougies": {}
        }
    )

    portefeuille.setdefault("positions", {})
    portefeuille.setdefault("dernieres_bougies", {})

    historique = charger_json(
        FICHIER_HISTORIQUE,
        []
    )

    print("BOT KRAKEN EN SIMULATION")
    print("Aucun ordre réel ne sera envoyé.")
    print("Frais simulés : 0 €")
    print("Analyse des bougies : 1 minute")
    print("Positions maximales : illimitées")
    print("Mise par achat : 10 €")
    print("Vente : +0,80 %")

    while True:

        debut = time.monotonic()

        try:
            executer_cycle(portefeuille, historique)

        except Exception as erreur:
            print(f"Erreur générale : {erreur}")

        duree = time.monotonic() - debut

        attente = max(1, INTERVALLE - duree)

        print(
            f"\nProchaine analyse dans "
            f"{attente:.0f} secondes."
        )

        time.sleep(attente)


if __name__ == "__main__":
    main()
