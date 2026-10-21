from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from app.common.response import Response
from app.common.exceptions import (
    BusinessException,
    bussiness_excpetion_hadler,
    http_excpetion_hadler,
    validation_excpetion_hadler,
    global_excpetion_hadler,
)
from app.models.user import User
from app.database import Base, engine
from app.api import api
from app.config import UPLOAD_DIR

Base.metadata.create_all(bind=engine)

app = FastAPI()
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(BusinessException, bussiness_excpetion_hadler)  # type: ignore
app.add_exception_handler(HTTPException, http_excpetion_hadler)  # type: ignore
app.add_exception_handler(RequestValidationError, validation_excpetion_hadler)  # type: ignore
app.add_exception_handler(Exception, global_excpetion_hadler)
app.include_router(api)

# 挂载静态资源：/uploads/xxx.jpg → uploads/xxx.jpg
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/", response_model=Response)
def root():
    return Response.success(message="Hello FastAPI")
