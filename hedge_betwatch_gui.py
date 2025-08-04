import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re

BOOKIES = ["TAB", "Unibet", "Neds", "Ladbrokes", "Sportsbet"]
BETWATCH_URL = "https://www.betwatch.com/next-to-jump"

st.title("🐎 Betwatch Hedge Builder – AU Racing")
st.write("Build a hedged matched bet from the next-to-jump races using real odds from Betwatch")

with st.sidebar:
    st.header("Multi Setup")
    stake = st.number_input("Total Stake ($)", 10, 1000, 50)
    promo_type = st.selectbox("Promo Type", ["Bet Return (1 leg fails)", "Bonus Bet Conversion"])
    if promo_type == "Bonus Bet Conversion":
        bonus_odds = st.number_input("Bonus Bet Odds (e.g. 5.0)", min_value=1.01, value=5.0, step=0.1)

def fetch_next_races():
    response = requests.get(BETWATCH_URL, timeout=10)
    soup = BeautifulSoup(response.text, "html.parser")
    race_blocks = soup.select(".card")[:3]
    races = []
    for race in race_blocks:
        title = race.select_one(".card-title").text.strip()
        rows = race.select(".runner")
        runners = []
        for r in rows:
            name = r.select_one(".runner-name").text.strip()
            odds_cells = r.select(".odds")
            odds = {}
            for cell in odds_cells:
                bookie = cell.get("data-bookie")
                price = cell.text.strip()
                if bookie and re.match(r"[0-9.]+", price):
                    odds[bookie] = float(price)
            runners.append({"name": name, "odds": odds})
        races.append({"title": title, "runners": runners})
    return races

races = fetch_next_races()
st.subheader("Next 3 Races from Betwatch")
legs = []
for i, race in enumerate(races):
    st.markdown(f"### Race {i+1}: {race['title']}")
    runner_names = [r["name"] for r in race["runners"]]
    chosen_runner = st.selectbox(f"Select runner for multi leg {i+1}", runner_names, key=f"leg{i+1}")
    back_odds = 0.0
    hedge_odds = {}
    for r in race["runners"]:
        if r["name"] == chosen_runner:
            back_odds = max(r["odds"].values()) if r["odds"] else 2.0
        else:
            for b in BOOKIES:
                if b in r["odds"]:
                    hedge_odds.setdefault(b, []).append((r["name"], r["odds"][b]))
    legs.append({"race": race["title"], "selection": chosen_runner, "back_odds": back_odds, "hedge_odds": hedge_odds})

def calc_dutch(hedge_list, hedge_total):
    odds_map = {}
    for bookie, entries in hedge_list.items():
        for name, odd in entries:
            key = f"{name} ({bookie})"
            odds_map[key] = odd
    inv_sum = sum(1/o for o in odds_map.values())
    stakes = {k: round((1/o)/inv_sum * hedge_total, 2) for k, o in odds_map.items()}
    return stakes

if st.button("🔁 Build Hedge Plan"):
    total_odds = 1
    for leg in legs:
        total_odds *= leg["back_odds"]

    st.markdown(f"## Combined Multi Odds: `{round(total_odds, 2)}`")

    for i, leg in enumerate(legs):
        st.markdown(f"### Leg {i+1}: {leg['selection']} in {leg['race']}")
        st.write(f"Back Odds: {leg['back_odds']}")
        stake_split = calc_dutch(leg['hedge_odds'], stake / 3)
        df = pd.DataFrame(list(stake_split.items()), columns=["Hedge Option", "Stake ($)"])
        st.table(df)

    if promo_type == "Bet Return (1 leg fails)":
        st.info("If 1 leg fails, you'll get your $50 back in bonus bet. Use that in high odds and hedge for 70% cash return (~$35).")
    else:
        st.success("Bonus Bet Conversion Calculator Below:")
        hedge_return = stake * 0.7 if bonus_odds >= 4 else stake * 0.65
        st.write(f"🎯 Estimated return from bonus bet at {bonus_odds} odds: **${round(hedge_return, 2)}**")
