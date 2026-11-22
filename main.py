import requests

url = "https://api.kraken.com/0/public/Ticker"

cryptos = [
    "XBTEUR",
    "ETHEUR",
    "SOLEUR",
    "XRPEUR",
    "ADAEUR"
]

response = requests.get(
    url,
    params={"pair": ",".join(cryptos)},
    timeout=20
)

data = response.json()

if data["error"]:
    print("Erreur Kraken :", data["error"])
else:
    for pair, values in data["result"].items():
        print(pair, ":", values["c"][0], "EUR")
