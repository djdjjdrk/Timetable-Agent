"""补充 aaa 的课程和秋季课表；默认预览，--apply 后事务写入，可重复运行。"""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Course, Schedule, User


COURSES = [
    ("MATH101", "高等数学", ""),
    ("ENG101", "大学英语", ""),
    ("DS101", "数据结构", ""),
    ("DM201", "离散数学", "命题逻辑、集合与关系、图论和组合计数，培养计算机专业的数学基础。"),
    ("PY201", "Python程序设计", "函数、面向对象、文件处理与常用标准库，配套上机练习和综合实践。"),
    ("DB201", "数据库原理与应用", "关系模型、SQL、数据库设计、事务与索引，结合 PostgreSQL 开展实践。"),
    ("OS201", "操作系统", "进程与线程、进程调度、内存管理、文件系统及 Linux 基础实践。"),
    ("PE201", "大学体育（羽毛球）", "羽毛球基本步法、发球与击球技术，结合体能训练和双打练习。"),
]

# 周一至周五，每周 12 次课、24 学时；午休、晚上及周末不新增课程。
WEEK = [
    (0, "1-2节", "MATH101", "教学楼 A102"),
    (0, "3-4节", "DS101", "教学楼 B305"),
    (1, "1-2节", "ENG101", "教学楼 A201"),
    (1, "3-4节", "PY201", "计算机实验楼 C203"),
    (1, "5-6节", "DM201", "教学楼 B302"),
    (2, "1-2节", "MATH101", "教学楼 A102"),
    (2, "3-4节", "DB201", "计算机实验楼 C205"),
    (2, "7-8节", "PE201", "体育馆羽毛球场"),
    (3, "1-2节", "DS101", "教学楼 B305"),
    (3, "3-4节", "PY201", "计算机实验楼 C203"),
    (4, "1-2节", "ENG101", "教学楼 A201"),
    (4, "3-4节", "OS201", "教学楼 B308"),
]


def periods(value):
    match = re.fullmatch(r"\s*(\d+)\s*(?:[-~～—至]\s*(\d+))?\s*节?\s*", value)
    if not match:
        raise ValueError(f"无法识别已有节次，停止写入以避免冲突：{value}")
    start, end = int(match[1]), int(match[2] or match[1])
    if start < 1 or end < start:
        raise ValueError(f"无效节次：{value}")
    return set(range(start, end + 1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="实际写入；默认仅预览")
    args = parser.parse_args()
    with SessionLocal() as db, db.begin():
        user = db.scalar(select(User).where(User.username == "aaa").with_for_update())
        if user is None or user.role != "student" or user.status != 1:
            raise ValueError("aaa 必须是已存在且正常启用的学生账号")
        courses = {}
        new_courses = []
        for code, name, description in COURSES:
            course = db.scalar(select(Course).where(Course.code == code))
            if course is None:
                course = db.scalar(select(Course).where(Course.name == name))
            if course is None:
                if not description:
                    raise ValueError(f"缺少预期基础课程：{code}")
                course = Course(code=code, name=name, description=description, status=1)
                db.add(course)
                new_courses.append(course)
            if course.status != 1:
                raise ValueError(f"课程已停用：{name}")
            courses[code] = course
        db.flush()
        existing = list(db.scalars(select(Schedule).where(Schedule.user_id == user.id)))
        added, skipped = [], 0
        for week in range(8):
            for weekday, period, code, location in WEEK:
                day = date(2026, 10, 26) + timedelta(weeks=week, days=weekday)
                course = courses[code]
                overlaps = [s for s in existing if s.class_date == day and periods(s.period) & periods(period)]
                if overlaps:
                    if len(overlaps) == 1 and overlaps[0].course_id == course.id and periods(overlaps[0].period) == periods(period):
                        skipped += 1
                        continue
                    raise ValueError(f"{day} {period} 与已有课表冲突，已取消本次写入")
                item = Schedule(user_id=user.id, course_id=course.id, class_date=day, period=period, location=location)
                db.add(item)
                existing.append(item)
                added.append(item)
        db.flush()
        summary = {
            "applied": args.apply,
            "username": user.username,
            "start": "2026-10-26",
            "end": "2026-12-18",
            "courses_added": [{"id": c.id, "name": c.name, "code": c.code} for c in new_courses],
            "schedules_added": len(added),
            "existing_sessions_reused": skipped,
            "new_schedule_ids": [s.id for s in added],
            "weekly_class_hours": 24,
        }
        if not args.apply:
            db.rollback()
        print(json.dumps(summary, ensure_ascii=True))


if __name__ == "__main__":
    main()
