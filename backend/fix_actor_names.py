"""
数据库迁移脚本 - 清理演员名称中的方括号和无效字符
使用方法: python fix_actor_names.py
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'backend'))
from database import get_db


def clean_actor_name(name: str) -> str:
    """清理演员名称中的方括号、引号等"""
    if not name:
        return name
    # 去除首尾的方括号、引号、空格
    cleaned = name.strip().strip('[]"\' ')
    return cleaned if cleaned else name


def is_valid_actor(name: str) -> bool:
    """检查是否为有效的演员名"""
    if not name or len(name) < 2:
        return False
    invalid_names = {'佚名', '未知', '[未找到]', 'None', ''}
    if name in invalid_names:
        return False
    # 过滤明显不是演员名的
    if name.startswith('★') or '商品ご購入' in name or '画像' in name or '拡大' in name:
        return False
    if name.startswith('ᐸ') or 'img' in name.lower():
        return False
    return True


def fix_actor_names():
    """修复数据库中所有影片的演员名称"""
    print("开始修复演员名称...")

    conn = get_db()
    cursor = conn.cursor()

    # 获取所有影片
    cursor.execute("SELECT id, code, actors FROM movies WHERE actors IS NOT NULL AND actors != '[]' AND actors != ''")
    rows = cursor.fetchall()

    fixed_count = 0

    for movie_id, code, actors_str in rows:
        try:
            # 解析 JSON 数组
            actors = json.loads(actors_str)
            if not isinstance(actors, list):
                print(f"  警告: {code} actors 不是数组: {repr(actors_str)}")
                continue

            # 清理每个演员名称
            cleaned_actors = []
            for actor in actors:
                cleaned = clean_actor_name(actor)
                # 验证是否为有效演员名
                if is_valid_actor(cleaned) and cleaned not in cleaned_actors:
                    cleaned_actors.append(cleaned)

            # 如果有变化，更新数据库
            if cleaned_actors:
                new_actors_str = json.dumps(cleaned_actors, ensure_ascii=False)
                if new_actors_str != actors_str:
                    cursor.execute("UPDATE movies SET actors = ? WHERE id = ?", (new_actors_str, movie_id))
                    fixed_count += 1
                    if fixed_count <= 20:  # 只打印前20个
                        print(f"  修复: {code}")
                        print(f"    Before: {actors_str}")
                        print(f"    After:  {new_actors_str}")

        except json.JSONDecodeError as e:
            print(f"  JSON解析错误: {code} - {repr(actors_str)}: {e}")
        except Exception as e:
            print(f"  错误: {code} - {e}")

    conn.commit()
    print(f"\n修复完成！共修复 {fixed_count} 部影片的演员数据")


if __name__ == "__main__":
    fix_actor_names()
