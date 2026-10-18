#!/bin/sh
# 跨卷搬运演员目录。用法：
#   sh media-merge.sh plan.tsv          # dry-run，只打印将要执行的 rsync
#   sh media-merge.sh plan.tsv apply    # 真搬（rsync 复制+校验，成功后才删源）
#
# plan.tsv 每行：<源目录>\t<目标目录>
#
# 特性：
#   - rsync 3.0.9 兼容（DSM 6 自带版本，没有 --info=progress2）
#   - 可断点续传；中断后重跑同一条命令即可，已传的自动跳过
#   - 三步走：复制 -> rsync --dry-run 校验 0 差异 -> 才 rm -rf 源
#   - 任何一步失败立即退出并保留源
#   - 每条操作前后都写 migration-log/media-merge.log

set -u
PLAN="$1"
MODE="${2:-dryrun}"
LOG=/volume2/docker/mymoviedb/migration-log
mkdir -p "$LOG"
STAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

log() {
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$STAMP" "MERGE" "$1" "$2" "$3" "$4" "$5" >> "$LOG/media-merge.log"
}

if [ ! -f "$PLAN" ]; then
    echo "找不到计划文件: $PLAN"
    exit 1
fi

echo "模式: $MODE   计划: $PLAN"
echo "-------------------------------------------"

n=0
while IFS='	' read -r SRC DST; do
    case "$SRC" in ''|\#*) continue ;; esac
    [ -z "${DST:-}" ] && continue
    n=$((n+1))

    if [ ! -d "$SRC" ]; then
        log SKIP "$SRC" "-" "-" "源目录不存在"
        echo "[$n] 跳过（源不存在）"
        continue
    fi
    if [ "$SRC" = "$DST" ]; then
        log ERROR "$SRC" "-" "-" "源与目标相同"
        echo "[$n] 错误：源与目标相同"
        exit 1
    fi

    SZ=$(du -sk "$SRC" 2>/dev/null | cut -f1)
    echo ""
    echo "[$n] $SRC"
    echo "  -> $DST   (${SZ}K)"

    if [ "$MODE" != "apply" ]; then
        echo "    dry-run"
        log DRYRUN "$SRC" "$DST" "$SZ" "PENDING"
        continue
    fi

    mkdir -p "$DST" || { log ERROR "$SRC" "$DST" "$SZ" "创建目标失败"; exit 1; }

    rsync -aH --stats --partial --exclude='.DS_Store' "$SRC/" "$DST/"
    rc=$?
    if [ $rc -ne 0 ]; then
        log ERROR "$SRC" "$DST" "$SZ" "rsync复制失败 rc=$rc 源保留"
        echo "    复制失败 rc=$rc，源已保留。修好后重跑同一条命令。"
        exit 1
    fi

    # 校验：只问「源的内容是否都已存在于目标」。
    # 不能加 --delete —— 目标本来就含另一份副本里的其它番号，那是正常的，
    # 加了 --delete 会把「目标多出来的文件」误报成差异。
    DIFF=$(rsync -aHn --itemize-changes "$SRC/" "$DST/" 2>/dev/null | grep -v '/$@eaDir' | grep -v '@SynoEAStream' | wc -l)
    if [ "$DIFF" -ne 0 ]; then
        log ERROR "$SRC" "$DST" "$SZ" "校验发现$DIFF处差异 源保留"
        echo "    校验发现 $DIFF 处差异，源已保留："
        rsync -aHn --itemize-changes "$SRC/" "$DST/" | head -20
        exit 1
    fi

    if [ "${KEEP_SOURCE:-0}" = "1" ]; then
        log COPY "$SRC" "$DST" "$SZ" "OK(校验通过,保留源)"
        echo "    校验通过，KEEP_SOURCE=1 保留源"
        continue
    fi

    rm -rf "$SRC" || { log ERROR "$SRC" "$DST" "$SZ" "删源失败,数据已在目标"; continue; }
    log MOVE "$SRC" "$DST" "$SZ" "OK(复制+校验通过,已删源)"
    echo "    完成"
done < "$PLAN"

echo ""
echo "-------------------------------------------"
if [ "$MODE" = "apply" ]; then
    echo "完成。日志: $LOG/media-merge.log"
    echo "下一步同步数据库:"
    echo "  sudo /usr/local/bin/docker exec mymoviedb python3 /app/scripts_sync.py --check"
else
    echo "dry-run 结束，未做任何改动。"
fi
