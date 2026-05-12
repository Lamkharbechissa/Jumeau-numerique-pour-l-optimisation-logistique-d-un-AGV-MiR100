# 🤖 Jumeau Numérique pour l'optimisation logistique d'un AGV MiR100
### Projet PJT — Arts et Métiers, Aix-en-Provence · 2025–2026

> Conception et mise en œuvre d'un jumeau numérique d'un robot mobile autonome (AGV) de type MiR100, destiné à assurer l'approvisionnement logistique de postes de production au sein d'une usine pédagogique. Le système optimise les déplacements de l'AGV en tenant compte des priorités opérationnelles de chaque poste, afin de réduire les temps de trajet et d'améliorer l'efficacité globale du système de production.

---

## 📖 Introduction

Dans le cadre du projet PJT, notre travail a porté sur la conception d'un jumeau numérique d'un AGV MiR100. Le jumeau numérique développé reproduit le comportement décisionnel du robot réel, en intégrant des informations issues du terrain (demandes des postes, position du robot, état du système) et en prenant des décisions optimisées concernant l'ordre d'exécution des missions.

---

## 🏭 Contexte industriel

L'usine considérée est une **usine pédagogique** composée de quatre postes de production (`POSTE_1`, `POSTE_2`, `POSTE_3`, `POSTE_4`) sur lesquels sont réalisées différentes opérations de fabrication, ainsi qu'un **poste de stockage central** à partir duquel les pièces sont récupérées et acheminées vers les postes.

L'**AGV MiR100** assure la logistique interne entre le stock et les postes de production. Chaque poste peut générer une demande d'approvisionnement en fonction de son niveau de stock et de l'urgence de l'opération en cours.

---

## 🎯 Objectifs du projet

- Concevoir un jumeau numérique représentant fidèlement le comportement logistique de l'AGV MiR100
- Mettre en place un système de **priorisation des demandes** basé sur l'urgence (niveau de stock) et la distance à parcourir
- **Optimiser les déplacements** de l'AGV en minimisant les trajets inutiles pour réduire les temps de cycle
- Assurer une **communication fiable et sécurisée** entre le jumeau numérique et le robot réel via l'API REST MiR
- **Automatiser le déclenchement** des missions logistiques via scan de codes-barres

---

## 🏗️ Architecture globale de la solution

La solution repose sur une **architecture logicielle Python modulaire** comprenant :

- Un module de **gestion des demandes** provenant des postes de production
- Un module de **modélisation de l'usine** (positions des postes et du stock)
- Un module de **calcul des priorités et d'optimisation** des missions
- Un module de **communication avec le robot MiR100** via son API REST
- Un module d'**interaction opérateur** via lecture de codes-barres (scannette USB)

L'ensemble constitue le jumeau numérique, agissant comme un **système décisionnel central** connecté au robot réel.

---

## 📡 Communication avec le robot MiR100

La communication est réalisée via la bibliothèque Python `requests`, envoyant des requêtes HTTP vers l'API REST du robot. L'authentification est assurée par **Basic Authentication** (identifiant et mot de passe encodés en base64).

```python
class MiRAPI:
    def __init__(self, ip, username, password):
        self.base_url = f"https://{ip}/api/v2.0.0"

        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {token}",
            "Accept-Language": "en_US",
            "Content-Type": "application/json"
        }
        requests.packages.urllib3.disable_warnings()
```

### Fonctions principales

**`get_position`** — Interroge l'API pour connaître la position exacte du robot (x, y), renvoyée à l'algorithme de priorisation.

```python
def get_position(self):
    r = requests.get(f"{self.base_url}/status", headers=self.headers, verify=False)
    data = r.json()
    return data["position"]["x"], data["position"]["y"]
```

**`est_pret`** — Vérifie que le robot est en mode "Ready". Si le robot est en arrêt d'urgence ou en erreur, le système attend avant d'envoyer un ordre.

```python
def est_pret(self):
    try:
        r = requests.get(
            f"{self.base_url}/status",
            headers=self.headers,
            verify=False,
            timeout=3
        )
        return r.json()["state_text"] == "Ready"
    except requests.exceptions.RequestException:
        print("[MIR] Robot momentanément inaccessible")
        return False
```

**`lancer_mission`** — Envoie une requête `POST` à `/mission_queue` avec l'identifiant unique (GUID) de la mission créée sur l'interface MiR.

