"""
Système de prévision et aide à la décision pour le traitement du mildiou
Version finale complète avec :
- Modèles Simple + IPI avec interpolation bilinéaire
- Gestion multi-cépages et coefficient de pousse
- Graphiques d'évolution
- Calcul IFT automatique
- Export et synthèse annuelle
"""

import json
import csv
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import requests

# Bibliothèques optionnelles pour graphiques
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    GRAPHIQUES_DISPONIBLES = True
except ImportError:
    GRAPHIQUES_DISPONIBLES = False
    print("⚠️  matplotlib non installé - Graphiques désactivés")
    print("   Pour activer : pip install matplotlib")


class ConfigVignoble:
    """Configuration du vignoble"""

    # Sensibilités variétales (échelle 1-9, où 9 = très sensible)
    SENSIBILITES_CEPAGES = {
        'Chardonnay': 7, 'Cabernet Sauvignon': 6, 'Merlot': 7,
        'Grenache': 5, 'Syrah': 6, 'Pinot Noir': 8,
        'Sauvignon': 7, 'Carignan': 4, 'Mourvèdre': 5,
        'Cinsault': 5, 'Ugni Blanc': 6, 'Viognier': 6,
        'Caladoc': 6
    }

    # Coefficients de sensibilité par stade phénologique
    COEF_STADES = {
        'repos': 0.0,
        'debourrement': 0.8,
        'pousse_10cm': 1.5,
        'pre_floraison': 1.8,
        'floraison': 2.0,
        'nouaison': 1.8,
        'fermeture_grappe': 1.5,
        'veraison': 0.7,
        'maturation': 0.3
    }

    def __init__(self, config_file: str = 'config_vignoble.json'):
        # Toujours chercher le fichier dans le répertoire du script
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_file = os.path.join(script_dir, config_file)
        self.load_config()

    def load_config(self):
        """Charge la configuration depuis le fichier JSON"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.latitude = config['latitude']
                self.longitude = config['longitude']
                self.parcelles = config['parcelles']
                self.surface_totale = sum(p['surface_ha'] for p in self.parcelles)
                print(f"✅ Configuration chargée depuis : {self.config_file}")
        except FileNotFoundError:
            print(f"⚠️ Fichier de configuration non trouvé : {self.config_file}")
            print("Création d'un fichier par défaut.")
            self.create_default_config()

    def create_default_config(self):
        """Crée un fichier de configuration par défaut"""
        config = {
            "latitude": 43.21,
            "longitude": 5.54,
            "localisation": "Cassis, France",
            "parcelles": [
                {
                    "nom": "Parcelle 1",
                    "surface_ha": 1.5,
                    "cepages": ["Grenache", "Syrah"],
                    "stade_actuel": "repos"
                },
                {
                    "nom": "Parcelle 2",
                    "surface_ha": 1.5,
                    "cepages": ["Mourvèdre"],
                    "stade_actuel": "repos"
                }
            ]
        }
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        self.latitude = config['latitude']
        self.longitude = config['longitude']
        self.parcelles = config['parcelles']
        self.surface_totale = sum(p['surface_ha'] for p in self.parcelles)


class MeteoAPI:
    """Gestion des données météorologiques via Open-Meteo (gratuit)"""

    def __init__(self, latitude: float, longitude: float):
        self.latitude = latitude
        self.longitude = longitude
        self.base_url = "https://api.open-meteo.com/v1/forecast"

    def get_meteo_data(self, days_past: int = 14, days_future: int = 7) -> Dict:
        """
        Récupère les données météo passées et futures
        """
        params = {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'daily': 'temperature_2m_max,temperature_2m_min,precipitation_sum,relative_humidity_2m_mean',
            'timezone': 'Europe/Paris',
            'past_days': days_past,
            'forecast_days': days_future
        }

        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            return self._format_meteo_data(data)

        except requests.RequestException as e:
            print(f"❌ Erreur lors de la récupération des données météo: {e}")
            return {}

    def _format_meteo_data(self, raw_data: Dict) -> Dict:
        """Formate les données brutes de l'API"""
        daily = raw_data.get('daily', {})

        formatted = {}
        for i, date in enumerate(daily.get('time', [])):
            formatted[date] = {
                'temp_max': daily['temperature_2m_max'][i],
                'temp_min': daily['temperature_2m_min'][i],
                'temp_moy': (daily['temperature_2m_max'][i] + daily['temperature_2m_min'][i]) / 2,
                'precipitation': daily['precipitation_sum'][i],
                'humidite': daily['relative_humidity_2m_mean'][i]
            }

        return formatted


class ModeleSimple:
    """Modèle simplifié basé sur la règle des 3-10 améliorée"""

    @staticmethod
    def calculer_risque_infection(meteo_48h: List[Dict], stade_coef: float,
                                   sensibilite_cepage: float) -> Tuple[float, str]:
        """
        Calcule le risque d'infection sur les dernières 48h
        """
        if not meteo_48h:
            return 0.0, "FAIBLE"

        # Cumul pluie sur 48h
        pluie_totale = sum(m.get('precipitation', 0) for m in meteo_48h)

        # Température moyenne sur périodes humides
        jours_humides = [m for m in meteo_48h if m.get('precipitation', 0) > 1]
        if jours_humides:
            temp_moy = sum(m['temp_moy'] for m in jours_humides) / len(jours_humides)
        else:
            temp_moy = sum(m['temp_moy'] for m in meteo_48h) / len(meteo_48h)

        # Calcul du score de base
        score_base = 0

        # Critère pluie
        if pluie_totale >= 10:
            score_base += 5
        elif pluie_totale >= 5:
            score_base += 3
        elif pluie_totale >= 2:
            score_base += 1

        # Critère température (optimum 20-25°C)
        if 20 <= temp_moy <= 25:
            score_base += 4
        elif 15 <= temp_moy <= 28:
            score_base += 2
        elif 10 <= temp_moy <= 30:
            score_base += 1

        # Humidité
        humid_moy = sum(m.get('humidite', 0) for m in meteo_48h) / len(meteo_48h)
        if humid_moy > 85:
            score_base += 1

        # Application coefficients
        score_final = score_base * stade_coef * (sensibilite_cepage / 5)
        score_final = min(10, score_final)  # Cap à 10

        # Niveau textuel
        if score_final >= 7:
            niveau = "FORT"
        elif score_final >= 4:
            niveau = "MOYEN"
        else:
            niveau = "FAIBLE"

        return round(score_final, 1), niveau


