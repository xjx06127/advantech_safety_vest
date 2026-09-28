import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.linear_model import LinearRegression
from sklearn.metrics import r2_score

# 한글 폰트 설정 (Windows: Malgun Gothic, Mac: AppleGothic)
plt.rcParams['font.family'] = 'Malgun Gothic' 
plt.rcParams['axes.unicode_minus'] = False

def run_analysis():
    print("--- [데이터 분석 시작] ---")
    
    # 1. 데이터 로드 및 변수 정의
    try:
        df = pd.read_csv('../data/training_dataset.csv')
        print(">> 데이터 로드 성공")
    except FileNotFoundError:
        print("[오류] 'training_dataset.csv' 파일을 찾을 수 없습니다.")
        return

    target_col = 'mean.WristT_60' 
    features_env = ['mean.Temperature_60', 'mean.Humidity_60']
    features_all = features_env + ['mean.hr_60'] 

    # 필요한 모든 컬럼을 포함하는 데이터프레임 생성 및 결측치 제거
    analysis_df = df[features_all + [target_col]].dropna()
    print(f">> 분석에 사용된 샘플 수: {len(analysis_df)}개")
    print("-" * 30)

    # =========================================================
    # 3. 상관 관계 분석 (Correlation Analysis)
    # =========================================================
    print("\n[1] 상관 계수 (Correlation Coefficient) 분석")
    corr_matrix = analysis_df.corr()
    target_corr = corr_matrix[target_col].drop(target_col).sort_values(ascending=False)
    
    print(f"Target: {target_col} (손목 온도) 와의 상관관계")
    print(target_corr)
    
    # 상관관계 히트맵 시각화
    plt.figure(figsize=(10, 8))
    sns.heatmap(corr_matrix, annot=True, fmt=".3f", cmap='coolwarm', vmin=-1, vmax=1)
    plt.title('주요 변수 간 상관관계 히트맵')
    plt.tight_layout()
    plt.savefig('../docs/correlation_heatmap.png')
    print(">> 'correlation_heatmap_complete.png' 저장 완료")

    # =========================================================
    # 4. 단순 선형 회귀 (Simple Linear Regression) - 온도, 습도 각각
    # =========================================================
    print("\n[2] 단순 선형 회귀 분석 (Simple Regression)")
    
    # --- 4-1. WristT ~ EnvT (온도) ---
    X_temp = analysis_df[['mean.Temperature_60']].values
    y = analysis_df[target_col].values
    model_temp = LinearRegression().fit(X_temp, y)
    r2_temp = r2_score(y, model_temp.predict(X_temp))

    print("\n[2-1] WristT ~ 환경 온도 (EnvT)")
    print(f"   - 회귀식: WristT = {model_temp.coef_[0]:.5f} * EnvT + {model_temp.intercept_:.5f}")
    print(f"   - 기울기 (환경 영향도): {model_temp.coef_[0]:.5f}")
    print(f"   - 설명력 (R^2): {r2_temp:.5f}")
    
    # --- 4-2. WristT ~ Humi (습도) ---
    X_humi = analysis_df[['mean.Humidity_60']].values
    model_humi = LinearRegression().fit(X_humi, y)
    r2_humi = r2_score(y, model_humi.predict(X_humi))
    
    print("\n[2-2] WristT ~ 환경 습도 (Humi)")
    print(f"   - 회귀식: WristT = {model_humi.coef_[0]:.5f} * Humi + {model_humi.intercept_:.5f}")
    print(f"   - 기울기 (습도 영향도): {model_humi.coef_[0]:.5f}")
    print(f"   - 설명력 (R^2): {r2_humi:.5f}")
    
    # 회귀선 시각화 (온도)
    plt.figure(figsize=(10, 6))
    plt.scatter(X_temp, y, color='blue', alpha=0.5, label='실제 데이터')
    plt.plot(X_temp, model_temp.predict(X_temp), color='red', linewidth=2, label=f'회귀선 (R^2={r2_temp:.3f})')
    plt.xlabel('환경 온도 (Env Temp)')
    plt.ylabel('손목 온도 (Wrist Temp)')
    plt.title('환경 온도에 따른 손목 온도 변화')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.savefig('../docs/regression_plot.png')
    print(">> 'regression_plot_temp.png' 저장 완료")


    # =========================================================
    # 5. 다중 회귀 분석 (Multiple Regression) - 온도 + 습도 결합
    # =========================================================
    print("\n[3] 다중 회귀 분석 (Multiple Regression)")
    X_multi = analysis_df[features_env].values
    
    model_multi = LinearRegression()
    model_multi.fit(X_multi, y)
    r2_multi = r2_score(y, model_multi.predict(X_multi))

    print(f"[3-1] WristT ~ EnvT + Humi (환경 결합)")
    print(f"   - 다중 회귀 설명력 (R^2): {r2_multi:.5f}")
    print("   - 각 변수의 영향력 (회귀 계수):")
    for name, coef in zip(features_env, model_multi.coef_):
        print(f"     * {name}: {coef:.5f}")

    print("\n--- [데이터 분석 종료] ---")

if __name__ == "__main__":
    run_analysis()