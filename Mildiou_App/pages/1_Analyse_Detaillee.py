"""
Page Analyse Détaillée d'une Parcelle
Avec mode debug et détails complets
Fichier : pages/1_Analyse_Detaillee.py
"""

import streamlit as st
import sys
import os
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mildiou_prevention import SystemeDecision

st.set_page_config(page_title="Analyse Détaillée", page_icon="🔍", layout="wide")

# Style
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .debug-box {
        background-color: #263238;
        color: #aed581;
        padding: 1rem;
        border-radius: 0.5rem;
        font-family: monospace;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.title("🔍 Analyse Détaillée d'une Parcelle")

# Initialiser le système
@st.cache_resource
def init_systeme():
    return SystemeDecision()

try:
    systeme = init_systeme()

    # Sidebar - Sélection parcelle
    with st.sidebar:
        st.subheader("📍 Sélection Parcelle")

        parcelle_names = [p['nom'] for p in systeme.config.parcelles]
        parcelle_selectionnee = st.selectbox(
            "Choisir une parcelle",
            parcelle_names,
            key="parcelle_select"
        )

        st.markdown("---")

        # Options d'analyse
        st.subheader("⚙️ Options d'Analyse")
        utiliser_ipi = st.checkbox("Activer modèle IPI", value=True)
        mode_debug = st.checkbox("Mode Debug", value=False,
                                help="Affiche les calculs détaillés")

        st.markdown("---")

        # Bouton analyse
        if st.button("🔄 Actualiser l'analyse", type="primary"):
            st.cache_data.clear()
            st.rerun()

    # Analyse
    if parcelle_selectionnee:
        # Onglets principaux
        tab1, tab2, tab3 = st.tabs(["📊 Synthèse", "🔬 Détails Techniques", "📅 Historique"])

        # Récupérer l'analyse
        analyse = systeme.analyser_parcelle(parcelle_selectionnee, utiliser_ipi=utiliser_ipi, debug=False)

        if 'erreur' in analyse:
            st.error(f"❌ {analyse['erreur']}")
            st.stop()

        # TAB 1 : Synthèse
        with tab1:
            # Informations parcelle
            parcelle_obj = next(p for p in systeme.config.parcelles if p['nom'] == parcelle_selectionnee)

            col_info1, col_info2, col_info3 = st.columns(3)

            with col_info1:
                st.markdown("### 📍 Parcelle")
                st.markdown(f"**Nom :** {parcelle_obj['nom']}")
                st.markdown(f"**Surface :** {parcelle_obj['surface_ha']} ha")

            with col_info2:
                st.markdown("### 🍇 Cépages")
                for cepage in parcelle_obj['cepages']:
                    st.markdown(f"- {cepage}")

            with col_info3:
                st.markdown("### 🌱 Stade Actuel")
                st.markdown(f"**{parcelle_obj['stade_actuel']}**")
                coef_stade = systeme.config.COEF_STADES.get(parcelle_obj['stade_actuel'], 0)
                coef_pousse = systeme.traitements.COEF_POUSSE.get(parcelle_obj['stade_actuel'], 0)
                st.caption(f"Coef. risque : {coef_stade}")
                st.caption(f"Coef. pousse : {coef_pousse}")

            st.markdown("---")

            # Métriques principales
            st.subheader("📊 Évaluation Actuelle")

            col_m1, col_m2, col_m3 = st.columns(3)

            risque = analyse['risque_infection']
            protection = analyse['protection_actuelle']
            decision = analyse['decision']

            with col_m1:
                # Indicateur visuel risque
                risque_color = "🔴" if risque['score'] >= 7 else ("🟠" if risque['score'] >= 4 else "🟢")
                st.metric(
                    f"{risque_color} Risque d'Infection",
                    f"{risque['score']}/10",
                    delta=risque['niveau'],
                    help="Basé sur météo 48h + stade + sensibilité"
                )

                if utiliser_ipi and risque['ipi'] is not None:
                    st.metric(
                        "IPI (Indice Potentiel)",
                        f"{risque['ipi']}/100",
                        delta=risque.get('ipi_niveau', 'N/A'),
                        help="Évalue la sévérité si infection"
                    )

            with col_m2:
                # Indicateur visuel protection
                prot_color = "🟢" if protection['score'] >= 7 else ("🟠" if protection['score'] >= 4 else "🔴")
                st.metric(
                    f"{prot_color} Protection Résiduelle",
                    f"{protection['score']}/10",
                    delta=None,
                    help=f"Limité par : {protection.get('facteur_limitant', 'N/A')}"
                )

                if protection['dernier_traitement']:
                    dt = protection['dernier_traitement']
                    st.caption(f"Dernier trait. : {dt['date']}")
                    st.caption(f"Produit : {dt['caracteristiques'].get('nom', 'N/A')}")
                else:
                    st.caption("Aucun traitement enregistré")

            with col_m3:
                # Score décision
                dec_color = "🔴" if decision['urgence'] == 'haute' else ("🟠" if decision['urgence'] == 'moyenne' else "🟢")
                st.metric(
                    f"{dec_color} Score Décision",
                    f"{decision['score']}/10",
                    delta=decision['urgence'].upper(),
                    help="Risque - Protection"
                )

            # Recommandation claire
            st.markdown("---")
            st.subheader("➜ Recommandation")

            if decision['urgence'] == 'haute':
                st.error(f"""
                ### 🔴 {decision['action']}
                
                **Urgence élevée** - Action immédiate recommandée
                
                {decision.get('alerte_preventive', '')}
                """)
            elif decision['urgence'] == 'moyenne':
                st.warning(f"""
                ### 🟠 {decision['action']}
                
                **Surveillance nécessaire**
                
                {decision.get('alerte_preventive', '')}
                """)
            else:
                st.success(f"""
                ### 🟢 {decision['action']}
                
                **Situation sous contrôle**
                """)

            # Météo actuelle
            st.markdown("---")
            st.subheader("🌤️ Conditions Météorologiques")

            meteo = analyse['meteo_actuelle']
            col_w1, col_w2, col_w3 = st.columns(3)

            with col_w1:
                st.metric("Température",
                         f"{meteo.get('temp_moy', 0):.1f}°C",
                         delta=f"Min: {meteo.get('temp_min', 0):.1f}°C | Max: {meteo.get('temp_max', 0):.1f}°C")

            with col_w2:
                st.metric("Précipitations", f"{meteo.get('precipitation', 0):.1f} mm")

            with col_w3:
                st.metric("Humidité", f"{meteo.get('humidite', 0):.0f}%")

            # Prévisions
            if analyse['previsions_3j']:
                st.markdown("---")
                st.subheader("📅 Prévisions 3 Jours")

                prev = analyse['previsions_3j']
                st.info(f"💧 Pluie prévue : **{prev['pluie_totale']} mm**")

                if prev['details']:
                    cols_prev = st.columns(len(prev['details']))
                    for idx, (date, meteo_prev) in enumerate(prev['details'].items()):
                        with cols_prev[idx]:
                            st.caption(f"**{date}**")
                            st.caption(f"🌡️ {meteo_prev['temp_moy']:.1f}°C")
                            st.caption(f"💧 {meteo_prev['precipitation']:.1f}mm")

        # TAB 2 : Détails Techniques
        with tab2:
            st.subheader("🔬 Détails des Calculs")

            col_tech1, col_tech2 = st.columns(2)

            with col_tech1:
                st.markdown("### 🦠 Modèle Simple")
                st.markdown(f"""
                **Score calculé :** {risque['score']}/10
                
                **Facteurs pris en compte :**
                - Pluie 48h
                - Température (optimum 20-25°C)
                - Humidité relative
                - Coefficient stade : {coef_stade}
                - Sensibilité cépages
                
                **Résultat :** {risque['niveau']}
                """)

            with col_tech2:
                if utiliser_ipi and risque['ipi'] is not None:
                    st.markdown("### 📊 Modèle IPI")
                    st.markdown(f"""
                    **IPI calculé :** {risque['ipi']}/100
                    
                    **Méthode :**
                    - Interpolation bilinéaire
                    - Température vs Durée humectation
                    - Table Lalancette et al.
                    
                    **Niveau :** {risque.get('ipi_niveau', 'N/A')}
                    
                    💡 *L'IPI évalue la sévérité potentielle si infection, pas la probabilité d'infection*
                    """)

            st.markdown("---")

            # Protection détaillée
            st.markdown("### 🛡️ Analyse de la Protection")

            if protection['dernier_traitement']:
                dt = protection['dernier_traitement']
                carac = dt['caracteristiques']

                col_prot1, col_prot2 = st.columns(2)

                with col_prot1:
                    st.markdown(f"""
                    **Traitement actif :**
                    - Date : {dt['date']}
                    - Produit : {carac.get('nom', 'N/A')}
                    - Type : {carac.get('type', 'N/A')}
                    """)

                with col_prot2:
                    st.markdown(f"""
                    **Caractéristiques :**
                    - Persistance : {carac.get('persistance_jours', 0)} jours
                    - Seuil lessivage : {carac.get('lessivage_seuil_mm', 0)} mm
                    - Dose appliquée : {dt.get('dose_kg_ha', 'N/A')} kg/ha
                    """)

                # Facteur limitant en évidence
                facteur = protection.get('facteur_limitant', 'Inconnu')

                if 'Pousse' in facteur:
                    st.warning(f"⚠️ **Facteur limitant : {facteur}**\n\nLa croissance végétale dilue la protection. Renouvellement fréquent recommandé.")
                elif 'Lessivage' in facteur:
                    st.error(f"🌧️ **Facteur limitant : {facteur}**\n\nProtection lessivée. Traitement nécessaire.")
                else:
                    st.info(f"ℹ️ **Facteur limitant : {facteur}**")

            # Mode debug
            if mode_debug:
                st.markdown("---")
                st.subheader("🐛 Mode Debug")

                # Réexécuter avec debug
                with st.spinner("Recalcul avec traces debug..."):
                    # Capturer la sortie debug
                    import io
                    from contextlib import redirect_stdout

                    f = io.StringIO()
                    with redirect_stdout(f):
                        analyse_debug = systeme.analyser_parcelle(
                            parcelle_selectionnee,
                            utiliser_ipi=utiliser_ipi,
                            debug=True
                        )
                    debug_output = f.getvalue()

                    st.markdown('<div class="debug-box">', unsafe_allow_html=True)
                    st.code(debug_output, language="text")
                    st.markdown('</div>', unsafe_allow_html=True)

        # TAB 3 : Historique
        with tab3:
            st.subheader("📅 Historique des Traitements")

            # Filtrer traitements de cette parcelle
            traitements_parcelle = [
                t for t in systeme.traitements.historique.get('traitements', [])
                if t['parcelle'] == parcelle_selectionnee
            ]

            if traitements_parcelle:
                # Trier par date décroissante
                traitements_parcelle.sort(key=lambda x: x['date'], reverse=True)

                # Affichage tableau
                import pandas as pd

                df_data = []
                for t in traitements_parcelle:
                    df_data.append({
                        'Date': t['date'],
                        'Produit': t['caracteristiques'].get('nom', t['produit']),
                        'Type': t['caracteristiques'].get('type', 'N/A'),
                        'Dose (kg/ha)': t.get('dose_kg_ha', 'N/A'),
                        'Persistance (j)': t['caracteristiques'].get('persistance_jours', 0)
                    })

                df = pd.DataFrame(df_data)
                st.dataframe(df, use_container_width=True, hide_index=True)

                # Statistiques
                st.markdown("---")
                col_stat1, col_stat2, col_stat3 = st.columns(3)

                with col_stat1:
                    st.metric("Total traitements", len(traitements_parcelle))

                with col_stat2:
                    # Dernier traitement
                    dernier = traitements_parcelle[0]
                    jours_depuis = (datetime.now() - datetime.strptime(dernier['date'], '%Y-%m-%d')).days
                    st.metric("Dernier traitement", f"Il y a {jours_depuis}j")

                with col_stat3:
                    # Produit le plus utilisé
                    produits = [t['caracteristiques'].get('nom', 'N/A') for t in traitements_parcelle]
                    produit_freq = max(set(produits), key=produits.count)
                    st.metric("Produit principal", produit_freq)

            else:
                st.info("📝 Aucun traitement enregistré pour cette parcelle")
                st.markdown("Utilisez la page **Gestion Traitements** pour ajouter un traitement.")

except Exception as e:
    st.error(f"❌ Erreur : {str(e)}")
    import traceback
    with st.expander("Détails de l'erreur"):
        st.code(traceback.format_exc())