"""
Script d'exemple pour utiliser le système de prévision mildiou
"""

from mildiou_prevention import SystemeDecision, ConfigVignoble
from datetime import datetime


def exemple_analyse_complete():
    """Exemple d'analyse complète de toutes les parcelles"""
    print("🍇 SYSTÈME DE PRÉVISION MILDIOU")
    print("=" * 60)

    # Initialiser le système
    systeme = SystemeDecision()

    # Analyser chaque parcelle
    for parcelle in systeme.config.parcelles:
        print(f"\n📍 Analyse de: {parcelle['nom']}")

        # Analyse avec modèle IPI activé
        analyse = systeme.analyser_parcelle(
            parcelle['nom'],
            utiliser_ipi=True
        )

        if 'erreur' not in analyse:
            systeme.afficher_rapport(analyse)
        else:
            print(f"❌ Erreur: {analyse['erreur']}")

        print("\n" + "-" * 60)


def exemple_ajout_traitement():
    """Exemple d'ajout d'un traitement"""
    systeme = SystemeDecision()

    print("\n📝 ENREGISTREMENT D'UN TRAITEMENT")
    print("=" * 60)

    # Ajouter un traitement
    date_traitement = datetime.now().strftime('%Y-%m-%d')

    systeme.traitements.ajouter_traitement(
        parcelle='Parcelle Haute',
        date=date_traitement,
        produit='bouillie_bordelaise'
    )

    print(f"✅ Traitement enregistré:")
    print(f"   Parcelle: Parcelle Haute")
    print(f"   Date: {date_traitement}")
    print(f"   Produit: Bouillie bordelaise")
    print(f"   Persistance: 10 jours")

    # Réanalyser la parcelle
    print("\n🔄 Réanalyse après traitement...")
    analyse = systeme.analyser_parcelle('Parcelle Haute', utiliser_ipi=True)
    systeme.afficher_rapport(analyse)


def exemple_modification_stade():
    """Exemple de mise à jour du stade phénologique"""
    import json

    print("\n🌱 MISE À JOUR DU STADE PHÉNOLOGIQUE")
    print("=" * 60)

    # Charger la config
    with open('config_vignoble.json', 'r', encoding='utf-8') as f:
        config = json.load(f)

    # Modifier le stade d'une parcelle
    for parcelle in config['parcelles']:
        if parcelle['nom'] == 'Parcelle Haute':
            ancien_stade = parcelle['stade_actuel']
            parcelle['stade_actuel'] = 'pousse_10cm'  # Changement de stade

            print(f"Parcelle: {parcelle['nom']}")
            print(f"Ancien stade: {ancien_stade}")
            print(f"Nouveau stade: {parcelle['stade_actuel']}")

    # Sauvegarder
    with open('config_vignoble.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print("✅ Configuration mise à jour")


def exemple_liste_fongicides():
    """Affiche la liste des fongicides disponibles"""
    from mildiou_prevention import GestionTraitements

    print("\n💊 FONGICIDES DISPONIBLES")
    print("=" * 60)

    gestion = GestionTraitements()

    for code, info in gestion.FONGICIDES.items():
        print(f"\n🔹 {info['nom']}")
        print(f"   Code: {code}")
        print(f"   Type: {info['type']}")
        print(f"   Persistance: {info['persistance_jours']} jours")
        print(f"   Seuil lessivage: {info['lessivage_seuil_mm']} mm")


def exemple_comparaison_modeles():
    """Compare les résultats des modèles simple et IPI"""
    systeme = SystemeDecision()

    print("\n🔬 COMPARAISON DES MODÈLES")
    print("=" * 60)

    parcelle_test = systeme.config.parcelles[0]['nom']

    # Analyse avec modèle simple uniquement
    print("\n1️⃣ MODÈLE SIMPLE")
    analyse_simple = systeme.analyser_parcelle(parcelle_test, utiliser_ipi=False)
    print(f"   Risque: {analyse_simple['risque_infection']['score']}/10")
    print(f"   Niveau: {analyse_simple['risque_infection']['niveau']}")

    # Analyse avec modèle IPI
    print("\n2️⃣ MODÈLE IPI")
    analyse_ipi = systeme.analyser_parcelle(parcelle_test, utiliser_ipi=True)
    print(f"   Risque: {analyse_ipi['risque_infection']['score']}/10")
    print(f"   IPI: {analyse_ipi['risque_infection']['ipi']}/100")
    print(f"   Niveau: {analyse_ipi['risque_infection']['niveau']}")

    print("\n📊 Le modèle IPI affine le modèle simple avec une évaluation")
    print("   plus précise de la durée d'humectation foliaire.")


def menu_interactif():
    """Menu interactif pour utiliser le système"""
    while True:
        print("\n" + "=" * 60)
        print("🍇 SYSTÈME DE PRÉVISION MILDIOU - MENU")
        print("=" * 60)
        print("\n1. Analyser toutes les parcelles")
        print("2. Enregistrer un traitement")
        print("3. Modifier le stade phénologique")
        print("4. Liste des fongicides disponibles")
        print("5. Comparer les modèles")
        print("6. Quitter")

        choix = input("\n➜ Votre choix (1-6): ").strip()

        if choix == '1':
            exemple_analyse_complete()
        elif choix == '2':
            exemple_ajout_traitement()
        elif choix == '3':
            exemple_modification_stade()
        elif choix == '4':
            exemple_liste_fongicides()
        elif choix == '5':
            exemple_comparaison_modeles()
        elif choix == '6':
            print("\n👋 À bientôt !")
            break
        else:
            print("\n❌ Choix invalide")

        input("\n[Appuyez sur Entrée pour continuer]")


if __name__ == "__main__":
    # Lancer le menu interactif
    menu_interactif()

    # Ou décommenter pour lancer un exemple spécifique:
    # exemple_analyse_complete()
    # exemple_ajout_traitement()
    # exemple_liste_fongicides()