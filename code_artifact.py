import streamlit as st
import re
import pandas as pd
import itertools

st.set_page_config(page_title="競輪 擬似単勝オッズ計算アプリ", layout="centered")

st.title("競輪 擬似単勝オッズ計算アプリ")
st.caption("オッズ画面のテキストから、擬似単勝・人気順位・支持率を自動計算します！")

st.markdown("---")

# --- URLパラメーターの取得（ブックマークレット連携用） ---
query_params = st.query_params
default_text = query_params.get("odds_text", "")

st.subheader("📊 オッズテキスト")
pasted_text = st.text_area("オッズテキスト（ブックマークレットから自動入力されます）", value=default_text, height=160, placeholder="ここにコピーしたテキストを貼り付けてください...")

if not pasted_text.strip():
    st.info("💡 ブックマークレットを実行するか、テキストを貼り付けてください。")
    st.stop()

# --- テキストの正規化（スペースや特殊文字のゆれを吸収） ---
normalized_text = pasted_text.replace('\xa0', ' ')

# --- 車番数モードの判定 ---
all_odds_raw_temp = re.findall(r'(\d{1,5}\.\d+)', normalized_text)
raw_count = len(all_odds_raw_temp)

estimated_cars = 9
if raw_count >= 450:
    estimated_cars = 9
elif raw_count >= 280:
    estimated_cars = 8
elif raw_count >= 150:
    estimated_cars = 7

col1, col2 = st.columns([2, 1])
with col1:
    mode_options = ["自動判定", 9, 8, 7]
    selected_mode = st.radio("車番数モード", mode_options, index=0, horizontal=True)

if selected_mode == "自動判定":
    car_count_mode = estimated_cars
    st.info(f"💡 検出データから **{car_count_mode}車立て** として判定しました。")
else:
    car_count_mode = selected_mode

# 1車あたりに必要なオッズ数（7車:30個, 8車:42個, 9車:56個）
per_car_target = (car_count_mode - 1) * (car_count_mode - 2)

# --- 【プロ仕様】re.finditerによる完全正確なブロック位置の走査 ---
# テキスト内にあるすべての「〇番車 全選択」の位置を順番にすべて検出する
matches = list(re.finditer(r'(\d{1,2})\s*番\s*車\s*全\s*選\s*択', normalized_text))

records = []
found_blocks = 0

if matches:
    for idx, match in enumerate(matches):
        car_num = int(match.group(1))
        if car_num > car_count_mode:
            continue
            
        start_pos = match.end()
        
        # 次の車番ブロックの開始位置、または最後の車番なら「発売票数」の位置を終了位置とする
        if idx + 1 < len(matches):
            end_pos = matches[idx + 1].start()
        else:
            vote_match = re.search(r'発\s*売\s*票\s*数', normalized_text[start_pos:])
            if vote_match:
                end_pos = start_pos + vote_match.start()
            else:
                end_pos = len(normalized_text)
                
        # その車番専用のテキストブロックを切り出し
        block_text = normalized_text[start_pos:end_pos]
        
        # ブロック内のすべての小数点付きオッズを抽出
        block_odds = re.findall(r'(\d{1,5}\.\d+)', block_text)
        
        # 必要な個数（例: 7車なら正確に30個）だけを取得
        valid_odds = block_odds[:per_car_target]
        
        for odds_str in valid_odds:
            try:
                val = float(odds_str)
                if 0 < val < 9998:
                    records.append({"first": car_num, "odds": val})
            except ValueError:
                pass
        found_blocks += 1

# 安全装置：もし何らかの理由でブロックが見つからなかった場合のエラー表示
if found_blocks == 0 or len(records) == 0:
    st.error("❌ オッズテキストの構造を認識できませんでした。テキストが正しくコピーされているか確認してください。")
    st.stop()

cars = list(range(1, car_count_mode + 1))
st.success(f"データ解析成功！ （検出車番ブロック数: {found_blocks} / 有効オッズ総数: {len(records)} 組 / 設定: {car_count_mode}車立て）")

# --- 擬似単勝オッズ計算 ---
pseudo_odds_map = {}

for car in cars:
    car_records = [r for r in records if r["first"] == car]
    valid_odds = [r["odds"] for r in car_records]
    
    if valid_odds:
        inv_sum = sum(1.0 / odds for odds in valid_odds)
        if inv_sum > 0:
            pseudo_odds_map[car] = round(1.0 / inv_sum, 1)

if not pseudo_odds_map:
    st.warning("計算できるデータがありませんでした。")
    st.stop()

