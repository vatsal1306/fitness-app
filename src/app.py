"""
File for application code for fastapi. execute run command in Makefile to start the uvicorn server.
Author: vatsal1306
"""
import json
import os
from time import time

from fastapi import FastAPI

from src import ROOT_DIR
from src.Logging import logger
from src.Utils.utils import Person, Response, adjust_format
from src.model import LLM

app = FastAPI()
logger.info("Application started")


# model = LLM()


# @app.on_event("startup")
# def init_model():
#     LLM()


@app.get("/")
async def root():
    return {"msg": "Home page"}


@app.post("/test/water")
async def test_water(item: Person):
    return {"success": {"liters": 2.8}}


@app.post("/test/workout")
async def test_workout(item: Person):
    resp = {}
    with open(os.path.join(ROOT_DIR, 'output', 'sample_workout_output.json')) as f:
        resp = json.load(f)
    return resp


@app.post("/test/meal")
async def test_meal(item: Person):
    resp = {}
    with open(os.path.join(ROOT_DIR, 'output', 'sample_diet_output.json')) as f:
        resp = json.load(f)

    resp = adjust_format(resp)
    return resp


@app.post('/water')
async def water(item: Person):
    try:
        water_start = time()
        logger.info(f"Executing {item}")
        model = LLM()
        response: Response = model.get_text_response(item, "water")
        logger.info(f"/water done in {time() - water_start} seconds.")
        return response
    except Exception as e:
        logger.exception(e)
        return {"error": str(e)}


@app.post('/workout')
async def workout(item: Person):
    try:
        workout_start = time()
        logger.info(f"Executing /workout for - {item}")
        model = LLM()
        response: Response = model.get_text_response(item, "workout")
        logger.info(f"/workout done in {time() - workout_start} seconds.")
        return response
    except Exception as e:
        logger.exception(e)
        return {"error": str(e)}


@app.post('/meal')
async def meal(item: Person):
    try:
        meal_start = time()
        logger.info(f"Executing /meal for - {item}")
        model = LLM()
        response: Response = model.get_text_response(item, "meal")
        response: Response = model.generate_image(response, item.id)
        response: Response = adjust_format(response)
        logger.info(f"/meal done in {time() - meal_start} seconds.")
        return response
    except Exception as e:
        logger.exception(e)
        return {"error": str(e)}
