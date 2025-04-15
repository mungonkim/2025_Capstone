import pandas as pd
import numpy as np
import os
import pickle
import joblib
from text_preprocessor import clean_text, tokenize_and_remove_stopwords
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.sequence import pad_sequences
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import MinMaxScaler

# 사용자 입력 받기
def get_user_input():
    print("사용자 입력을 시작합니다.")
    title = input("작품명: ").strip()
    genre = input("장르 (로맨스, 로판, 무협, 미스터리, 판타지, 현판): ").strip()
    plot = input("줄거리: ").strip()
    print(f"\n 입력 완료: {title} | {genre} | {plot}\n")
    return title, genre, plot

# 수치 정제 함수
def parse_count(text):
    import re
    text = str(text).replace(",", "")
    text = re.sub(r"[가-힣\s]*", "", text)
    match = re.search(r"(\d+)(만)?", text)
    if not match:
        return 0
    number = int(match.group(1))
    return number * 10000 if match.group(2) == "만" else number

# 감정 비율 계산 함수
def compute_sentiment_ratios(comment_df, model, tokenizer, max_len):
    pos_ratio, neg_ratio = {}, {}
    for col in comment_df.columns:
        comments = comment_df[col].dropna().tolist()
        cleaned = [clean_text(c) for c in comments]
        tokenized = tokenize_and_remove_stopwords(pd.Series(cleaned))
        sequences = tokenizer.texts_to_sequences(tokenized)
        padded = pad_sequences(sequences, maxlen=max_len)

        if padded.shape[0] == 0:
            print(f"⚠️ '{col}' → 감정 예측 불가 (패딩 없음)")
            pos_ratio[col], neg_ratio[col] = np.nan, np.nan
            continue

        predictions = model.predict(padded)
        binary = [1 if p >= 0.5 else 0 for p in predictions]
        total = len(binary)
        pos = sum(binary)
        neg = total - pos
        pos_ratio[col] = round(pos / total, 5)
        neg_ratio[col] = round(neg / total, 5)
    return pos_ratio, neg_ratio

# 메인 실행 함수
def run_predictor():
    title, genre, plot = get_user_input()

    info_path = f"webnovel_data/{genre}_본문정보.csv"
    comment_path = f"webnovel_data/{genre}_댓글.csv"

    df = pd.read_csv(info_path)
    comment_df = pd.read_csv(comment_path)

    df["다운로드 수"] = df["다운로드 수"].apply(parse_count)
    df["관심 수"] = df["관심 수"].apply(parse_count)

    with open("models/tokenizer_config.pkl", "rb") as f:
        config = pickle.load(f)
    tokenizer = config["tokenizer"]
    max_len = config["max_len"]
    sentiment_model = load_model("models/sentiment_model.h5")

    pos_dict, neg_dict = compute_sentiment_ratios(comment_df, sentiment_model, tokenizer, max_len)
    df["긍정 비율"] = df["제목"].map(pos_dict)
    df["부정 비율"] = df["제목"].map(neg_dict)

    df = df.dropna(subset=["긍정 비율", "부정 비율", "별점"])
    if df.empty:
        print("유사 작품 데이터 부족. 예측 불가.")
        return

    # 가중 평균 기반 예측
    weights = {
        "다운로드 수": 0.1,
        "관심 수": 0.25,
        "긍정 비율": 0.35,
        "부정 비율": 0.2,
        "별점": 0.1
    }
    max_download = df["다운로드 수"].max()
    max_interest = df["관심 수"].max()

    avg_download = df["다운로드 수"].mean() / max_download
    avg_interest = df["관심 수"].mean() / max_interest
    avg_pos = df["긍정 비율"].mean()
    avg_neg = df["부정 비율"].mean()
    avg_rating = df["별점"].mean() / 10

    weighted_score = (
        avg_download * weights["다운로드 수"] +
        avg_interest * weights["관심 수"] +
        avg_pos * weights["긍정 비율"] +
        avg_neg * weights["부정 비율"] +
        avg_rating * weights["별점"]
    ) * 10

    #  ML 회귀 기반 예측
    X = df[["다운로드 수", "관심 수", "긍정 비율", "부정 비율", "별점"]]
    y = df["별점"]
    scaler = MinMaxScaler()
    X_scaled = scaler.fit_transform(X)
    model = RandomForestRegressor(random_state=42)
    model.fit(X_scaled, y)
    prediction = model.predict([X_scaled.mean(axis=0)])
    ml_score = float(prediction[0])

    # 하이브리드 예측 비율 설정
    num_samples = len(df)
    if num_samples < 10:
        alpha = 0.7
    elif num_samples < 20:
        alpha = 0.5
    else:
        alpha = 0.3

    hybrid_score = weighted_score * alpha + ml_score * (1 - alpha)

    print("\n[예측 결과]")
    print(f"- 긍정 비율 평균: {avg_pos:.2%}")
    print(f"- 부정 비율 평균: {avg_neg:.2%}")
    print(f"- 다운로드 수 정규화 평균: {avg_download:.4f}")
    print(f"- 관심 수 정규화 평균: {avg_interest:.4f}")
    print(f"- 별점 평균 (정규화): {avg_rating:.4f}")
    print(f" 혼합형 예측 평점: {round(hybrid_score, 2)}점")

if __name__ == "__main__":
    run_predictor()