```python
def lancer_mission(self, mission_id, priority=0):
    """Lance une mission sur le MiR via l'API REST (version token base64)"""
    url = f"{self.base_url}/mission_queue"
    try:
        response = requests.post(
            url,
            headers=self.headers,
            json={"mission_id": mission_id, "priority": priority},
            verify=False,
            timeout=5
        )
        print(f"[MIR] Status: {response.status_code}, Response: {response.text}")
        return response.status_code in [200, 201]
    except requests.exceptions.RequestException as e:
        print("[MIR] Erreur lors de l'exécution de la mission:", e)
        return False
```

### Configuration des missions sur l'interface MiR

Les missions sont créées depuis le menu **Setup → Missions**. Chaque mission peut contenir un algorithme d'actions séquentielles. Les principales instructions utilisées sont :

- **`Move to`** — Déplace l'AGV vers une position prédéfinie sur la carte (tolérance de position : 0,1 m)
- **`Run UR program`** — Exécute un programme préalablement créé sur l'interface du bras robotique

---

## 🔄 Gestion des demandes et interaction opérateur

### Modélisation de la donnée

Lorsqu'un opérateur scanne un QR code, un objet `Demande` est créé qui fige l'instant précis de la demande (`heure_demande`), permettant au système de calculer le temps d'attente de chaque poste.

```python
class Demande:
    def __init__(self, poste_id, piece, niveau_stock):
        self.poste_id      = poste_id
        self.piece         = piece
        self.niveau_stock  = niveau_stock
        self.heure_demande = datetime.now()
        self.priorite      = 0
```

### Gestionnaire central

Le gestionnaire est le chef d'orchestre qui fait le lien entre les scans et le robot.

**`recevoir_scan_qr`** — Enregistre une nouvelle demande dans la file d'attente dès qu'un scan est détecté.

```python
def recevoir_scan_qr(self, poste_id, piece, niveau_stock):
    print(f"[SCAN] Poste {poste_id} demande {piece} (niveau: {niveau_stock})")
    demande = Demande(poste_id, piece, niveau_stock)
    self.demandes.append(demande)
```

**`executer_cycle`** — Boucle principale : vérifie les demandes, contrôle la disponibilité du robot, sélectionne la mission optimale via l'algorithme, et l'ordonne au MiR.

```python
def executer_cycle(self):
    if not self.demandes:
        return

    if not self.mir.est_pret():
        return

    position_mir     = self.mir.get_position()
    demandes_triees  = self.optimiseur.trier_demandes(self.demandes, position_mir)
    demande          = demandes_triees[0]
    mission_id       = self.missions[demande.poste_id]

    print(f"[ACTION] Lancement mission vers {demande.poste_id}")
    if self.mir.lancer_mission(mission_id):
        print("[OK] Mission lancée")
        self.demandes.remove(demande)
    else:
        print("[ERREUR] Échec lancement mission")
```

### Interaction physique via scannette USB

Chaque poste de production dispose d'un opérateur pouvant déclencher une demande logistique via scannette USB. Le scan d'un QR code transmet automatiquement l'identifiant du poste, le type de pièce demandée et le niveau de stock associé.

Format du QR code : `POSTE_1|PIGNON|CRITIQUE`

**`attendre_scan_qr`** — La scannette USB se comportant comme un clavier, cette fonction attend que le QR code soit « tapé » par le scanner.

```python
def attendre_scan_qr():
    """Attente d'un scan USB"""
    data = input()  # bloquant, la scannette tape le QR
    return data.strip()
```

**`parser_scan`** — Découpe la chaîne brute pour que le système puisse traiter chaque information séparément.

```python
def parser_scan(data):
    """Parser le contenu du QR code"""
    try:
        poste_id, piece, niveau_stock = data.split("|")
        return poste_id, piece, niveau_stock
    except ValueError:
        print("[ERREUR] QR code invalide :", data)
        return None
```

**`ecouter_scanner`** — Tourne dans un **Thread** (processus parallèle), permettant au programme de continuer à piloter le robot tout en restant à l'écoute d'un nouveau scan à n'importe quel moment.

```python
def ecouter_scanner(gestion):
    print("[INFO] Scanner USB prêt")
    while True:
        data    = attendre_scan_qr()
        resultat = parser_scan(data)
        if resultat:
            poste_id, piece, niveau_stock = resultat
            gestion.recevoir_scan_qr(poste_id, piece, niveau_stock)
```

