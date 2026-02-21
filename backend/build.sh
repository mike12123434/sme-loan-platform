#!/usr/bin/env bash
# build.sh — Render 部署建置腳本
# 放在 backend/ 資料夾，Build Command 設為：bash build.sh
set -e  # 任何指令失敗即中止

echo "============================================"
echo "  永豐金控 SME API — Render Build Script"
echo "============================================"

# 1. 升級 pip
echo ""
echo "▶ Step 1: 升級 pip..."
pip install --upgrade pip

# 2. 安裝所有依賴
echo ""
echo "▶ Step 2: 安裝 Python 套件..."
pip install -r requirements.txt

# 3. 訓練模型（若 model.pkl 已存在則跳過）
echo ""
echo "▶ Step 3: 確保 model.pkl 存在..."
python train_model.py

echo ""
echo "✅ Build 完成！"
