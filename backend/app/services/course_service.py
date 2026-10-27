from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.common.exceptions import BusinessException
from app.models.course import Course
from app.models.schedule import Schedule
from app.schemas.course import CourseCreateRequest, CourseResponse, CourseUpdateRequest


def list_courses(db: Session, keywords: str | None = None) -> list[CourseResponse]:
    """课程的列表。"""
    query = db.query(Course)
    if keywords and keywords.strip():
        kw = f"%{keywords.strip()}%"
        query = query.filter(
            or_(
                Course.name.ilike(kw),
                Course.code.ilike(kw),
                Course.description.ilike(kw),
            )
        )
    rows = query.order_by(Course.id.desc()).all()
    return [CourseResponse.model_validate(row) for row in rows]


def _get_course(db: Session, course_id: int) -> Course:
    row = db.query(Course).filter(Course.id == course_id).first()
    if not row:
        raise BusinessException(message="课程不存在")
    return row


def get_course(db: Session, course_id: int) -> CourseResponse:
    """课程详情。"""
    return CourseResponse.model_validate(_get_course(db, course_id))


def _save_course(db: Session, course: Course) -> CourseResponse:
    code, course_id = course.code, course.id
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # 数据库唯一约束兜底，处理并发提交相同代码的情况。
        if code and db.query(Course).filter(
            Course.code == code, Course.id != course_id
        ).first():
            raise BusinessException(message="课程代码已存在") from None
        raise
    db.refresh(course)
    return CourseResponse.model_validate(course)


def create_course(db: Session, data: CourseCreateRequest) -> CourseResponse:
    """新增课程；空代码保存为 None，有值时必须唯一。"""
    code = (data.code or "").strip() or None
    if code and db.query(Course).filter(Course.code == code).first():
        raise BusinessException(message="课程代码已存在")
    course = Course(
        name=data.name.strip(),
        code=code,
        description=(data.description or "").strip() or None,
        status=data.status,
    )
    db.add(course)
    return _save_course(db, course)


def update_course(
    db: Session, course_id: int, data: CourseUpdateRequest
) -> CourseResponse:
    """更新课程，省略字段保持原值，代码和简介允许清空。"""
    row = _get_course(db, course_id)
    payload = data.model_dump(exclude_unset=True)
    for field in ("name", "status"):
        if payload.get(field) is None:
            payload.pop(field, None)
    if "name" in payload:
        payload["name"] = payload["name"].strip()
    if "code" in payload:
        code = (payload["code"] or "").strip() or None
        if code and db.query(Course).filter(
            Course.code == code, Course.id != course_id
        ).first():
            raise BusinessException(message="课程代码已存在")
        payload["code"] = code
    if "description" in payload:
        payload["description"] = (payload["description"] or "").strip() or None
    for field, value in payload.items():
        setattr(row, field, value)
    return _save_course(db, row)


def delete_course(db: Session, course_id: int) -> None:
    """删除课程，已关联课表的课程不可删除。"""
    row = _get_course(db, course_id)
    linked = db.query(Schedule.id).filter(Schedule.course_id == course_id).first()
    if linked:
        raise BusinessException(message="该课程已关联课表，无法删除")
    db.delete(row)
    db.commit()
