# ============================================================
# PROJET : Logistique intelligente MiR100 + QR codes USB
# Auteur : ---
# Description :
# - Lecture QR codes avec scannette USB
# - Priorisation des demandes (urgence, temps, distance)
# - Communication avec le MiR via API REST
# - Lancement de missions existantes dans l'interface MiR
# ============================================================

import math
import requests
import threading
import time
from datetime import datetime
import base64

# ============================================================
# CLASSE : Demande
# ============================================================

class Demande:
    def __init__(self, poste_id, piece, niveau_stock):
        self.poste_id = poste_id
        self.piece = piece
        self.niveau_stock = niveau_stock
        self.heure_demande = datetime.now()
        self.priorite = 0

# ============================================================
# CLASSE : Usine
# ============================================================

class Usine:
    def __init__(self, postes, stock_position):
        self.postes = postes
        self.stock_position = stock_position

    def distance(self, a, b):
        return math.dist(a, b)

# ============================================================
# CLASSE : OptimiseurPLNE
# ============================================================

class OptimiseurPLNE:
    def __init__(self, usine):
        self.usine = usine
        self.poids_stock = {"critique": 5, "faible": 3, "normal": 1}

    def calculer_priorite(self, demande, position_mir):
        urgence = self.poids_stock.get(demande.niveau_stock, 1)
        temps_attente = (datetime.now() - demande.heure_demande).seconds / 60
        distance = (
            self.usine.distance(position_mir, self.usine.stock_position)
            + self.usine.distance(self.usine.stock_position,
                                  self.usine.postes[demande.poste_id])
        )
        demande.priorite = 5 * urgence + 0 * temps_attente - 1 * distance
        return demande.priorite

    def trier_demandes(self, demandes, position_mir):
        for d in demandes:
            self.calculer_priorite(d, position_mir)
        return sorted(demandes, key=lambda d: d.priorite, reverse=True)

# ============================================================
# CLASSE : MiRAPI (version avec token base64)
# ============================================================

class MiRAPI:
    def __init__(self, ip, username, password):
        self.base_url = f"https://{ip}/api/v2.0.0"
        # Encode username:password en base64
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic YWRtaW46OGM2OTc2ZTViNTQxMDQxNWJkZTkwOGJkNGRlZTE1ZGZiMTY3YTljODczZmM0YmI4YTgxZjZmMmFiNDQ4YTkxOA==",
            "Accept-Language": "en_US",
            "Content-Type": "application/json"
        }
        requests.packages.urllib3.disable_warnings()

    def get_position(self):
        r = requests.get(f"{self.base_url}/status", headers=self.headers, verify=False)
        data = r.json()
        return data["position"]["x"], data["position"]["y"]

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

    def lancer_mission(self, mission_id, priority=0):
        """
        Lance une mission sur le MiR via l'API REST (version token base64)
        """
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

# ============================================================
# CLASSE : GestionnaireLogistique
# ============================================================

class GestionnaireLogistique:
    def __init__(self, usine, mir_api, missions):
        self.usine = usine
        self.mir = mir_api
        self.missions = missions  # dict: poste_id -> mission_id
        self.demandes = []
        self.optimiseur = OptimiseurPLNE(usine)

    # --- Réception d'une demande via QR code ---
    def recevoir_scan_qr(self, poste_id, piece, niveau_stock):
        print(f"[SCAN] Poste {poste_id} demande {piece} (niveau: {niveau_stock})")
        demande = Demande(poste_id, piece, niveau_stock)
        self.demandes.append(demande)

    # --- Cycle d'exécution du MiR ---
    def executer_cycle(self):
        if not self.demandes:
            return

        if not self.mir.est_pret():
            return

        position_mir = self.mir.get_position()
        demandes_triees = self.optimiseur.trier_demandes(self.demandes, position_mir)
        demande = demandes_triees[0]
        mission_id = self.missions[demande.poste_id]

        print(f"[ACTION] Lancement mission vers {demande.poste_id}")
        if self.mir.lancer_mission(mission_id):
            print("[OK] Mission lancée")
            self.demandes.remove(demande)
        else:
            print("[ERREUR] Échec lancement mission")

# ============================================================
# --- FONCTIONS POUR LE SCANNER USB ---
# ============================================================

def attendre_scan_qr():
    """Attente d'un scan USB"""
    data = input()  # bloquant, la scannette tape le QR
    return data.strip()

def parser_scan(data):
    """Parser le contenu du QR code"""
    try:
        poste_id, piece, niveau_stock = data.split("|")
        return poste_id, piece, niveau_stock
    except ValueError:
        print("[ERREUR] QR code invalide :", data)
        return None

def ecouter_scanner(gestion):
    print("[INFO] Scanner USB prêt")
    while True:
        data = attendre_scan_qr()
        resultat = parser_scan(data)
        if resultat:
            poste_id, piece, niveau_stock = resultat
            gestion.recevoir_scan_qr(poste_id, piece, niveau_stock)

# ============================================================
# PROGRAMME PRINCIPAL
# ============================================================

if __name__ == "__main__":
    # --- Géométrie usine ---
    usine = Usine(
        postes={
            "POSTE_1": (16.634, 8.019),
            "POSTE_2": (15.849, 7.703),
            "POSTE_3": (13.919, 7.527)
        },
        stock_position=(18.017, 4.537)
    )

    # --- Connexion MiR ---
    mir = MiRAPI(
        ip="192.168.12.20",
        username="admin",
        password="admin"
    )

    # --- Missions MiR (UUID depuis interface) ---
    missions = {
        "POSTE_1": "e32cb40a-db5e-11f0-a79a-0001297a2882",
        "POSTE_2": "14673050-db5f-11f0-a79a-0001297a2882",
        "POSTE_3": "27bec3bd-db5f-11f0-a79a-0001297a2882"
    }
    # --- Gestionnaire Logistique ---
    gestion = GestionnaireLogistique(usine, mir, missions)

    # --- Lancement du thread scanner ---
    threading.Thread(target=ecouter_scanner, args=(gestion,), daemon=True).start()

    # --- Boucle principale pour exécuter les missions ---
    while True:
        gestion.executer_cycle()
        time.sleep(2)  # évite spam API MiR