# --- 人気順位・支持率の計算（同率対応） ---
sorted_cars = sorted(pseudo_odds_map.items(), key=lambda x: x[1])

odds_freq = {}
for _, odds in sorted_cars:
    odds_freq[odds] = odds_freq.get(odds, 0) + 1

rank_map = {}
display_rank_map = {}
rank_to_cars = {}

for i, (car, odds) in enumerate(sorted_cars):
    if i > 0 and odds == sorted_cars[i-1][1]:
        rank_map[car] = rank_map[sorted_cars[i-1][0]]
    else:
        rank_map[car] = i + 1
        
    actual_rank = rank_map[car]
    if actual_rank not in rank_to_cars:
        rank_to_cars[actual_rank] = []
    rank_to_cars[actual_rank].append(car)
    
    if odds_freq[odds] > 1:
        display_rank_map[car] = f"{actual_rank}位（同率）"
    else:
        display_rank_map[car] = f"{actual_rank}位"

inv_totals = {car: 1.0 / odds for car, odds in pseudo_odds_map.items()}
total_inv = sum(inv_totals.values())
support_rates = {car: (inv / total_inv) * 100 for car, inv in inv_totals.items()}

# --- 車立てごとの対象順位・除外ルール設定 ---
if car_count_mode == 9:
    target_ranks = [1, 3, 4, 5]
    exclude_pair = {3, 5}
    st.markdown("### 🎯 9車立て 買い目構成（1, 3, 4, 5番人気 / 5点買い）")
else:
    target_ranks = [1, 2, 3, 4]
    exclude_pair = {2, 4}
    st.markdown(f"### 🎯 {car_count_mode}車立て 買い目構成（1, 2, 3, 4番人気 / 5点買い）")

# ピックアップ車番一覧の表示
target_data = []
for r_target in target_ranks:
    cars_at_rank = rank_to_cars.get(r_target, [])
    if cars_at_rank:
        for car in cars_at_rank:
            target_data.append({
                "人気順位": f"{r_target}番人気",
                "順位表示": display_rank_map[car],
                "車番": f"{car}番車",
                "擬似単勝オッズ": f"{pseudo_odds_map[car]:.1f}倍",
                "支持率目安": f"{support_rates[car]:.1f}%"
            })
    else:
        target_data.append({
            "人気順位": f"{r_target}番人気",
            "順位表示": "---",
            "車番": "該当なし",
            "擬似単勝オッズ": "---",
            "支持率目安": "---"
        })

st.markdown("#### 📋 ピックアップ車番一覧")
st.table(pd.DataFrame(target_data))

# --- ワイド買い目 ---
target_cars_map = {r: rank_to_cars.get(r, [None])[0] for r in target_ranks}

if None in target_cars_map.values():
    st.warning("指定された人気順位に対応する車番を特定できませんでした。")
else:
    all_pairs = list(itertools.combinations(target_ranks, 2))
    purchase_bets = []
    excluded_bets = []
    
    for r1, r2 in all_pairs:
        c1 = target_cars_map[r1]
        c2 = target_cars_map[r2]
        pair_cars = tuple(sorted([c1, c2]))
        
        bet_info = {
            "組み合わせ": f"{r1}番人気 ＆ {r2}番人気",
            "車番ペア": f"{pair_cars[0]}番車 － {pair_cars[1]}番車"
        }
        
        if set([r1, r2]) == exclude_pair:
            excluded_bets.append(bet_info)
        else:
            purchase_bets.append(bet_info)

    st.markdown("#### 🚫 除外する買い目")
    if excluded_bets:
        st.table(pd.DataFrame(excluded_bets))
    else:
        st.info("除外対象の買い目はありません。")

    st.markdown("#### ✅ 実際に購入する買い目（計5点）")
    if purchase_bets:
        st.table(pd.DataFrame(purchase_bets))
    else:
        st.info("購入対象の買い目がありません。")

# --- 全車番一覧の表示 ---
st.markdown("### 📋 全車番の擬似単勝オッズ一覧")
full_data = []
for car, rank in sorted(rank_map.items(), key=lambda x: (x[1], pseudo_odds_map[x[0]])):
    full_data.append({
        "順位": display_rank_map[car],
        "車番": f"{car}番車",
        "擬似単勝オッズ": f"{pseudo_odds_map[car]:.1f}倍",
        "支持率目安": f"{support_rates[car]:.1f}%"
    })

st.dataframe(pd.DataFrame(full_data), use_container_width=True, hide_index=True)
