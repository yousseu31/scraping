import requests

url = "https://www.beac.int/"

response = requests.get(url)
print(f"Status code: {response.status_code}")
print(response.text[:500])  # affiche les 500 premiers caractères du code HTML
