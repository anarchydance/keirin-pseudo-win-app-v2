import streamlit as st
import re
import pandas as pd

st.set_page_config(page_title="競輪 擬似単勝オッズ計算アプリ", layout="centered")

st.title("競輪 擬似単勝オッズ計算アプリ")
st.caption("オッズ画面のテキストから、擬似単勝・人気順位・支持率を自動計算します！")

st.markdown("---")

# --- URLパラメーターの取得（ブックマークレット連携用） ---
query_params = st.query_params
default_text = query_params.get("odds_text", "")

st.subheader("📊 オッズテキスト")
pasted_text = st.text_area("オッズテキスト（ブックマークレットから自動入力されます）", value=default_text, height=160, placeholder="ここにコピーしたテキストを貼り付けてください...")

# --- 車番数の自動判定 & 手動選択 ---
all_odds_raw_temp = re.findall(r'(\d{1,5}\.\d+)', pasted_text) if pasted_text else []
data_count = len(all_odds_raw_temp)

# データ数に応じた推定車番
estimated_cars = 9
if data_count >= 450:
    estimated_cars = 9
elif data_count >= 280:
    estimated_cars = 8
elif data_count >= 150:
    estimated_cars = 7

col1, col2 = st.columns([2, 1])
with col1:
    mode_options = ["自動判定", 9, 8, 7]
    selected_mode = st.radio("車番数モード", mode_options, index=0, horizontal=True, help="自動判定はデータ数から自動推測します。必要に応じて手動で固定できます。")

if selected_mode == "自動判定":
    car_count_mode = estimated_cars
    st.info(f"💡 データ数（{data_count}件）から **{car_count_mode}車立て** として自動判定しました。")
else:
    car_count_mode = selected_mode

if not pasted_text.strip():
    st.info("💡 ブックマークレットを実行するか、テキストを貼り付けてください。")
    st.stop()

# --- 以降の計算ロジック ---
cars = list(range(1, car_count_mode + 1))

def get_combinations(first_car, all_cars):
    combs = []
    other_cars = [c for c in all_cars if c != first_car]
    for c2 in other_cars:
        for c3 in other_cars:
            if c2 != c3:
                combs.append((first_car, c2, c3))
    return combs

all_odds_raw = all_odds_raw_temp

records = []
odds_idx = 0

for first_car in cars:
    combs = get_combinations(first_car, cars)
    for c1, c2, c3 in combs:
        if odds_idx < len(all_odds_raw):
            try:
                odds_val = float(all_odds_raw[odds_idx])
                records.append({"first": c1, "second": c2, "third": c3, "odds": odds_val})
            except ValueError:
                pass
            odds_idx += 1

if not records:
    st.error("オッズデータを自動検出できませんでした。テキスト全体が正しくコピーされているか確認してください。")
    st.stop()

st.success(f"データ解析成功！ （検出データ: {len(records)} 組 / 設定: {car_count_mode}車立て）")

# --- 擬似単勝オッズ計算 ---
pseudo_odds_map = {}

for car in cars:
    car_records = [r for r in records if r["first"] == car]
    if not car_records:
        continue
    valid_odds = [r["odds"] for r in car_records if 0 < r["odds"] < 9998]
    if valid_odds:
        inv_sum = sum(1.0 / odds for odds in valid_odds)
        if inv_sum > 0:
            pseudo_odds_map[car] = round(1.0 / inv_sum, 1)

if not pseudo_odds_map:
    st.warning("計算できるデータがありませんでした。")
    st.stop()

# 人気順位・支持率の計算
sorted_cars = sorted(pseudo_odds_map.items(), key=lambda x: x[1])
rank_map = {car: idx for idx, (car, odds) in enumerate(sorted_cars, 1)}

inv_totals = {car: 1.0 / odds for car, odds in pseudo_odds_map.items()}
total_inv = sum(inv_totals.values())
support_rates = {car: (inv / total_inv) * 100 for car, inv in inv_totals.items()}

# --- 車立てごとの対象順位表示 ---
if car_count_mode == 9:
    target_ranks = [2, 5, 6, 7, 9]
    st.markdown("### 🎯 9車立て指定人気順位の車番（9点買い対象）")
else:
    target_ranks = [2, 5, 6, 7]
    st.markdown(f"### 🎯 {car_count_mode}車立て指定人気順位の車番（6点買い対象）")

rank_to_car = {rank: car for car, rank in rank_map.items()}

result_data = []
for r_target in target_ranks:
    car = rank_to_car.get(r_target)
    if car is not None:
        result_data.append({
            "人気順位": f"{r_target}番人気",
            "車番": f"{car}番車",
            "擬似単勝オッズ": f"{pseudo_odds_map[car]:.1f}倍",
            "支持率目安": f"{support_rates[car]:.1f}%"
        })
    else:
        result_data.append({
            "人気順位": f"{r_target}番人気",
            "車番": "該当なし",
            "擬似単勝オッズ": "---",
            "支持率目安": "---"
        })

df_target = pd.DataFrame(result_data)
st.table(df_target)

# --- 全車番一覧の表示 ---
st.markdown("### 📋 全車番の擬似単勝オッズ一覧")
full_data = []
for car, rank in sorted(rank_map.items(), key=lambda x: x[1]):
    full_data.append({
        "順位": f"{rank}位",
        "車番": f"{car}番車",
        "擬似単勝オッズ": f"{pseudo_odds_map[car]:.1f}倍",
        "支持率目安": f"{support_rates[car]:.1f}%"
    })

df_full = pd.DataFrame(full_data)
st.dataframe(df_full, use_container_width=True, hide_index=True)