class ModeleIPI:
    """
    Modèle IPI (Indice Potentiel d'Infection)
    Avec interpolation bilinéaire pour plus de précision
    """

    # Table IPI (durée humectation en heures vs température moyenne)
    IPI_TABLE = {
        10: {6: 10, 9: 20, 12: 30, 15: 40, 18: 50},
        13: {5: 10, 7: 20, 10: 30, 12: 40, 15: 60, 18: 80},
        16: {4: 10, 6: 20, 8: 30, 10: 50, 12: 70, 15: 90},
        19: {3: 10, 5: 20, 7: 40, 9: 60, 11: 80, 13: 100},
        21: {3: 10, 4: 20, 6: 50, 8: 80, 10: 100},
        24: {3: 10, 4: 30, 6: 70, 8: 100},
        27: {3: 20, 5: 60, 7: 100}
    }

    @staticmethod
    def _interpolate(x: float, x0: float, y0: float, x1: float, y1: float) -> float:
        """Interpolation linéaire simple"""
        if x1 == x0:
            return y0
        return y0 + (x - x0) * (y1 - y0) / (x1 - x0)

    @staticmethod
    def _find_bounding_keys(keys: List[float], value: float) -> Tuple[float, float]:
        """Trouve les deux clés qui encadrent la valeur"""
        if value <= keys[0]:
            return keys[0], keys[0]
        if value >= keys[-1]:
            return keys[-1], keys[-1]

        for i in range(len(keys) - 1):
            if keys[i] <= value < keys[i+1]:
                return keys[i], keys[i+1]
        return keys[-1], keys[-1]

    @staticmethod
    def calculer_ipi(meteo_evenement: Dict, duree_humectation_estimee: float) -> int:
        """
        Calcule l'IPI pour un événement pluvieux
        Utilise l'interpolation bilinéaire
        """
        temp = meteo_evenement['temp_moy']

        # Hors limites de température
        if temp < 10 or temp > 27:
            return 0

        temp_keys = sorted(ModeleIPI.IPI_TABLE.keys())

        # 1. Encadrer la température
        t0, t1 = ModeleIPI._find_bounding_keys(temp_keys, temp)

        # 2. Interpoler pour la température basse (t0)
        durees_t0 = ModeleIPI.IPI_TABLE[t0]
        keys_d_t0 = sorted(durees_t0.keys())
        d0_t0, d1_t0 = ModeleIPI._find_bounding_keys(keys_d_t0, duree_humectation_estimee)
        ipi_t0 = ModeleIPI._interpolate(duree_humectation_estimee,
                                        d0_t0, durees_t0[d0_t0],
                                        d1_t0, durees_t0[d1_t0])

        if t0 == t1:
            return round(max(0, ipi_t0))

        # 3. Interpoler pour la température haute (t1)
        durees_t1 = ModeleIPI.IPI_TABLE[t1]
        keys_d_t1 = sorted(durees_t1.keys())
        d0_t1, d1_t1 = ModeleIPI._find_bounding_keys(keys_d_t1, duree_humectation_estimee)
        ipi_t1 = ModeleIPI._interpolate(duree_humectation_estimee,
                                        d0_t1, durees_t1[d0_t1],
                                        d1_t1, durees_t1[d1_t1])

        # 4. Interpoler entre les deux températures
        ipi_final = ModeleIPI._interpolate(temp, t0, ipi_t0, t1, ipi_t1)

        return round(max(0, ipi_final))

    @staticmethod
    def estimer_duree_humectation(precipitation: float, humidite: float) -> float:
        """
        Estime la durée d'humectation foliaire
        Version recalibrée
        """
        if precipitation < 2:
            return 0

        if precipitation < 5:
            duree_base = precipitation * 0.8
        else:
            duree_base = precipitation * 1.2

        if humidite > 90:
            duree_base *= 1.3
        elif humidite > 80:
            duree_base *= 1.1

        return min(duree_base, 24)


