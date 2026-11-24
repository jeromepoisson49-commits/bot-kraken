
import json
import os
import time
from datetime import datetime, timezone

import requests

# ==========================================
# CONFIGURATION
# ==========================================

CAPITAL_INITIAL = 500.0
MISE_PAR_POSITION = 10.0

FRAIS = 0.0
BAISSE_MIN = 0.001
MULTIPLICATEUR_VOLUME = 1.5
OBJECTIF_VENTE = 0.008

PAUSE_ENTRE_REQUETES = 0.20

NOMBRE_CRYPTOS = 50
PAGES_COINGECKO_MAX = 4
CRYPTOS_PAR_PAGE = 250

FICHIER_PORTEFEUILLE = "portefeuille.json"
FICHIER_HISTORIQUE = "transactions.json"
FICHIER_SELECTION = "selection_cryptos.json"

BASE_KRAKEN = "https://api.kraken.com/0/public"
URL_COINGECKO = "https://api.coingecko.com/api/v3"

ALIAS_SYMBOLES = {"BTC": "XBT"}

session = requests.Session()
session.headers.update({"User-Agent": "BotKrakenSimulation/2.0"})


# ==========================================
# FICHIERS
# ==========================================

def charger_json(fichier, defaut):
    if os.path.exists(fichier):
        try:
            with open(fichier, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as erreur:
            print(f"Erreur lecture {fichier} : {erreur}")
    return defaut


def sauvegarder_json(fichier, donnees):
    temporaire = fichier + ".tmp"
    with open(temporaire, "w", encoding="utf-8") as f:
        json.dump(donnees, f, indent=4, ensure_ascii=False)
    os.replace(temporaire, fichier)


def enregistrer_transaction(historique, transaction):
    transaction["date"] = datetime.now(timezone.utc).isoformat()
    historique.append(transaction)


def verifier_comptabilite(portefeuille, historique):
    solde_theorique = CAPITAL_INITIAL

    for transaction in historique:
        montant = float(transaction.get("montant_eur", 0))
        frais = float(transaction.get("frais_eur", 0))

        if transaction.get("type") == "ACHAT":
            solde_theorique -= montant + frais
        elif transaction.get("type") == "VENTE":
            solde_theorique += montant - frais

    solde_actuel = float(portefeuille.get("euros", 0))
    ecart = solde_actuel - solde_theorique

    print("\n========== CONTRÔLE COMPTABLE ==========")
    print(f"Solde enregistré : {solde_actuel:.2f} €")
    print(f"Solde calculé depuis l'historique : {solde_theorique:.2f} €")
    print(f"Écart constaté : {ecart:+.2f} €")

    if abs(ecart) > 0.02:
        print("ATTENTION : historique et portefeuille non réconciliés.")
        print("Aucun solde n'a été modifié automatiquement.")
    else:
        print("Comptabilité cohérente.")
    print("========================================\n")


# ==========================================
# API
# ==========================================

def requete_json(url, params=None):
    reponse = session.get(url, params=params, timeout=30)
    reponse.raise_for_status()
    return reponse.json()


def requete_kraken(endpoint, params=None):
    donnees = requete_json(f"{BASE_KRAKEN}/{endpoint}", params)

    if donnees.get("error"):
        raise Exception(str(donnees["error"]))

    return donnees["result"]


# ==========================================
# SÉLECTION DES CRYPTOS
# ==========================================

def obtenir_catalogue_kraken():
    result = requete_kraken("AssetPairs")
    catalogue = []

    for identifiant, infos in result.items():
        nom = infos.get("wsname", "")
        altname = infos.get("altname", "")

        if not nom.endswith("/EUR") or not altname:
            continue

        if infos.get("status") not in (None, "online"):
            continue

        symbole = nom.split("/")[0].upper()

        catalogue.append({
            "id": identifiant,
            "altname": altname,
            "nom": nom,
            "symbole": symbole
        })

    return catalogue


def obtenir_classement_coingecko():
    classement = []

    for page in range(1, PAGES_COINGECKO_MAX + 1):
        donnees = requete_json(
            f"{URL_COINGECKO}/coins/markets",
            {
                "vs_currency": "eur",
                "order": "market_cap_desc",
                "per_page": CRYPTOS_PAR_PAGE,
                "page": page,
                "sparkline": "false"
            }
        )

        if not donnees:
            break

        classement.extend(donnees)
        time.sleep(1)

    return classement


def construire_selection():
    print("Récupération des paires EUR de Kraken...")
    catalogue = obtenir_catalogue_kraken()

    print("Récupération du classement CoinGecko...")
    classement = obtenir_classement_coingecko()

    paires_par_symbole = {}

    for paire in catalogue:
        paires_par_symbole.setdefault(paire["symbole"], []).append(paire)

    selection = []
    symboles_deja_pris = set()

    for crypto in classement:
        symbole = crypto.get("symbol", "").upper()
        symbole = ALIAS_SYMBOLES.get(symbole, symbole)

        correspondances = paires_par_symbole.get(symbole, [])

        if len(correspondances) != 1:
            continue

        if symbole in symboles_deja_pris:
            continue

        paire = correspondances[0]

        selection.append({
            **paire,
            "crypto": crypto.get("name", symbole),
            "capitalisation_eur": crypto.get("market_cap")
        })

        symboles_deja_pris.add(symbole)

        if len(selection) >= NOMBRE_CRYPTOS:
            break

    if not selection:
        raise Exception("Aucune crypto compatible trouvée.")

    print(f"{len(selection)} cryptos sélectionnées.")

    return {
        "date": datetime.now(timezone.utc).date().isoformat(),
        "catalogue": catalogue,
        "selection": selection
    }


def obtenir_selection_cryptos():
    cache = charger_json(FICHIER_SELECTION, {})
    date_du_jour = datetime.now(timezone.utc).date().isoformat()

    if cache.get("date") == date_du_jour and cache.get("selection"):
        print("Classement quotidien déjà actualisé.")
        return cache

    try:
        nouveau_cache = construire_selection()
        sauvegarder_json(FICHIER_SELECTION, nouveau_cache)
        return nouveau_cache

    except Exception as erreur:
        print(f"Erreur classement : {erreur}")

        if cache.get("selection") and cache.get("catalogue"):
            print("Utilisation de la dernière sélection sauvegardée.")
            return cache

        raise


# ==========================================
# CORRESPONDANCE DES PAIRES
# ==========================================

def construire_index_paires(catalogue):
    index = {}

    for paire in catalogue:
        for alias in (
            paire.get("id"),
            paire.get("altname"),
            paire.get("nom")
        ):
            if alias:
                index[alias] = paire

    return index


def trouver_paire(position_key, index_paires):
    return index_paires.get(position_key)


# ==========================================
# PRIX
# ==========================================

def obtenir_prix_tous(paires):
    identifiants = list(dict.fromkeys(
        paire["id"] for paire in paires
    ))

    if not identifiants:
        return {}

    result = requete_kraken(
        "Ticker",
        {"pair": ",".join(identifiants)}
    )

    prix_par_alias = {}

    for paire in paires:
        infos = (
            result.get(paire["id"])
            or result.get(paire["altname"])
            or result.get(paire["nom"])
        )

        # Recherche complémentaire sur les clés renvoyées par Kraken.
        if infos is None:
            for cle, valeur in result.items():
                if cle.upper() in (
                    paire["id"].upper(),
                    paire["altname"].upper(),
                    paire["nom"].upper()
                ):
                    infos = valeur
                    break

        if infos:
            prix = float(infos["c"][0])
            prix_par_alias[paire["id"]] = prix
            prix_par_alias[paire["altname"]] = prix

    return prix_par_alias


def obtenir_bougies(paire):
    result = requete_kraken(
        "OHLC",
        {
            "pair": paire["altname"],
            "interval": 1
        }
    )

    cles = [cle for cle in result if cle != "last"]

    if not cles:
        raise Exception("Aucune bougie reçue.")

    bougies = result[cles[0]]
    bougies_fermees = bougies[:-1]

    if len(bougies_fermees) < 22:
        raise Exception("Pas assez de bougies.")

    return bougies_fermees


# ==========================================
# SIGNAL D'ACHAT
# ==========================================

def signal_achat(bougies):
    derniere = bougies[-1]
    precedente = bougies[-2]

    volumes_precedents = [
        float(b[6]) for b in bougies[-21:-1]
    ]

    volume_moyen = sum(volumes_precedents) / len(volumes_precedents)

    ouverture = float(derniere[1])
    cloture = float(derniere[4])
    volume = float(derniere[6])
    cloture_precedente = float(precedente[4])

    baisse = (
        (cloture_precedente - cloture) / cloture_precedente
        if cloture_precedente > 0 else 0
    )

    achat = (
        baisse >= BAISSE_MIN
        and volume >= volume_moyen * MULTIPLICATEUR_VOLUME
        and cloture > ouverture
    )

    return {
        "achat": achat,
        "baisse": baisse,
        "volume": volume,
        "volume_moyen": volume_moyen,
        "timestamp": int(derniere[0])
    }


# ==========================================
# CYCLE DE SIMULATION
# ==========================================

def executer_cycle(portefeuille, historique, cache):
    selection = cache["selection"]
    catalogue = cache["catalogue"]

    index_paires = construire_index_paires(catalogue)

    selection_ids = {paire["id"] for paire in selection}

    # Paires de la sélection + paires des positions déjà ouvertes.
    paires_a_surveiller = {
        paire["id"]: paire for paire in selection
    }

    for position_key in portefeuille["positions"]:
        paire = trouver_paire(position_key, index_paires)

        if paire:
            paires_a_surveiller[paire["id"]] = paire
        else:
            print(f"Attention : paire introuvable pour {position_key}")

    paires = list(paires_a_surveiller.values())

    print("\n========== BOT KRAKEN ==========")
    print(f"Cryptos sélectionnées : {len(selection)}")
    print(f"Solde : {portefeuille['euros']:.2f} €")
    print(f"Positions ouvertes : {len(portefeuille['positions'])}")

    prix_tous = obtenir_prix_tous(paires)

    portefeuille.setdefault("derniers_prix", {})

    # Enregistre les cours pour le tableau de bord.
    for paire in paires:
        prix = prix_tous.get(paire["id"])

        if prix is not None:
            portefeuille["derniers_prix"][paire["id"]] = prix
            portefeuille["derniers_prix"][paire["altname"]] = prix

    portefeuille["maj_prix_utc"] = datetime.now(timezone.utc).isoformat()

    for paire in paires:
        identifiant = paire["id"]
        altname = paire["altname"]
        nom = paire["nom"]

        try:
            prix = prix_tous.get(identifiant)

            if prix is None:
                print(f"{nom} : cours indisponible.")
                continue

            print(f"\nAnalyse de {nom} : {prix:.8f} €")

            # Retrouve une position existante avec son ancienne clé,
            # qu'elle soit l'identifiant Kraken ou son altname.
            position_key = None

            for cle in (identifiant, altname):
                if cle in portefeuille["positions"]:
                    position_key = cle
                    break

            position = (
                portefeuille["positions"].get(position_key)
                if position_key else None
            )

            # ----------------------------------
            # VENTE
            # ----------------------------------

            if position:
                prix_achat = float(position["prix_achat"])
                objectif = prix_achat * (1 + OBJECTIF_VENTE)

                if prix >= objectif:
                    quantite = float(position["quantite"])
                    montant_vente = quantite * prix
                    frais_vente = montant_vente * FRAIS
                    montant_net = montant_vente - frais_vente

                    gain = montant_net - float(position["cout_total"])

                    portefeuille["euros"] += montant_net

                    enregistrer_transaction(
                        historique,
                        {
                            "type": "VENTE",
                            "crypto": position.get("nom", altname),
                            "paire": position_key,
                            "prix_achat": prix_achat,
                            "prix_vente": prix,
                            "quantite": quantite,
                            "montant_eur": montant_vente,
                            "frais_eur": frais_vente,
                            "gain_perte": gain
                        }
                    )

                    del portefeuille["positions"][position_key]

                    print(f"VENTE SIMULÉE. Gain : {gain:.4f} €")
                else:
                    print(f"Position conservée. Objectif : {objectif:.8f} €")

                continue

            # Pas de nouvel achat hors sélection.
            if identifiant not in selection_ids:
                continue

            # ----------------------------------
            # ACHAT
            # ----------------------------------

            bougies = obtenir_bougies(paire)
            signal = signal_achat(bougies)

            portefeuille.setdefault("dernieres_bougies", {})
            dernier_timestamp = portefeuille["dernieres_bougies"].get(identifiant)

            if signal["timestamp"] == dernier_timestamp:
                print("Bougie déjà analysée.")
                continue

            portefeuille["dernieres_bougies"][identifiant] = signal["timestamp"]

            print(f"Baisse : {signal['baisse'] * 100:.3f} %")
            print(f"Volume : {signal['volume']:.4f}")
            print(f"Moyenne volume : {signal['volume_moyen']:.4f}")

            if not signal["achat"]:
                print("Aucun signal d'achat.")
                continue

            if portefeuille["euros"] < MISE_PAR_POSITION:
                print("Solde insuffisant.")
                continue

            frais_achat = MISE_PAR_POSITION * FRAIS
            montant_investi = MISE_PAR_POSITION - frais_achat

            if prix <= 0:
                print("Prix invalide : achat ignoré.")
                continue

            quantite = montant_investi / prix

            portefeuille["euros"] -= MISE_PAR_POSITION

            portefeuille["positions"][identifiant] = {
                "nom": paire.get("crypto", altname),
                "prix_achat": prix,
                "quantite": quantite,
                "cout_total": MISE_PAR_POSITION
            }

            enregistrer_transaction(
                historique,
                {
                    "type": "ACHAT",
                    "crypto": paire.get("crypto", altname),
                    "paire": identifiant,
                    "prix_achat": prix,
                    "quantite": quantite,
                    "montant_eur": MISE_PAR_POSITION,
                    "frais_eur": frais_achat
                }
            )

            print(f"ACHAT SIMULÉ : {MISE_PAR_POSITION:.2f} €")

        except Exception as erreur:
            print(f"Erreur sur {nom} : {erreur}")

        time.sleep(PAUSE_ENTRE_REQUETES)

    # ======================================
    # BILAN
    # ======================================

    total = float(portefeuille["euros"])
    valeur_positions_connue = 0.0
    positions_sans_cours = 0

    for position_key, position in portefeuille["positions"].items():
        paire = trouver_paire(position_key, index_paires)

        prix = None
        if paire:
            prix = prix_tous.get(paire["id"])

        if prix is None:
            prix = portefeuille["derniers_prix"].get(position_key)

        if prix is not None:
            valeur = float(position["quantite"]) * float(prix)
            total += valeur
            valeur_positions_connue += valeur
        else:
            positions_sans_cours += 1

    print("\n========== BILAN ==========")
    print(f"Solde disponible : {portefeuille['euros']:.2f} €")
    print(f"Valeur des positions valorisées : {valeur_positions_connue:.2f} €")

    if positions_sans_cours:
        print(f"Positions sans cours : {positions_sans_cours}")
        print("La valeur totale affichée est incomplète.")
    else:
        print(f"Valeur totale estimée : {total:.2f} €")
        print(f"Résultat estimé : {total - CAPITAL_INITIAL:+.2f} €")

    print(f"Positions ouvertes : {len(portefeuille['positions'])}")
    print(f"Transactions enregistrées : {len(historique)}")
    print("===========================\n")

    sauvegarder_json(FICHIER_PORTEFEUILLE, portefeuille)
    sauvegarder_json(FICHIER_HISTORIQUE, historique)


# ==========================================
# DÉMARRAGE : UN SEUL CYCLE
# ==========================================

def main():
    portefeuille = charger_json(
        FICHIER_PORTEFEUILLE,
        {
            "euros": CAPITAL_INITIAL,
            "positions": {},
            "dernieres_bougies": {},
            "derniers_prix": {}
        }
    )

    portefeuille.setdefault("positions", {})
    portefeuille.setdefault("dernieres_bougies", {})
    portefeuille.setdefault("derniers_prix", {})

    historique = charger_json(FICHIER_HISTORIQUE, [])

    print("BOT KRAKEN EN SIMULATION")
    print("Aucun ordre réel ne sera envoyé.")

    verifier_comptabilite(portefeuille, historique)

    cache = obtenir_selection_cryptos()
    executer_cycle(portefeuille, historique, cache)

    print("Cycle terminé. Fin du programme.")


if __name__ == "__main__":
    main()
