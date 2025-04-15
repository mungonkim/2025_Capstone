import pandas as pd
import numpy as np
import pickle
import urllib.request
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Embedding, LSTM, Dense, Dropout, Bidirectional, BatchNormalization
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.optimizers import Adam
from tensorflow.keras.callbacks import EarlyStopping
from sklearn.metrics import classification_report
from konlpy.tag import Okt

# 1. 데이터 로딩
urllib.request.urlretrieve("https://raw.githubusercontent.com/e9t/nsmc/master/ratings_train.txt", "ratings_train.txt")
urllib.request.urlretrieve("https://raw.githubusercontent.com/e9t/nsmc/master/ratings_test.txt", "ratings_test.txt")

train_data = pd.read_table("ratings_train.txt")
test_data = pd.read_table("ratings_test.txt")

#  2. 간단한 전처리 함수
def preprocess(df):
    df = df.dropna(how='any')  # 결측치 제거
    df = df[df['document'].str.strip() != '']  # 공백 제거
    return df

train_data = preprocess(train_data)
test_data = preprocess(test_data)

#  3. 형태소 분석 + 불용어 제거
okt = Okt()
stopwords = set(['의', '가', '이', '은', '들', '는', '좀', '잘', '걍', '과', '도',
                 '를', '으로', '자', '에', '와', '한', '하다', '고', '에서', '까지'])

def tokenize_and_remove_stopwords(text_series):
    tokenized_sentences = []
    for sentence in text_series:
        try:
            tokens = okt.morphs(str(sentence), stem=True)
            clean_tokens = [word for word in tokens if word not in stopwords and len(word) > 1]
            tokenized_sentences.append(clean_tokens)
        except Exception:
            tokenized_sentences.append([])
    return tokenized_sentences

X_train = tokenize_and_remove_stopwords(train_data['document'])
X_test = tokenize_and_remove_stopwords(test_data['document'])

#  4. 라벨 정리 + 빈 샘플 제거
X_y_pair = [(x, y) for x, y in zip(X_train, train_data['label']) if len(x) > 0]
X_train, y_train = zip(*X_y_pair)

#  5. Tokenizer + Padding
tokenizer = Tokenizer(oov_token="<OOV>")
tokenizer.fit_on_texts(X_train)
X_train_seq = tokenizer.texts_to_sequences(X_train)

lengths = [len(x) for x in X_train_seq]
max_len = int(np.percentile(lengths, 95))
X_train_pad = pad_sequences(X_train_seq, maxlen=max_len)
y_train = np.array(y_train)

#  6. 개선된 모델 구성
# LSTM 유닛 수 증가 + Dense 레이어 추가 + Dropout 강화
model = Sequential()
model.add(Embedding(len(tokenizer.word_index) + 1, 200))  # 단어를 임베딩 벡터로 변환
model.add(Bidirectional(LSTM(128, return_sequences=True)))  # 앞뒤 문맥 정보 수집 강화
model.add(Dropout(0.5))
model.add(Bidirectional(LSTM(64)))  # 추가 LSTM으로 정보 통합
model.add(BatchNormalization())
model.add(Dense(64, activation='relu'))  # 표현력 강화
model.add(Dropout(0.5))  # 과적합 방지
model.add(Dense(1, activation='sigmoid'))  # sigmoid로 긍/부정 이진 분류

model.compile(optimizer=Adam(learning_rate=0.0003), loss="binary_crossentropy", metrics=["accuracy"])


#  7. 학습
early_stopping = EarlyStopping(monitor="val_loss", patience=2, restore_best_weights=True)
model.fit(
    X_train_pad,
    y_train,
    validation_split=0.2,
    epochs=10,
    batch_size=64,
    callbacks=[early_stopping]
)

#  8. 테스트 평가 (빈 댓글 제거된 것과 y_test 동기화)
X_y_test_pair = [(x, y) for x, y in zip(X_test, test_data['label']) if len(x) > 0]
X_test_filtered, y_test = zip(*X_y_test_pair)

# 토크나이징 → 시퀀싱 → 패딩
X_test_seq = tokenizer.texts_to_sequences(X_test_filtered)
X_test_pad = pad_sequences(X_test_seq, maxlen=max_len)
y_test = np.array(y_test)

# 예측 및 성능 출력
y_pred = model.predict(X_test_pad)
y_pred_labels = (y_pred > 0.5).astype(int)

print("\n 테스트 성능:\n")
print(classification_report(y_test, y_pred_labels))

#  9. 모델 저장
model.save("sentiment_model.h5")
with open("tokenizer_config.pkl", "wb") as f:
    pickle.dump({"tokenizer": tokenizer, "max_len": max_len}, f)

print("\n형태소 분석 기반 전처리 모델 저장 완료!")