class GestionTraitements:
    """Gestion des traitements et calcul de la protection résiduelle"""

    # Base de données fongicides
    FONGICIDES = {
        'bouillie_bordelaise': {
            'nom': 'Bouillie bordelaise',
            'persistance_jours': 10,
            'lessivage_seuil_mm': 30,
            'type': 'contact',
            'dose_reference_kg_ha': 2.0  # Pour calcul IFT
        },
        'cymoxanil': {
            'nom': 'Cymoxanil',
            'persistance_jours': 7,
            'lessivage_seuil_mm': 20,
            'type': 'penetrant',
            'dose_reference_kg_ha': 0.5
        },
        'fosetyl_al': {
            'nom': 'Fosétyl-Al',
            'persistance_jours': 14,
            'lessivage_seuil_mm': 40,
            'type': 'systemique',
            'dose_reference_kg_ha': 2.5
        },
        'mancozebe': {
            'nom': 'Mancozèbe',
            'persistance_jours': 7,
            'lessivage_seuil_mm': 25,
            'type': 'contact',
            'dose_reference_kg_ha': 1.6
        }
    }

    # Coefficients de vitesse de pousse
    COEF_POUSSE = {
        'repos': 0.0,
        'debourrement': 0.5,
        'pousse_10cm': 2.0,
        'pre_floraison': 1.8,
        'floraison': 1.0,
        'nouaison': 0.8,
        'fermeture_grappe': 0.5,
        'veraison': 0.2,
        'maturation': 0.1
    }

    def __init__(self, fichier_historique: str = 'traitements.json'):
        # Toujours chercher le fichier dans le répertoire du script
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.fichier = os.path.join(script_dir, fichier_historique)
        self.historique = self.charger_historique()

    def charger_historique(self) -> Dict:
        """Charge l'historique des traitements"""
        try:
            with open(self.fichier, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {'traitements': []}

    def sauvegarder_historique(self):
        """Sauvegarde l'historique"""
        with open(self.fichier, 'w', encoding='utf-8') as f:
            json.dump(self.historique, f, indent=2, ensure_ascii=False)

    def ajouter_traitement(self, parcelle: str, date: str, produit: str,
                          dose_kg_ha: Optional[float] = None):
        """Ajoute un traitement à l'historique"""
        produit_key = produit.lower().replace(' ', '_')

        if produit_key not in self.FONGICIDES:
            print(f"⚠️  Produit '{produit}' inconnu. Ajout avec paramètres par défaut.")
            caracteristiques = {
                'nom': produit,
                'persistance_jours': 7,
                'lessivage_seuil_mm': 25,
                'type': 'contact',
                'dose_reference_kg_ha': 1.0
            }
        else:
            caracteristiques = self.FONGICIDES[produit_key].copy()

        # Dose appliquée (défaut = dose de référence)
        if dose_kg_ha is None:
            dose_kg_ha = caracteristiques['dose_reference_kg_ha']

        traitement = {
            'parcelle': parcelle,
            'date': date,
            'produit': produit_key,
            'dose_kg_ha': dose_kg_ha,
            'caracteristiques': caracteristiques
        }
        self.historique['traitements'].append(traitement)
        self.sauvegarder_historique()
        print(f"✅ Traitement '{caracteristiques['nom']}' ajouté pour '{parcelle}' le {date}")

    def calculer_protection_actuelle(self, parcelle: str, date_actuelle: str,
                                    meteo_periode: Dict, stade_actuel: str
                                    ) -> Tuple[float, Dict, str]:
        """
        Calcule le niveau de protection actuel (0-10)
        Prend en compte : Persistance, Pousse (dilution), Lessivage
        """
        traitements_parcelle = [t for t in self.historique['traitements']
                               if t['parcelle'] == parcelle]

        if not traitements_parcelle:
            return 0.0, {}, "Aucun traitement"

        dernier_traitement = max(traitements_parcelle, key=lambda x: x['date'])

        date_trait = datetime.strptime(dernier_traitement['date'], '%Y-%m-%d')
        date_act = datetime.strptime(date_actuelle, '%Y-%m-%d')
        jours_ecoules = (date_act - date_trait).days

        if jours_ecoules < 0:
            return 10.0, dernier_traitement, "Traitement futur"

        carac = dernier_traitement['caracteristiques']
        persistance = carac.get('persistance_jours', 7)
        seuil_lessivage = carac.get('lessivage_seuil_mm', 25)
        type_produit = carac.get('type', 'contact')

        facteur_limitant = "Persistance"

        # 1. Protection par temps
        protection_temps = max(0, 10 - (jours_ecoules / persistance * 10))
        protection = protection_temps

        # 2. Protection par pousse (sauf systémiques)
        if type_produit in ['contact', 'penetrant']:
            coef_pousse = self.COEF_POUSSE.get(stade_actuel, 1.0)
            protection_pousse = max(0, 10 - (jours_ecoules * coef_pousse))

            if protection_pousse < protection:
                protection = protection_pousse
                facteur_limitant = "Pousse (dilution)"

        # 3. Lessivage
        pluie_depuis_traitement = sum(
            meteo_periode.get(date, {}).get('precipitation', 0)
            for date in meteo_periode
            if date >= dernier_traitement['date'] and date <= date_actuelle
        )

        if pluie_depuis_traitement > seuil_lessivage:
            protection = 0
            facteur_limitant = f"Lessivage ({pluie_depuis_traitement:.1f}mm)"

        return round(protection, 1), dernier_traitement, facteur_limitant

    def calculer_ift_periode(self, date_debut: str, date_fin: str,
                            surface_totale: float) -> Dict:
        """
        Calcule l'IFT (Indice de Fréquence de Traitement) sur une période
        IFT = Σ (dose appliquée / dose de référence) / surface
        """
        traitements_periode = [
            t for t in self.historique['traitements']
            if date_debut <= t['date'] <= date_fin
        ]

        if not traitements_periode:
            return {
                'ift_total': 0.0,
                'nb_traitements': 0,
                'details': []
            }

        ift_details = []
        ift_total = 0.0

        for t in traitements_periode:
            dose_appliquee = t.get('dose_kg_ha', 0)
            dose_reference = t['caracteristiques'].get('dose_reference_kg_ha', 1.0)

            ift_traitement = dose_appliquee / dose_reference
            ift_total += ift_traitement

            ift_details.append({
                'date': t['date'],
                'parcelle': t['parcelle'],
                'produit': t['caracteristiques']['nom'],
                'ift': round(ift_traitement, 2)
            })

        return {
            'ift_total': round(ift_total, 2),
            'nb_traitements': len(traitements_periode),
            'details': ift_details,
            'periode': f"{date_debut} à {date_fin}"
        }
class GestionHistoriqueAlertes:
    """Gestion de l'historique des alertes et analyses"""

    def __init__(self, fichier='historique_alertes.json'):
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.fichier = os.path.join(script_dir, fichier)
        self.historique = self.charger_historique()

    def charger_historique(self):
        """Charge l'historique depuis le fichier JSON"""
        try:
            with open(self.fichier, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return self.creer_structure_defaut()

    def creer_structure_defaut(self):
        """Crée la structure par défaut"""
        return {
            'campagnes': []
        }

    def sauvegarder(self):
        """Sauvegarde l'historique"""
        with open(self.fichier, 'w', encoding='utf-8') as f:
            json.dump(self.historique, f, indent=2, ensure_ascii=False)

    def get_campagne(self, annee):
        """Récupère une campagne par année"""
        for c in self.historique['campagnes']:
            if c['annee'] == annee:
                return c
        return None

    def creer_campagne(self, annee):
        """Crée une nouvelle campagne"""
        campagne = {
            'annee': annee,
            'analyses': []
        }
        self.historique['campagnes'].append(campagne)
        return campagne

    def ajouter_analyse(self, analyse_complete):
        """
        Ajoute une analyse à l'historique
        analyse_complete : Dict retourné par SystemeDecision.analyser_parcelle()
        """
        # Extraire l'année de la date
        date_analyse = analyse_complete['date_analyse']
        annee = datetime.strptime(date_analyse, '%Y-%m-%d').year

        # Récupérer ou créer la campagne
        campagne = self.get_campagne(annee)
        if not campagne:
            campagne = self.creer_campagne(annee)

        # Préparer l'enregistrement simplifié
        analyse_simplifiee = {
            'date': date_analyse,
            'parcelle': analyse_complete['parcelle'],
            'stade': analyse_complete['stade'],
            'risque': {
                'score': analyse_complete['risque_infection']['score'],
                'niveau': analyse_complete['risque_infection']['niveau'],
                'ipi': analyse_complete['risque_infection'].get('ipi')
            },
            'protection': {
                'score': analyse_complete['protection_actuelle']['score'],
                'dernier_traitement': analyse_complete['protection_actuelle']['dernier_traitement'].get('date') if
                analyse_complete['protection_actuelle']['dernier_traitement'] else None,
                'facteur_limitant': analyse_complete['protection_actuelle']['facteur_limitant']
            },
            'decision': {
                'score': analyse_complete['decision']['score'],
                'action': analyse_complete['decision']['action'],
                'urgence': analyse_complete['decision']['urgence']
            },
            'meteo': {
                'temp_moy': analyse_complete['meteo_actuelle'].get('temp_moy'),
                'precipitation': analyse_complete['meteo_actuelle'].get('precipitation'),
                'humidite': analyse_complete['meteo_actuelle'].get('humidite')
            },
            'previsions': {
                'pluie_3j': analyse_complete['previsions_3j']['pluie_totale']
            }
        }

        # Vérifier si une analyse existe déjà pour cette date et parcelle
        analyses_existantes = [a for a in campagne['analyses']
                               if a['date'] == date_analyse and a['parcelle'] == analyse_complete['parcelle']]

        if analyses_existantes:
            # Remplacer l'analyse existante
            idx = campagne['analyses'].index(analyses_existantes[0])
            campagne['analyses'][idx] = analyse_simplifiee
        else:
            # Ajouter nouvelle analyse
            campagne['analyses'].append(analyse_simplifiee)

        self.sauvegarder()

    def get_analyses_parcelle(self, parcelle, date_debut=None, date_fin=None):
        """Récupère toutes les analyses d'une parcelle sur une période"""
        analyses = []

        for campagne in self.historique['campagnes']:
            for analyse in campagne['analyses']:
                if analyse['parcelle'] == parcelle:
                    if date_debut and analyse['date'] < date_debut:
                        continue
                    if date_fin and analyse['date'] > date_fin:
                        continue
                    analyses.append(analyse)

        return sorted(analyses, key=lambda x: x['date'])

    def get_alertes_urgence(self, urgence='haute', jours=7):
        """Récupère les alertes d'un niveau d'urgence sur les derniers jours"""
        date_limite = (datetime.now() - timedelta(days=jours)).strftime('%Y-%m-%d')
        alertes = []

        for campagne in self.historique['campagnes']:
            for analyse in campagne['analyses']:
                if analyse['date'] >= date_limite and analyse['decision']['urgence'] == urgence:
                    alertes.append(analyse)

        return sorted(alertes, key=lambda x: x['date'], reverse=True)

    def generer_rapport_campagne(self, annee):
        """Génère un rapport statistique pour une campagne"""
        campagne = self.get_campagne(annee)
        if not campagne or not campagne['analyses']:
            return None

        analyses = campagne['analyses']

        # Statistiques par parcelle
        parcelles_stats = {}
        for analyse in analyses:
            parcelle = analyse['parcelle']
            if parcelle not in parcelles_stats:
                parcelles_stats[parcelle] = {
                    'nb_analyses': 0,
                    'alertes_haute': 0,
                    'alertes_moyenne': 0,
                    'risque_moyen': 0,
                    'protection_moyenne': 0
                }

            stats = parcelles_stats[parcelle]
            stats['nb_analyses'] += 1
            stats['risque_moyen'] += analyse['risque']['score']
            stats['protection_moyenne'] += analyse['protection']['score']

            if analyse['decision']['urgence'] == 'haute':
                stats['alertes_haute'] += 1
            elif analyse['decision']['urgence'] == 'moyenne':
                stats['alertes_moyenne'] += 1

        # Calculer moyennes
        for stats in parcelles_stats.values():
            if stats['nb_analyses'] > 0:
                stats['risque_moyen'] = round(stats['risque_moyen'] / stats['nb_analyses'], 2)
                stats['protection_moyenne'] = round(stats['protection_moyenne'] / stats['nb_analyses'], 2)

        return {
            'annee': annee,
            'nb_analyses_total': len(analyses),
            'parcelles': parcelles_stats,
            'periode': {
                'debut': min(a['date'] for a in analyses),
                'fin': max(a['date'] for a in analyses)
            }
        }



class SystemeDecision:
    """Système principal d'aide à la décision"""

    # Constantes configurables
    SEUIL_ALERTE_PLUIE = 10  # mm
    SEUIL_PROTECTION_FAIBLE = 5  # /10
    SEUIL_DECISION_HAUTE = 5  # /10
    SEUIL_DECISION_MOYENNE = 2  # /10

    def __init__(self):
        self.config = ConfigVignoble()
        self.meteo = MeteoAPI(self.config.latitude, self.config.longitude)
        self.traitements = GestionTraitements()
        self.modele_simple = ModeleSimple()
        self.modele_ipi = ModeleIPI()
        self.historique_analyses = []  # Pour graphiques
        self.historique_alertes = GestionHistoriqueAlertes()

    def analyser_parcelle(self, nom_parcelle: str, utiliser_ipi: bool = False,
                         debug: bool = False) -> Dict:
        """Analyse complète d'une parcelle"""
        parcelle = next((p for p in self.config.parcelles if p['nom'] == nom_parcelle), None)
        if not parcelle:
            return {'erreur': f"Parcelle '{nom_parcelle}' non trouvée"}

        meteo_data = self.meteo.get_meteo_data(days_past=14, days_future=7)
        if not meteo_data:
            return {'erreur': "Impossible de récupérer les données météo"}

        date_actuelle = datetime.now().strftime('%Y-%m-%d')

        # Données 48h passées
        dates_48h = [(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
                     for i in range(2, -1, -1)]
        meteo_48h = [meteo_data.get(d, {}) for d in dates_48h if d in meteo_data]

        # Sensibilité moyenne des cépages
        sensibilites = [self.config.SENSIBILITES_CEPAGES.get(c, 5)
                        for c in parcelle['cepages']]
        sensibilite_moy = sum(sensibilites) / len(sensibilites)

        stade_coef = self.config.COEF_STADES.get(parcelle['stade_actuel'], 1.0)

        # MODÈLE SIMPLE
        risque_simple, niveau_simple = self.modele_simple.calculer_risque_infection(
            meteo_48h, stade_coef, sensibilite_moy
        )

        if debug:
            print("\n🔍 MODE DEBUG - CALCUL RISQUE SIMPLE")
            print(f"Pluie 48h: {sum(m.get('precipitation', 0) for m in meteo_48h):.1f}mm")
            temp_moy_48h = sum(m.get('temp_moy', 0) for m in meteo_48h)/len(meteo_48h) if meteo_48h else 0
            print(f"Temp moyenne 48h: {temp_moy_48h:.1f}°C")
            print(f"Coef stade: {stade_coef}")
            print(f"Sensibilité cépages: {sensibilite_moy:.1f}")
            print(f"→ Score: {risque_simple}/10 ({niveau_simple})")

        # MODÈLE IPI
        ipi_value = None
        ipi_risque = "N/A"

        if utiliser_ipi and meteo_48h and stade_coef > 0.0:
            jour_max_pluie = max(meteo_48h, key=lambda x: x.get('precipitation', 0))

            if jour_max_pluie.get('precipitation', 0) >= 2:
                duree_humect = self.modele_ipi.estimer_duree_humectation(
                    jour_max_pluie['precipitation'],
                    jour_max_pluie['humidite']
                )
                if duree_humect > 0:
                    ipi_value = self.modele_ipi.calculer_ipi(jour_max_pluie, duree_humect)

                    if ipi_value >= 60:
                        ipi_risque = "FORT"
                    elif ipi_value >= 30:
                        ipi_risque = "MOYEN"
                    else:
                        ipi_risque = "FAIBLE"

                    if debug:
                        print("\n🔍 MODE DEBUG - CALCUL IPI")
                        print(f"Jour max pluie: {jour_max_pluie['precipitation']:.1f}mm")
                        print(f"Température: {jour_max_pluie['temp_moy']:.1f}°C")
                        print(f"Humidité: {jour_max_pluie['humidite']:.0f}%")
                        print(f"Durée humectation: {duree_humect:.1f}h")
                        print(f"→ IPI: {ipi_value}/100 ({ipi_risque})")
                else:
                    ipi_value = 0
                    ipi_risque = "FAIBLE (Humect. Nulle)"
            else:
                ipi_value = 0
                ipi_risque = "FAIBLE (Pluie Insuff.)"
        elif utiliser_ipi:
            ipi_value = 0
            ipi_risque = "NUL (Repos végétatif)"

        # PROTECTION ACTUELLE
        protection, dernier_trait, facteur_limitant = self.traitements.calculer_protection_actuelle(
            nom_parcelle, date_actuelle, meteo_data, parcelle['stade_actuel']
        )

        if debug:
            print("\n🔍 MODE DEBUG - PROTECTION")
            print(f"Stade: {parcelle['stade_actuel']}")
            print(f"Coef pousse: {self.traitements.COEF_POUSSE.get(parcelle['stade_actuel'], 1.0)}")
            print(f"→ Protection: {protection}/10 (Limité par: {facteur_limitant})")

        # DÉCISION
        score_decision = risque_simple - protection

        if score_decision >= self.SEUIL_DECISION_HAUTE:
            decision = "TRAITER MAINTENANT"
            urgence = "haute"
        elif score_decision >= self.SEUIL_DECISION_MOYENNE:
            decision = "Surveiller - Traiter si pluie annoncée"
            urgence = "moyenne"
        else:
            decision = "Pas de traitement nécessaire"
            urgence = "faible"

        # PRÉVISIONS
        dates_futures = sorted([d for d in meteo_data.keys() if d > date_actuelle])[:3]
        pluie_prevue = sum(meteo_data[d]['precipitation'] for d in dates_futures)

        alerte_preventive = ""
        if pluie_prevue > self.SEUIL_ALERTE_PLUIE and protection < self.SEUIL_PROTECTION_FAIBLE:
            alerte_preventive = f"⚠️  Pluie de {pluie_prevue:.1f}mm prévue - Traitement préventif recommandé"

        analyse = {
            'parcelle': nom_parcelle,
            'date_analyse': date_actuelle,
            'cepages': parcelle['cepages'],
            'stade': parcelle['stade_actuel'],
            'meteo_actuelle': meteo_data.get(date_actuelle, {}),
            'risque_infection': {
                'score': risque_simple,
                'niveau': niveau_simple,
                'ipi': ipi_value,
                'ipi_niveau': ipi_risque
            },
            'protection_actuelle': {
                'score': protection,
                'dernier_traitement': dernier_trait,
                'facteur_limitant': facteur_limitant
            },
            'decision': {
                'score': round(score_decision, 1),
                'action': decision,
                'urgence': urgence,
                'alerte_preventive': alerte_preventive
            },
            'previsions_3j': {
                'pluie_totale': round(pluie_prevue, 1),
                'details': {d: meteo_data[d] for d in dates_futures}
            }
        }

        # Stocker pour historique graphique
        self.historique_analyses.append({
            'date': date_actuelle,
            'parcelle': nom_parcelle,
            'risque': risque_simple,
            'protection': protection,
            'decision_score': score_decision
        })
        try:
            self.historique_alertes.ajouter_analyse(analyse)
        except Exception as e:
            print(f"⚠️ Erreur sauvegarde historique : {e}")

        return analyse

    def afficher_rapport(self, analyse: Dict):
        """Affiche un rapport formaté de l'analyse"""
        print("\n" + "="*60)
        print(f"   ANALYSE MILDIOU - {analyse['parcelle']}")
        print("="*60)
        print(f"Date: {analyse['date_analyse']}")
        print(f"Cépages: {', '.join(analyse['cepages'])}")
        print(f"Stade phénologique: {analyse['stade']}")
        print("-"*60)

        meteo = analyse['meteo_actuelle']
        print(f"\n🌡️  MÉTÉO ACTUELLE")
        print(f"   Température: {meteo.get('temp_min', 'N/A')}°C - {meteo.get('temp_max', 'N/A')}°C")
        print(f"   Précipitations: {meteo.get('precipitation', 0):.1f} mm")
        print(f"   Humidité: {meteo.get('humidite', 'N/A'):.0f}%")

        risque = analyse['risque_infection']
        print(f"\n🦠 RISQUE INFECTION: {risque['niveau']}")
        print(f"   Score modèle simple: {risque['score']}/10")
        if risque['ipi'] is not None:
            print(f"   IPI: {risque['ipi']}/100 ({risque['ipi_niveau']})")
            if risque['ipi_niveau'] not in ["NUL (Repos végétatif)", "FAIBLE (Pluie Insuff.)"]:
                print(f"   💡 Note: IPI évalue la sévérité potentielle si infection")

        prot = analyse['protection_actuelle']
        print(f"\n🛡️  PROTECTION ACTUELLE: {prot['score']}/10")
        if prot['dernier_traitement']:
            dt = prot['dernier_traitement']
            print(f"   Dernier traitement: {dt['date']}")
            print(f"   Produit: {dt['caracteristiques'].get('nom', 'N/A')}")
            print(f"   Facteur limitant: {prot['facteur_limitant']}")

            if 'Pousse' in prot['facteur_limitant']:
                print(f"   ⚠️  Forte pousse active : renouveler plus fréquemment")
        else:
            print("   Aucun traitement enregistré.")

        dec = analyse['decision']
        print(f"\n{'='*60}")
        print(f"➜  DÉCISION: {dec['action']}")
        print(f"   Score décision: {dec['score']}/10")
        print(f"   Urgence: {dec['urgence'].upper()}")
        if dec['alerte_preventive']:
            print(f"\n   {dec['alerte_preventive']}")
        print("="*60)

        prev = analyse['previsions_3j']
        print(f"\n📅 PRÉVISIONS 3 JOURS")
        print(f"   Cumul pluie prévu: {prev['pluie_totale']} mm")
        print()

    def generer_graphique_evolution(self, parcelle: str, nb_jours: int = 30,
                                   fichier_sortie: str = 'evolution_risque.png'):
        """
        Génère un graphique d'évolution du risque et de la protection
        """
        if not GRAPHIQUES_DISPONIBLES:
            print("⚠️  matplotlib non installé. Graphiques non disponibles.")
            return

        # Récupérer les données météo historiques
        meteo_data = self.meteo.get_meteo_data(days_past=nb_jours, days_future=0)
        if not meteo_data:
            print("❌ Impossible de générer le graphique")
            return

        dates = []
        risques = []
        protections = []

        date_fin = datetime.now()

        for i in range(nb_jours, -1, -1):
            date = (date_fin - timedelta(days=i)).strftime('%Y-%m-%d')

            if date not in meteo_data:
                continue

            dates.append(datetime.strptime(date, '%Y-%m-%d'))

            # Calculer risque pour cette date
            date_48h_avant = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=2)).strftime('%Y-%m-%d')
            meteo_48h = []
            for j in range(3):
                d = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=2-j)).strftime('%Y-%m-%d')
                if d in meteo_data:
                    meteo_48h.append(meteo_data[d])

            parcelle_obj = next((p for p in self.config.parcelles if p['nom'] == parcelle), None)
            if parcelle_obj:
                sensibilites = [self.config.SENSIBILITES_CEPAGES.get(c, 5) for c in parcelle_obj['cepages']]
                sensibilite_moy = sum(sensibilites) / len(sensibilites)
                stade_coef = self.config.COEF_STADES.get(parcelle_obj['stade_actuel'], 1.0)

                risque, _ = self.modele_simple.calculer_risque_infection(meteo_48h, stade_coef, sensibilite_moy)
                protection, _, _ = self.traitements.calculer_protection_actuelle(
                    parcelle, date, meteo_data, parcelle_obj['stade_actuel']
                )

                risques.append(risque)
                protections.append(protection)

        # Créer le graphique
        fig, ax = plt.subplots(figsize=(12, 6))

        ax.plot(dates, risques, 'r-', linewidth=2, label='Risque infection', marker='o')
        ax.plot(dates, protections, 'g-', linewidth=2, label='Protection', marker='s')

        # Zone de décision
        ax.axhline(y=self.SEUIL_DECISION_HAUTE, color='orange', linestyle='--',
                   label=f'Seuil traitement ({self.SEUIL_DECISION_HAUTE}/10)')

        ax.fill_between(dates, 0, risques, alpha=0.2, color='red')
        ax.fill_between(dates, 0, protections, alpha=0.2, color='green')

        ax.set_xlabel('Date', fontsize=12)
        ax.set_ylabel('Score (0-10)', fontsize=12)
        ax.set_title(f'Évolution Risque/Protection - {parcelle}', fontsize=14, fontweight='bold')
        ax.legend(loc='best', fontsize=10)
        ax.grid(True, alpha=0.3)

        # Format des dates
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=max(1, nb_jours//10)))
        plt.xticks(rotation=45)

        plt.tight_layout()
        plt.savefig(fichier_sortie, dpi=150)
        print(f"✅ Graphique sauvegardé : {fichier_sortie}")
        plt.close()

    def exporter_analyses_csv(self, fichier: str = 'historique_analyses.csv'):
        """Exporte l'historique des analyses en CSV"""
        if not self.historique_analyses:
            print("⚠️  Aucune analyse à exporter")
            return

        with open(fichier, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['date', 'parcelle', 'risque', 'protection', 'decision_score'])
            writer.writeheader()
            writer.writerows(self.historique_analyses)

        print(f"✅ Historique exporté : {fichier}")

    def generer_synthese_annuelle(self, annee: int, fichier_sortie: str = None):
        """
        Génère une synthèse complète de l'année viticole
        """
        if fichier_sortie is None:
            fichier_sortie = f'synthese_{annee}.txt'

        date_debut = f"{annee}-01-01"
        date_fin = f"{annee}-12-31"

        # Calcul IFT
        ift = self.traitements.calculer_ift_periode(date_debut, date_fin, self.config.surface_totale)

        # Statistiques par parcelle
        stats_parcelles = {}
        for parcelle in self.config.parcelles:
            traitements_parcelle = [
                t for t in self.traitements.historique['traitements']
                if t['parcelle'] == parcelle['nom'] and date_debut <= t['date'] <= date_fin
            ]
            stats_parcelles[parcelle['nom']] = {
                'nb_traitements': len(traitements_parcelle),
                'surface_ha': parcelle['surface_ha'],
                'cepages': parcelle['cepages']
            }

        # Générer le rapport
        with open(fichier_sortie, 'w', encoding='utf-8') as f:
            f.write("="*70 + "\n")
            f.write(f"   SYNTHÈSE ANNUELLE MILDIOU - {annee}\n")
            f.write(f"   {self.config.config_file.replace('.json', '').upper()}\n")
            f.write("="*70 + "\n\n")

            f.write(f"📊 DONNÉES GÉNÉRALES\n")
            f.write(f"   Surface totale : {self.config.surface_totale} ha\n")
            f.write(f"   Nombre de parcelles : {len(self.config.parcelles)}\n")
            f.write(f"   Période d'analyse : {date_debut} au {date_fin}\n\n")

            f.write(f"💊 BILAN TRAITEMENTS\n")
            f.write(f"   Nombre total de traitements : {ift['nb_traitements']}\n")
            f.write(f"   IFT total : {ift['ift_total']}\n")
            f.write(f"   IFT moyen par hectare : {ift['ift_total']/self.config.surface_totale:.2f}\n\n")

            f.write(f"📋 DÉTAIL PAR PARCELLE\n")
            f.write("-"*70 + "\n")
            for nom, stats in stats_parcelles.items():
                f.write(f"\n🍇 {nom}\n")
                f.write(f"   Surface : {stats['surface_ha']} ha\n")
                f.write(f"   Cépages : {', '.join(stats['cepages'])}\n")
                f.write(f"   Traitements : {stats['nb_traitements']}\n")
                ift_parcelle = stats['nb_traitements']  # Simplification
                f.write(f"   IFT estimé : {ift_parcelle}\n")

            f.write("\n" + "-"*70 + "\n")
            f.write(f"📅 HISTORIQUE DES TRAITEMENTS\n")
            f.write("-"*70 + "\n")

            for detail in ift['details']:
                f.write(f"\n{detail['date']} - {detail['parcelle']}\n")
                f.write(f"   Produit : {detail['produit']}\n")
                f.write(f"   IFT : {detail['ift']}\n")

            f.write("\n" + "="*70 + "\n")
            f.write(f"💡 RECOMMANDATIONS\n")
            f.write("="*70 + "\n")

            if ift['ift_total'] > 15:
                f.write("⚠️  IFT élevé : Envisager des stratégies de réduction\n")
                f.write("   - Optimiser le positionnement des traitements\n")
                f.write("   - Privilégier les produits longue rémanence\n")
                f.write("   - Évaluer les cépages résistants\n")
            elif ift['ift_total'] < 8:
                f.write("✅ IFT maîtrisé : Bonne gestion phytosanitaire\n")
            else:
                f.write("✓  IFT dans la moyenne nationale\n")

            f.write("\n" + "="*70 + "\n")
            f.write(f"Rapport généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}\n")
            f.write("="*70 + "\n")

        print(f"✅ Synthèse annuelle générée : {fichier_sortie}")

        # Afficher aussi à l'écran
        with open(fichier_sortie, 'r', encoding='utf-8') as f:
            print("\n" + f.read())


# PROGRAMME PRINCIPAL
def menu_principal():
    """Menu interactif principal"""
    systeme = SystemeDecision()

    while True:
        print("\n" + "="*70)
        print("🍇 SYSTÈME DE PRÉVISION MILDIOU - MENU PRINCIPAL")
        print("="*70)
        print("\n1️⃣  Analyser toutes les parcelles")
        print("2️⃣  Analyser une parcelle spécifique")
        print("3️⃣  Enregistrer un traitement")
        print("4️⃣  Générer graphique d'évolution")
        print("5️⃣  Calculer IFT d'une période")
        print("6️⃣  Générer synthèse annuelle")
        print("7️⃣  Exporter historique CSV")
        print("8️⃣  Liste des fongicides disponibles")
        print("9️⃣  Quitter")

        choix = input("\n➜ Votre choix (1-9) : ").strip()

        if choix == '1':
            print("\n" + "="*70)
            print("📊 ANALYSE DE TOUTES LES PARCELLES")
            print("="*70)
            for parcelle in systeme.config.parcelles:
                analyse = systeme.analyser_parcelle(parcelle['nom'], utiliser_ipi=True)
                if 'erreur' not in analyse:
                    systeme.afficher_rapport(analyse)
                else:
                    print(f"❌ {analyse['erreur']}")

        elif choix == '2':
            print("\n📍 Parcelles disponibles :")
            for i, p in enumerate(systeme.config.parcelles, 1):
                print(f"   {i}. {p['nom']}")

            try:
                idx = int(input("\n➜ Numéro de la parcelle : ")) - 1
                parcelle = systeme.config.parcelles[idx]

                debug = input("Mode debug ? (o/n) : ").lower() == 'o'
                analyse = systeme.analyser_parcelle(parcelle['nom'], utiliser_ipi=True, debug=debug)

                if 'erreur' not in analyse:
                    systeme.afficher_rapport(analyse)
                else:
                    print(f"❌ {analyse['erreur']}")
            except (ValueError, IndexError):
                print("❌ Choix invalide")

        elif choix == '3':
            print("\n💊 ENREGISTREMENT D'UN TRAITEMENT")
            print("-"*70)

            print("\nParcelles disponibles :")
            for i, p in enumerate(systeme.config.parcelles, 1):
                print(f"   {i}. {p['nom']}")

            try:
                idx = int(input("\n➜ Numéro de la parcelle : ")) - 1
                parcelle = systeme.config.parcelles[idx]['nom']

                date = input("Date du traitement (YYYY-MM-DD) ou [Entrée]=aujourd'hui : ").strip()
                if not date:
                    date = datetime.now().strftime('%Y-%m-%d')

                print("\nProduits disponibles :")
                produits = list(systeme.traitements.FONGICIDES.keys())
                for i, p in enumerate(produits, 1):
                    print(f"   {i}. {systeme.traitements.FONGICIDES[p]['nom']}")

                prod_idx = int(input("\n➜ Numéro du produit : ")) - 1
                produit = produits[prod_idx]

                dose = input(f"Dose (kg/ha) ou [Entrée]=dose référence : ").strip()
                dose = float(dose) if dose else None

                systeme.traitements.ajouter_traitement(parcelle, date, produit, dose)

            except (ValueError, IndexError):
                print("❌ Entrée invalide")

        elif choix == '4':
            if not GRAPHIQUES_DISPONIBLES:
                print("\n❌ matplotlib non installé")
                print("   Installation : pip install matplotlib")
                continue

            print("\n📈 GÉNÉRATION DE GRAPHIQUE")
            print("-"*70)

            print("\nParcelles disponibles :")
            for i, p in enumerate(systeme.config.parcelles, 1):
                print(f"   {i}. {p['nom']}")

            try:
                idx = int(input("\n➜ Numéro de la parcelle : ")) - 1
                parcelle = systeme.config.parcelles[idx]['nom']

                nb_jours = input("Nombre de jours (défaut=30) : ").strip()
                nb_jours = int(nb_jours) if nb_jours else 30

                fichier = f"evolution_{parcelle.replace(' ', '_')}.png"
                systeme.generer_graphique_evolution(parcelle, nb_jours, fichier)

            except (ValueError, IndexError):
                print("❌ Entrée invalide")

        elif choix == '5':
            print("\n📊 CALCUL IFT")
            print("-"*70)

            date_debut = input("Date début (YYYY-MM-DD) : ").strip()
            date_fin = input("Date fin (YYYY-MM-DD) : ").strip()

            if date_debut and date_fin:
                ift = systeme.traitements.calculer_ift_periode(
                    date_debut, date_fin, systeme.config.surface_totale
                )

                print(f"\n{'='*70}")
                print(f"IFT PÉRIODE : {ift['periode']}")
                print(f"{'='*70}")
                print(f"IFT total : {ift['ift_total']}")
                print(f"IFT moyen/ha : {ift['ift_total']/systeme.config.surface_totale:.2f}")
                print(f"Nombre de traitements : {ift['nb_traitements']}")

                if ift['details']:
                    print(f"\nDétail :")
                    for d in ift['details']:
                        print(f"  {d['date']} - {d['parcelle']} - {d['produit']} (IFT: {d['ift']})")

        elif choix == '6':
            print("\n📑 SYNTHÈSE ANNUELLE")
            print("-"*70)

            annee = input(f"Année (défaut={datetime.now().year}) : ").strip()
            annee = int(annee) if annee else datetime.now().year

            systeme.generer_synthese_annuelle(annee)

        elif choix == '7':
            systeme.exporter_analyses_csv()

        elif choix == '8':
            print("\n💊 FONGICIDES DISPONIBLES")
            print("="*70)

            for code, info in systeme.traitements.FONGICIDES.items():
                print(f"\n🔹 {info['nom']}")
                print(f"   Code : {code}")
                print(f"   Type : {info['type']}")
                print(f"   Persistance : {info['persistance_jours']} jours")
                print(f"   Seuil lessivage : {info['lessivage_seuil_mm']} mm")
                print(f"   Dose référence : {info['dose_reference_kg_ha']} kg/ha")

        elif choix == '9':
            print("\n👋 Au revoir et bonnes vendanges !")
            break

        else:
            print("\n❌ Choix invalide")

        input("\n[Appuyez sur Entrée pour continuer]")


if __name__ == "__main__":
    menu_principal()