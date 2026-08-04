#!/bin/bash
# ============================================================
# Git Commit 质量门检查脚本
# 检查两条通行证是否齐全
# 返回 0 = 放行，返回 2 = 拦截
# ============================================================

RESULTS_DIR=".claude/results"
TESTER_FILE="$RESULTS_DIR/tester-result.txt"
QUALITY_FILE="$RESULTS_DIR/quality-result.txt"

if [ ! -f "$TESTER_FILE" ] || [ ! -f "$QUALITY_FILE" ]; then
  echo "=============================================="
  echo "  质量门未通过：缺少检查结果"
  echo "=============================================="
  echo ""
  echo "  原因：没有找到单元测试或代码质量的通行证。"
  echo ""
  echo "  请先运行 gitcommit-agent 完成质量检查后再提交："
  echo "    - 在对话中输入：'帮我提交代码'"
  echo "    - 或直接调用 gitcommit-agent"
  echo ""
  echo "  质量门 = 单元测试 PASS + 代码质量 PASS"
  echo "=============================================="
  exit 2
fi

TESTER_RESULT=$(head -1 "$TESTER_FILE")
QUALITY_RESULT=$(head -1 "$QUALITY_FILE")

if [ "$TESTER_RESULT" = "PASS" ] && [ "$QUALITY_RESULT" = "PASS" ]; then
  echo "=============================================="
  echo "  质量门通过"
  echo "=============================================="
  echo "  单元测试 : PASS"
  echo "  代码质量 : PASS"
  echo "=============================================="
  exit 0
else
  echo "=============================================="
  echo "  质量门未通过"
  echo "=============================================="
  echo ""
  if [ "$TESTER_RESULT" != "PASS" ]; then
    echo "  [单元测试] FAIL"
    echo "  ----------------------------------------"
    cat "$TESTER_FILE"
    echo ""
  fi
  if [ "$QUALITY_RESULT" != "PASS" ]; then
    echo "  [代码质量] FAIL"
    echo "  ----------------------------------------"
    cat "$QUALITY_FILE"
    echo ""
  fi
  echo "  请修复上述问题后重新运行质量检查。"
  echo "=============================================="
  exit 2
fi
