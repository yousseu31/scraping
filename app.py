from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import psycopg2
from datetime import datetime, date
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# CONFIGURATION DE LA BASE DE DONNÉES
DB_NAME = 'beac'
DB_USER = 'legane'
DB_PASSWORD = 'legane19'
DB_HOST = 'localhost'
DB_PORT = 5432

#  CONFIGURATION DE L'ENVOI D'EMAIL
SEND_EMAIL = "yousseucabrel@gmail.com"
PWD = "wybcgmbzcsnthmcu"
RECEIVE_EMAIL = "cabrelyousseu6@gmail.com"

# Création de l'application FastAPI
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

class Taux(BaseModel):
    paire: str
    achat: float
    vente: float

class TauxResponse(BaseModel):
    date_valeur: str
    taux: list[Taux]

def recuperer_taux():
    # Connexion à la base PostgreSQL
    conn = psycopg2.connect(
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT
    )
    cur = conn.cursor()

    url = "https://www.beac.int/"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    date_div = soup.find('div', class_='date_source_taux')
    date_valeur = None
    if date_div:
        match = re.search(r'Date de valeur : (\d{2}/\d{2}/\d{4})', date_div.text)
        if match:
            date_valeur = datetime.strptime(match.group(1), '%d/%m/%Y').date()

    # Modification : date du jour si date_valeur est None
    if date_valeur is None:
        date_valeur = date.today()

    documents = soup.find_all('div', class_='document')

    resultats = []
    for doc in documents:
        taux_div = doc.find('div', class_='taux_de_change')
        if taux_div:
            paire = taux_div.find('span', class_='code_valeur')
            achat = taux_div.find('div', id='middle')
            vente = taux_div.find('div', id='right')

            if paire and achat and vente:
                paire_text = paire.text.strip()
                achat_val = achat.text.strip().replace(',', '.')
                vente_val = vente.text.strip().replace(',', '.')

                try:
                    achat_float = float(achat_val)
                    vente_float = float(vente_val)
                except ValueError:
                    continue

                cur.execute("""
                    INSERT INTO taux_change (paire_devises, achat, vente, date_valeur)
                    VALUES (%s, %s, %s, %s)
                """, (paire_text, achat_float, vente_float, date_valeur))

                resultats.append((paire_text, achat_float, vente_float))

    conn.commit()
    cur.close()
    conn.close()

    return date_valeur, resultats

def envoyer_email(date_valeur, taux_list):
    subject = f"Taux BEAC du {date_valeur}"
    body = f"Voici les taux relevés le {date_valeur} :\n\n"
    for paire, achat, vente in taux_list:
        body += f"{paire} | Achat: {achat} | Vente: {vente}\n"

    message = MIMEMultipart()
    message['Subject'] = subject
    message['From'] = SEND_EMAIL
    message['To'] = RECEIVE_EMAIL
    message.attach(MIMEText(body, "plain"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(SEND_EMAIL, PWD)
        server.send_message(message)

@app.get("/scrape", response_model=TauxResponse)
def scrape():
    try:
        date_valeur, data = recuperer_taux()
        return {"date_valeur": str(date_valeur),
                "taux": [{"paire": t[0], "achat": t[1], "vente": t[2]} for t in data]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/scrape_and_send")
def scrape_and_send():
    try:
        date_valeur, data = recuperer_taux()
        envoyer_email(date_valeur, data)
        return {"message": f"Taux récupérés et e-mail envoyé pour la date {date_valeur}."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Pour déclenchement en ligne de commande (cron)
if __name__ == "__main__":
    date_valeur, taux = recuperer_taux()
    envoyer_email(date_valeur, taux)