---

## 🧠 Modélisation de la priorité des missions

Pour chaque demande logistique, une **priorité multi-objectifs** est calculée à partir de trois critères complémentaires :

$$Priority_i = \omega_u U_{i,norm} + \omega_a A_{i,norm} - \omega_d D_{i,norm}$$

$$\text{avec} \quad \omega_u + \omega_a + \omega_d = 1$$

| Critère | Description | Effet sur le score |
|---|---|---|
| **Urgence** (U) | Niveau de stock du poste demandeur | Plus le stock est bas → score monte |
| **Attente** (A) | Temps écoulé depuis l'émission de la demande | Plus l'attente est longue → score monte |
| **Distance** (D) | Trajet AGV → stock → poste de production | Plus le poste est loin → score baisse |

### Modes de fonctionnement

| Mode | ωu | ωa | ωd | Description |
|---|---|---|---|---|
| **Flux tendu** | 0,7 | 0,2 | 0,1 | Priorité maximale à l'urgence |
| **Économie d'énergie** | 0,2 | 0,2 | 0,6 | Minimise les déplacements |
| **Anti-blocage** | 0,3 | 0,5 | 0,2 | Évite la congestion par anticipation |

### Implémentation

```python
class Algo_Optim:
    def __init__(self, usine):
        self.usine       = usine
        self.poids_stock = {"critique": 3, "faible": 2, "normal": 1}

    def calculer_priorite(self, demande, position_mir):
        urgence       = self.poids_stock.get(demande.niveau_stock, 1)
        temps_attente = (datetime.now() - demande.heure_demande).seconds / 60
        distance      = (
            self.usine.distance(position_mir, self.usine.stock_position)
            + self.usine.distance(self.usine.stock_position,
                                  self.usine.postes[demande.poste_id])
        )
        demande.priorite = 0.3 * urgence + 0.2 * temps_attente - 0.5 * distance
        return demande.priorite

    def trier_demandes(self, demandes, position_mir):
        for d in demandes:
            self.calculer_priorite(d, position_mir)
        return sorted(demandes, key=lambda d: d.priorite, reverse=True)
```

---

## ⚙️ Exécution des missions et interaction avec le cobot

Une fois une mission sélectionnée et lancée par l'algorithme, le cycle complet s'exécute comme suit :

1. L'AGV MiR100 se déplace automatiquement vers le **poste de stockage**
2. Le **bras cobot** exécute un programme `pick` pour saisir la pièce demandée
3. L'AGV se déplace vers le **poste de production** concerné
4. Le cobot exécute un programme `place` pour déposer la pièce à l'emplacement prévu

Les programmes de pick and place ont été programmés en amont par l'équipe et sont intégrés au cycle global de fonctionnement du système logistique.

---

## 📊 Résultats et apports du projet

- ✅ Mise en œuvre d'un **jumeau numérique fonctionnel** directement connecté à un robot industriel réel
- ✅ Démonstration de l'intérêt d'une **priorisation dynamique des missions** en contexte logistique industriel
- ✅ Utilisation concrète d'une **API REST industrielle** pour le pilotage d'un AGV
- ✅ Intégration de notions clés : robotique mobile, optimisation des déplacements, programmation Python, systèmes cyber-physiques

---

## 🔭 Limites et perspectives d'amélioration

**Limites identifiées :**
- La fonction de calcul de priorité repose sur une pondération relativement simple, ne couvrant pas l'ensemble des contraintes d'un environnement industriel réel
- L'optimisation globale des trajets de type VRP (Vehicle Routing Problem) avancé n'a pas été implémentée
- Absence de visualisation graphique du jumeau numérique

**Perspectives d'amélioration :**
- [ ] Intégration d'algorithmes d'optimisation plus avancés (VRP, algorithmes génétiques…)
- [ ] Prise en compte de contraintes supplémentaires (temps de cycle, congestion des zones)
- [ ] Développement d'une **interface homme-machine** pour la supervision en temps réel
- [ ] Visualisation graphique du jumeau numérique et de l'état des postes



## Conclusion

Ce projet PJT a permis de concevoir un système complet de logistique intelligente basé sur un jumeau numérique d'AGV. Il illustre concrètement l'apport des outils numériques et de l'automatisation dans l'optimisation des flux industriels, tout en offrant une base solide pour des développements futurs plus avancés.
