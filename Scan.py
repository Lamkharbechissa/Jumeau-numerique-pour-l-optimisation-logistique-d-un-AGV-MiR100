import requests
import json
import base64
import hashlib

# --- Configuration MiR (Corrigée) ---
MIR_IP = "192.168.12.20" 
MIR_PORT = 8080 # <-- NOUVEAU : Utilisation du port 8080
API_VERSION = "v1" # <-- NOUVEAU : Cible l'API v1 (ou utilisez simplement /api/mission_queue)

USER = "admin"
PASSWORD = "admin"
MISSION_GUID = "5f61b35d-d4e1-11f0-8965-0001297a2882" 

# --- Authentification ---
# Le hashage SHA-256 peut ne pas être requis pour la v1.0. 
# Pour être sûr, nous allons d'abord essayer SANS le hash, car c'était la méthode v1.0 originale.
# Si ça échoue (401), nous reviendrons au hash.

auth_string = f"{USER}:{PASSWORD}" # Tentative sans hash pour la v1.0
auth_bytes = auth_string.encode('ascii')
base64_auth = "YWRtaW46OGM2OTc2ZTViNTQxMDQxNWJkZTkwOGJkNGRlZTE1ZGZiMTY3YTljODczZmM0YmI4YTgxZjZmMmFiNDQ4YTkxOA=="

# --- En-têtes HTTP ---
headers = {
    "Authorization": f"Basic {base64_auth}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# --- URL de l'API pour la file d'attente des missions (v1.0) ---
# En v1.0, le chemin est souvent /jobs, ou parfois /mission_queue, ou même juste /missions
url_queue = f"http://{MIR_IP}/api/v2.0.0/mission_queue" 
# NOTE: Le chemin "/api/v1/jobs" fonctionne mieux sur certaines v1.0. Nous allons l'essayer après.

# --- Corps de la requête POST pour mettre en file d'attente une mission ---
payload = {
    "mission_id": MISSION_GUID,
    "priority": 0 
}

print(f"Tentative finale: POST sur {url_queue} avec port 8080 (API v1.x)...")

try:
    # Envoi de la requête POST
    response = requests.post(url_queue, headers=headers, data=json.dumps(payload))
    
    # Le statut attendu pour l'ajout est généralement 201 (Created)
    if response.status_code == 201:
        print("🎉 ✅ MISSION LANCÉE AVEC SUCCÈS ! Code 201 Created (API v1.x).")
        print("Réponse du MiR:", response.json())
    elif response.status_code == 405:
        # Si vous obtenez 405 ici, essayez de changer l'URL pour:
        # url_queue = f"http://{MIR_IP}:{MIR_PORT}/api/{API_VERSION}/jobs"
        print(f"❌ Échec de l'ajout (405). Tentez de changer l'endpoint pour /api/{API_VERSION}/jobs.")
    elif response.status_code == 401:
        print("❌ Échec 401 : Authentification. Tentez d'utiliser le hachage SHA-256 (méthode de la v2.0).")
    else:
        print(f"❌ Erreur lors de l'ajout de la mission. Code de statut: {response.status_code}")
        print("Réponse du MiR:", response.text)

except requests.exceptions.RequestException as e:
    print(f"Une erreur de connexion est survenue: {e}")