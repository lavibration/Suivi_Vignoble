"""
Application Web Streamlit - Système de Prévision Mildiou
Page d'accueil : Vue d'ensemble + Gestion stades phénologiques
"""

import streamlit as st
from datetime import datetime
import sys
import os
import json

# Ajouter le répertoire parent au path pour importer mildiou_prevention
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mildiou_prevention import SystemeDecision

# Configuration de la page
st.set_page_config(
    page_title="Prévision Mildiou",
    page_icon="🍇",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Style CSS personnalisé
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        color: #2E7D32;
        margin-bottom: 1rem;
    }
    .alert-high {
        background-color: rgba(198, 40, 40, 0.15);
        border-left: 4px solid #c62828;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .alert-medium {
        background-color: rgba(239, 108, 0, 0.15);
        border-left: 4px solid #ef6c00;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
    .alert-low {
        background-color: rgba(46, 125, 50, 0.15);
        border-left: 4px solid #2e7d32;
        padding: 1rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialisation du système (avec cache pour performance)
@st.cache_resource
def init_systeme():
    return SystemeDecision()

# Fonction pour sauvegarder le stade d'une parcelle
def sauvegarder_stade(parcelle_nom, nouveau_stade):
    """Sauvegarde le nouveau stade dans config_vignoble.json"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(script_dir, 'config_vignoble.json')

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Mettre à jour le stade
        for parcelle in config['parcelles']:
            if parcelle['nom'] == parcelle_nom:
                parcelle['stade_actuel'] = nouveau_stade
                break

        # Sauvegarder
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

        return True
    except Exception as e:
        st.error(f"Erreur lors de la sauvegarde : {e}")
        return False

# Fonction pour obtenir la couleur selon l'urgence
def get_urgence_color(urgence):
    colors = {
        'haute': '🔴',
        'moyenne': '🟠',
        'faible': '🟢'
    }
    return colors.get(urgence, '⚪')

# Fonction pour obtenir la classe CSS selon l'urgence
def get_alert_class(urgence):
    classes = {
        'haute': 'alert-high',
        'moyenne': 'alert-medium',
        'faible': 'alert-low'
    }
    return classes.get(urgence, 'alert-low')

# Header
st.markdown('<p class="main-header">🍇 Système de Prévision Mildiou</p>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.title("⚙️ Navigation")
    st.markdown("---")

    # Informations système
    try:
        systeme = init_systeme()
        st.success(f"✅ {len(systeme.config.parcelles)} parcelles configurées")
        st.success(f"✅ {systeme.config.surface_totale:.1f} ha total")
    except Exception as e:
        st.error(f"❌ Erreur de chargement : {e}")
        st.stop()

    st.markdown("---")

    # Options d'affichage
    st.subheader("🎨 Affichage")
    afficher_ipi = st.checkbox("Afficher IPI", value=True)
    afficher_meteo = st.checkbox("Afficher météo", value=True)

# Main content
try:
    systeme = init_systeme()

    # Date et heure actuelles
    col_date, col_refresh = st.columns([3, 1])
    with col_date:
        st.caption(f"📅 Dernière mise à jour : {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    with col_refresh:
        if st.button("🔄 Actualiser"):
            st.cache_resource.clear()
            st.rerun()

    st.markdown("---")

    # NOUVELLE SECTION : Gestion des stades phénologiques
    with st.expander("🌱 Modifier les Stades Phénologiques", expanded=False):
        st.subheader("Mise à jour des stades végétatifs")

        stades_disponibles = [
            'repos',
            'debourrement',
            'pousse_10cm',
            'pre_floraison',
            'floraison',
            'nouaison',
            'fermeture_grappe',
            'veraison',
            'maturation'
        ]

        # Descriptions des stades
        descriptions_stades = {
            'repos': '🛌 Repos hivernal',
            'debourrement': '🌱 Débourrement (bourgeon éclaté)',
            'pousse_10cm': '📏 Pousse active (>10cm)',
            'pre_floraison': '🌸 Pré-floraison',
            'floraison': '💐 Floraison',
            'nouaison': '🫐 Nouaison (formation grains)',
            'fermeture_grappe': '🍇 Fermeture de la grappe',
            'veraison': '🎨 Véraison (changement couleur)',
            'maturation': '🍷 Maturation'
        }

        cols_stades = st.columns(len(systeme.config.parcelles))

        for idx, parcelle in enumerate(systeme.config.parcelles):
            with cols_stades[idx]:
                st.markdown(f"**{parcelle['nom']}**")

                # Stade actuel
                stade_actuel = parcelle['stade_actuel']
                st.caption(f"Stade actuel : {descriptions_stades.get(stade_actuel, stade_actuel)}")

                # Sélecteur nouveau stade
                index_actuel = stades_disponibles.index(stade_actuel) if stade_actuel in stades_disponibles else 0

                nouveau_stade = st.selectbox(
                    "Nouveau stade",
                    stades_disponibles,
                    index=index_actuel,
                    format_func=lambda x: descriptions_stades.get(x, x),
                    key=f"stade_{parcelle['nom']}"
                )

                # Afficher coefficients
                coef_risque = systeme.config.COEF_STADES.get(nouveau_stade, 0)
                coef_pousse = systeme.traitements.COEF_POUSSE.get(nouveau_stade, 0)

                st.caption(f"Coef. risque : {coef_risque}")
                st.caption(f"Coef. pousse : {coef_pousse}")

                # Bouton sauvegarde
                if nouveau_stade != stade_actuel:
                    if st.button(f"💾 Sauvegarder", key=f"save_{parcelle['nom']}", type="primary"):
                        if sauvegarder_stade(parcelle['nom'], nouveau_stade):
                            st.success(f"✅ Stade mis à jour !")
                            st.cache_resource.clear()
                            st.rerun()

    st.markdown("---")

    # Section Alertes Urgentes
    st.subheader("🚨 Alertes et Recommandations")

    alertes_urgentes = []

    for parcelle in systeme.config.parcelles:
        analyse = systeme.analyser_parcelle(parcelle['nom'], utiliser_ipi=afficher_ipi)

        if 'erreur' not in analyse:
            decision = analyse['decision']

            if decision['urgence'] in ['haute', 'moyenne']:
                alertes_urgentes.append({
                    'parcelle': parcelle['nom'],
                    'urgence': decision['urgence'],
                    'action': decision['action'],
                    'alerte': decision.get('alerte_preventive', '')
                })

    if alertes_urgentes:
        for alerte in alertes_urgentes:
            alert_class = get_alert_class(alerte['urgence'])
            urgence_icon = get_urgence_color(alerte['urgence'])

            st.markdown(f"""
            <div class="{alert_class}">
                <strong>{urgence_icon} {alerte['parcelle']}</strong><br>
                ➜ {alerte['action']}<br>
                {alerte['alerte'] if alerte['alerte'] else ''}
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="alert-low">
            <strong>🟢 Aucune alerte</strong><br>
            Toutes vos parcelles sont sous contrôle.
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Section Vue d'ensemble des parcelles
    st.subheader("📊 Vue d'Ensemble des Parcelles")

    # Créer les colonnes pour les cartes parcelles
    nb_parcelles = len(systeme.config.parcelles)
    cols = st.columns(min(nb_parcelles, 3))

    for idx, parcelle in enumerate(systeme.config.parcelles):
        col = cols[idx % min(nb_parcelles, 3)]

        with col:
            analyse = systeme.analyser_parcelle(parcelle['nom'], utiliser_ipi=afficher_ipi)

            if 'erreur' in analyse:
                st.error(f"Erreur : {analyse['erreur']}")
                continue

            # Carte parcelle avec conteneur pour meilleure visibilité
            with st.container(border=True):
                st.markdown(f"### 🍇 {parcelle['nom']}")

                # Badges informatifs
                col_info1, col_info2 = st.columns(2)
                with col_info1:
                    st.caption(f"🌱 {', '.join(parcelle['cepages'][:2])}")
                    if len(parcelle['cepages']) > 2:
                        st.caption(f"   +{len(parcelle['cepages'])-2} autres")
                with col_info2:
                    st.caption(f"📏 {parcelle['surface_ha']} ha")
                    st.caption(f"🌿 {parcelle['stade_actuel']}")

                st.markdown("---")

                # Métriques principales
                risque = analyse['risque_infection']
                protection = analyse['protection_actuelle']
                decision = analyse['decision']

                col_m1, col_m2 = st.columns(2)

                with col_m1:
                    st.metric(
                        "🦠 Risque",
                        f"{risque['score']}/10",
                        delta=risque['niveau'],
                        help=f"Niveau : {risque['niveau']}"
                    )

                with col_m2:
                    st.metric(
                        "🛡️ Protection",
                        f"{protection['score']}/10",
                        delta=None,
                        help=f"Limité par : {protection.get('facteur_limitant', 'N/A')}"
                    )

                # IPI si activé
                if afficher_ipi and risque['ipi'] is not None:
                    st.metric(
                        "📊 IPI",
                        f"{risque['ipi']}/100",
                        delta=risque.get('ipi_niveau', 'N/A'),
                        help=f"Niveau : {risque.get('ipi_niveau', 'N/A')}"
                    )

                # Décision avec couleur
                urgence_icon = get_urgence_color(decision['urgence'])

                if decision['urgence'] == 'haute':
                    st.error(f"**{urgence_icon} {decision['action']}**")
                elif decision['urgence'] == 'moyenne':
                    st.warning(f"**{urgence_icon} {decision['action']}**")
                else:
                    st.success(f"**{urgence_icon} {decision['action']}**")

                # Bouton détails
                if st.button(f"🔍 Voir Détails", key=f"details_{parcelle['nom']}", use_container_width=True):
                    st.switch_page("pages/1_Analyse_Detaillee.py")

    st.markdown("---")

    # Section Météo (si activée)
    if afficher_meteo:
        st.subheader("🌤️ Conditions Météorologiques")

        # Récupérer données météo
        meteo_data = systeme.meteo.get_meteo_data(days_past=1, days_future=3)

        if meteo_data:
            date_actuelle = datetime.now().strftime('%Y-%m-%d')
            meteo_actuelle = meteo_data.get(date_actuelle, {})

            col_m1, col_m2, col_m3, col_m4 = st.columns(4)

            with col_m1:
                st.metric(
                    "🌡️ Température",
                    f"{meteo_actuelle.get('temp_moy', 0):.1f}°C",
                    delta=f"{meteo_actuelle.get('temp_max', 0) - meteo_actuelle.get('temp_min', 0):.1f}°C écart"
                )

            with col_m2:
                st.metric(
                    "💧 Précipitations",
                    f"{meteo_actuelle.get('precipitation', 0):.1f} mm",
                    delta=None
                )

            with col_m3:
                st.metric(
                    "💨 Humidité",
                    f"{meteo_actuelle.get('humidite', 0):.0f}%",
                    delta=None
                )

            with col_m4:
                # Prévisions 3 jours
                dates_futures = sorted([d for d in meteo_data.keys() if d > date_actuelle])[:3]
                pluie_prevue = sum(meteo_data[d]['precipitation'] for d in dates_futures)
                st.metric(
                    "🌧️ Pluie prévue 3j",
                    f"{pluie_prevue:.1f} mm",
                    delta=None
                )
        else:
            st.warning("⚠️ Impossible de récupérer les données météo")

    st.markdown("---")

    # Section Statistiques Globales
    st.subheader("📈 Statistiques Globales")

    col_s1, col_s2, col_s3, col_s4 = st.columns(4)

    # Calculer stats
    nb_alertes_haute = len([a for a in alertes_urgentes if a['urgence'] == 'haute'])
    nb_alertes_moyenne = len([a for a in alertes_urgentes if a['urgence'] == 'moyenne'])

    # Compter traitements du mois
    date_debut_mois = datetime.now().replace(day=1).strftime('%Y-%m-%d')
    date_fin = datetime.now().strftime('%Y-%m-%d')

    traitements_mois = [
        t for t in systeme.traitements.historique.get('traitements', [])
        if date_debut_mois <= t['date'] <= date_fin
    ]

    with col_s1:
        st.metric("🚨 Alertes Urgentes", nb_alertes_haute)

    with col_s2:
        st.metric("⚠️ Alertes Moyennes", nb_alertes_moyenne)

    with col_s3:
        st.metric("💊 Traitements ce mois", len(traitements_mois))

    with col_s4:
        # Calcul IFT année en cours
        annee = datetime.now().year
        ift = systeme.traitements.calculer_ift_periode(
            f"{annee}-01-01",
            date_fin,
            systeme.config.surface_totale
        )
        st.metric("🧾 IFT Année", f"{ift['ift_total']:.1f}")

    st.markdown("---")

    # Footer
    st.caption("""
    💡 **Conseils d'utilisation :**
    - Consultez cette page chaque matin pour les alertes
    - Mettez à jour les stades phénologiques régulièrement (expander en haut)
    - Enregistrez vos traitements immédiatement après application
    - Utilisez les pages détaillées pour analyses approfondies
    """)

    st.caption("---")
    st.caption(f"🍇 Système Mildiou v1.0 | {systeme.config.config_file}")

except Exception as e:
    st.error(f"""
    ❌ **Erreur lors du chargement**
    
    {str(e)}
    
    Vérifiez que :
    - Le fichier `config_vignoble.json` existe
    - Le fichier `mildiou_prevention.py` est présent
    - Vous avez une connexion internet pour la météo
    """)
    st.stop()