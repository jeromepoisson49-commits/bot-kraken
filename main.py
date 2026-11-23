
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

    historique = charger_json(FICHIER_HISTORIQUE, [])

    print("BOT KRAKEN - SIMULATION")
    print("Aucun ordre réel ne sera envoyé.")
    print("Jusqu'à 50 cryptos, classement quotidien.")
    print("Analyse des bougies de 1 minute.")
    print("Mise par achat : 10 €.")
    print("Objectif de vente : +0,80 %.")

    cache = obtenir_selection_cryptos()

    print("Début du cycle d'analyse.")

    executer_cycle(portefeuille, historique, cache)

    print("Cycle terminé. Fin du programme.")


if __name__ == "__main__":
    main()
