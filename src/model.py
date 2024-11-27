"""
This file creates boto3 session for bedrock and makes model calls as per prompts and case.
Author: vatsal1306
"""
import base64
import io
import json
import os
import sys
from ast import literal_eval

import boto3
from PIL import Image
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from src import ROOT_DIR
from src.Logging import logger
from src.Utils import settings
from src.Utils.utils import Person, Response

env = load_dotenv(dotenv_path=os.path.join(ROOT_DIR, '.env'), verbose=True)
assert env == True

workout_plan = {}
with open(os.path.join(ROOT_DIR, 'sample_workout_plan.json')) as f:
    workout_plan = json.load(f)
logger.info("Loaded sample workout plan")

mealplan = {}
with open(os.path.join(ROOT_DIR, "sample_meal_plan.json"), 'r') as f:
    mealplan = json.load(f)
logger.info("Loaded sample meal plan")

water_plan = {}
with open(os.path.join(ROOT_DIR, "sample_water_intake.json"), 'r') as f:
    water_plan = json.load(f)
logger.info("Loaded sample water intake")


class FileReader:
    def __init__(self):
        self.workout_up = self._read_file(os.path.join(ROOT_DIR, "prompts", "workout_usr_prompt.txt"))
        self.workout_sp = self._read_file(os.path.join(ROOT_DIR, "prompts", "workout_system_prompt.txt"))
        self.diet_up = self._read_file(os.path.join(ROOT_DIR, "prompts", "diet_usr_prompt.txt"))
        self.diet_sp = self._read_file(os.path.join(ROOT_DIR, "prompts", "diet_system_prompt.txt"))
        self.water_sp = self._read_file(os.path.join(ROOT_DIR, "prompts", "water_system_prompt.txt"))
        self.water_up = self._read_file(os.path.join(ROOT_DIR, "prompts", "water_usr_prompt.txt"))

    def _read_file(self, filepath: str) -> str:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        else:
            logger.error(f"File {filepath} not found.")
            sys.exit(1)


# @Wrappers.singleton
class LLM(FileReader):
    """ Class for interacting with Bedrock."""

    def __init__(self):
        FileReader.__init__(self)
        self.client = self._get_bedrock_client()
        self.s3 = self._get_s3_client()
        self.text_model = settings.text_model
        self.image_model = settings.image_model
        self.temperature = float(settings.temperature)
        self.top_p = float(settings.top_p)
        self.max_tokens = int(settings.max_tokens)
        logger.info("LLM class initialized")

    @staticmethod
    def _get_s3_client():
        boto3_session = boto3.Session(aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                                      aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'), )
        return boto3_session.client('s3', region_name=os.getenv('AWS_REGION'))

    @staticmethod
    def _get_bedrock_client():
        """
        Initialize Bedrock client using boto3. AWS keys are fetched from .env file
        :return: botocore.client.BedrockRuntime
        """
        boto3_session = boto3.Session(aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                                      aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'), )
        return boto3_session.client('bedrock-runtime', region_name=os.getenv('AWS_REGION'))

    def generate_image(self, data: Response, id: int) -> Response:
        meal_data = data.get("success")
        if isinstance(meal_data, str):
            try:
                meal_data = json.loads(meal_data)
            except SyntaxError:
                meal_data = literal_eval(meal_data)

        try:
            for key, val in meal_data.items():
                for k, v in val.items():
                    img_prompt = f"Generate an image of meal({v['name']}) ingredients({', '.join(v['ingredients'])})."
                    logger.info(f"Image prompt - {img_prompt}")
                    img_body = json.dumps({"taskType": "TEXT_IMAGE", "textToImageParams": {"text": img_prompt},
                                           "imageGenerationConfig": {"numberOfImages": 1, "height": 512, "width": 512,
                                                                     "cfgScale": 8.0, "seed": 0}})
                    content_type = "application/json"
                    try:
                        response = self.client.invoke_model(body=img_body, modelId=self.image_model,
                                                            accept=content_type,
                                                            contentType=content_type)
                    except ClientError as e:
                        logger.error(f"Error while invoke model for image - {e}")
                        return {"error": str(e)}
                    except Exception as e:
                        logger.error(f"unknown error while invoke model for image - {e}")
                        return {"error": str(e)}

                    response = json.loads(response.get("body").read())
                    base64_image = response.get("images")[0]
                    base64_bytes = base64_image.encode('ascii')
                    image_bytes = base64.b64decode(base64_bytes)
                    finish_reason = response.get("error")
                    img_buffer = io.BytesIO(image_bytes)
                    img = Image.open(img_buffer)
                    img.save('test.png')
                    self.s3.upload_file('test.png', os.getenv('S3_BUCKET'), f"{id}/{key}/{k}.png")
                    # s3: // forge - meal - image / test.png
                    v['s3_location'] = f"s3://{os.getenv('S3_BUCKET')}/{id}/{key}/{k}.png"
        except Exception as e:
            logger.exception(f"unknown error while generating image - {e}")
            return {"error": str(e)}

        data["success"] = meal_data
        return data

    def _data_validation(self, resp: str) -> Response:
        try:
            resp_dict = literal_eval(resp)
            resp_dict = {"success": resp_dict}
        except SyntaxError:
            try:
                resp_dict = json.loads(resp)
                resp_dict = {"success": resp_dict}
            except SyntaxError as e:
                err_msg = f"Bedrock response is not in json, got - {e}"
                logger.error(err_msg)
                resp_dict = {"error": err_msg}
        except Exception as e:
            logger.exception(str(e))
            resp_dict = {"error": str(e)}

        return resp_dict

    def get_text_response(self, data: Person, event: str) -> Response:
        usr_data = f"Age={data.age}, Gender={data.gender}, Height={data.height}, Weight={data.weight}, current bodytype={data.current_body_type}, target bodytype={data.target_body_type}, diet preference={data.diet_preference}, Allergy={data.allergens}"
        match event:
            case "workout":
                system_msg = [{"text": self.workout_sp}]
                self.workout_up = self.workout_up.format(usr_data, workout_plan)
                usr_message = [{"role": "user", "content": [{"text": self.workout_up}]}]
                logger.info(f"Workout prompt - {self.workout_up}")
            case "meal":
                system_msg = [{"text": self.diet_sp}]
                self.diet_up = self.diet_up.format(usr_data, mealplan)
                usr_message = [{"role": "user", "content": [{"text": self.diet_up}]}]
                logger.info(f"Meal prompt - {self.diet_up}")
            case "water":
                system_msg = [{"text": self.water_sp}]
                self.water_up = self.water_up.format(usr_data, water_plan)
                usr_message = [{"role": "user", "content": [{"text": self.water_up}]}]
                logger.info(f"Water prompt - {self.water_up}")
            case _:
                logger.exception(f"{event} is not a valid case.")
                return {"error": f"TypeError: got invalid case [{event}]. Expected [workout, meal]."}

        try:
            response = self.client.converse(modelId=self.text_model, messages=usr_message, system=system_msg,
                                            inferenceConfig={"temperature": self.temperature,
                                                             "topP": self.top_p})
        except ClientError as e:
            logger.exception(e)
            return {"error": str(e)}

        except Exception as err:
            logger.exception(f"unknown exception occurred: {err}")
            return {"error": str(err)}

        if response["ResponseMetadata"]['HTTPStatusCode'] != 200:
            err_msg = f"Bedrock HTTP response is not success - {response}"
            logger.error(err_msg)
            return {"error": err_msg}

        logger.info(f"Response fetched successfully - {response['usage']}")
        response = response["output"]["message"]["content"][0]["text"]
        response = response.replace("```", "")
        response = response.replace("json", "", 1)
        logger.info(f"Response: {response}")

        response = self._data_validation(response)

        return response

# obj = LLM()
# data = Test(age=25, gender="male", height=170, weight=84, current_body_type="fat", target_body_type="cutting",
#             diet_preference="veg", allergens="non-veg")
# case = "diet"
# resp = obj.get_text_response(data, case)

# if resp["success"]:
#     op = resp["success"]
#     try:
#         op = op.replace("```", "")
#         op = op.replace("json", "", 1)
#         op_dict = literal_eval(op)
#     except SyntaxError as e:
#         try:
#             op_dict = json.loads(op)
#         except SyntaxError as e:
#             logger.error(f"Bedrock response is not in json, got - {e}")
#             op_dict = {"error": str(e)}
#     if op_dict:
#         if case == "workout":
#             with open(os.path.join(ROOT_DIR, "output",
#                                    f"workout_{str(datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))}.json"), "w",
#                       encoding="utf-8") as f:
#                 json.dump(op_dict, f, indent=4)
#
#         if case == "diet":
#             with open(
#                     os.path.join(ROOT_DIR, "output", f"diet_{str(datetime.now().strftime('%Y-%m-%d_%H-%M-%S'))}.json"),
#                     "w",
#                     encoding="utf-8") as f:
#                 json.dump(op_dict, f, indent=4)

# print("Hey")
# one = DailyWorkout(day=1, workouts=[
#     Workout(name="warm-up", description="5-10 mins of cardio (treadmill, bike)"),
#     Workout(name="Incline dumbbell press", sets=3, reps=12, weight=10),
#     Workout(name="Cable Flyes", sets=3, reps=12, weight=12),
#     Workout(name="Triceps pushdown", sets=3, reps=10, weight=10)
# ])
# two = DailyWorkout(day=2, workouts=[
#     Workout(name="warm-up", description="5-10 mins of cardio (treadmill, bike)"),
#     Workout(name="Pull-ups", sets=3, reps=8, description="or assisted pull-ups"),
#     Workout(name="Barbell rows", sets=3, reps=8),
#     Workout(name="Lat Pulldowns", sets=3, reps=10, weight=10),
#     Workout(name="Dumbell bicep curls", sets=3, reps=12, weight=12),
#     Workout(name="Hammer curls", sets=3, reps=12, weight=8)
# ])
# wp = WorkoutPlan(workoutplan=[one, two])
# from pprint import pprint
# pprint(wp.dict())
# print("\n\nBased on the provided details, I'll create a customized workout plan for the individual.\n\n**Workout Goals:**\n\n* Target Body Type: Cutting\n* Current Body Type: Fat\n* Age: 25\n* Gender: Male\n* Height: 170 cm\n* Weight: 84 kg\n* Diet Preference: Veg\n* Allergens: Non-veg (not applicable, as diet preference is veg)\n\n**Workout Plan:**\n\nTo achieve a cutting physique, we'll focus on a combination of cardio, strength training, and high-intensity interval training (HIIT). This will help burn fat, build lean muscle, and improve overall fitness.\n\n**Workout Split:**\n\n* Day 1: Chest and Triceps\n* Day 2: Back and Biceps\n* Day 3: Legs\n* Day 4: Shoulders and Abs\n* Day 5: Cardio and HIIT\n* Day 6 and 7: Rest days\n\n**Workout Routine:**\n\n**Day 1: Chest and Triceps**\n\n1. Warm-up: 5-10 minutes of cardio (treadmill, bike, or elliptical)\n2. Barbell Bench Press: 3 sets of 8-12 reps\n3. Incline Dumbbell Press: 3 sets of 10-15 reps\n4. Cable Flyes: 3 sets of 12-15 reps\n5. Tricep Pushdowns: 3 sets of 10-12 reps\n6. Tricep Dips: 3 sets of 12-15 reps\n7. Cool-down: 5-10 minutes of stretching\n\n**Day 2: Back and Biceps**\n\n1. Warm-up: 5-10 minutes of cardio\n2. Pull-ups: 3 sets of 8-12 reps (or Assisted Pull-ups)\n3. Barbell Rows: 3 sets of 8-12 reps\n4. Lat Pulldowns: 3 sets of 10-12 reps\n5. Dumbbell Bicep Curls: 3 sets of 10-12 reps\n6. Hammer Curls: 3 sets of 10-12 reps\n7. Cool-down: 5-10 minutes of stretching\n\n**Day 3: Legs**\n\n1. Warm-up: 5-10 minutes of cardio\n2. Squats: 3 sets of 8-12 reps\n3. Leg Press: 3 sets of 10-12 reps\n4. Lunges: 3 sets of 10-12 reps (per leg)\n5. Leg Extensions: 3 sets of 12-15 reps\n6. Leg Curls: 3 sets of 10-12 reps\n7. Cool-down: 5-10 minutes of stretching\n\n**Day 4: Shoulders and Abs**\n\n1. Warm-up: 5-10 minutes of cardio\n2. Dumbbell Shoulder Press: 3 sets of 8-12 reps\n3. Lateral Raises: 3 sets of 10-12 reps\n4. Planks: 3 sets of 30-60 seconds\n5. Russian Twists: 3 sets of 10-12 reps\n6. Leg Raises: 3 sets of 10-12 reps\n7. Cool-down: 5-10 minutes of stretching\n\n**Day 5: Cardio and HIIT**\n\n1. Warm-up: 5-10 minutes of cardio\n2. High-Intensity Interval Training (HIIT):\n\t* Sprints: 30 seconds of all-out effort followed by 30 seconds of rest\n\t* Burpees: 30 seconds of all-out effort followed by 30 seconds of rest\n\t* Jumping Jacks: 30 seconds of all-out effort followed by 30 seconds of rest\n\t* Repeat for 15-20 minutes\n3. Cool-down: 5-10 minutes of stretching\n\n**Progressive Overload:**\n\n* Increase the weight you lift by 2.5-5kg every two weeks, or as soon as you feel you can handle more.\n* Increase the number of reps or sets as you get stronger.\n\n**Nutrition Plan:**\n\nTo support your cutting goals, focus on a balanced diet with a caloric deficit. Aim for:\n\n* 1700-2000 calories per day\n* 1.6-2.2 grams of protein per kilogram of body weight (112-140g for you)\n* 2-3 grams of carbohydrates per kilogram of body weight (134-250g for you)\n* 0.5-1 gram of healthy fats per kilogram of body weight (42-84g for you)\n\nEat lean protein sources like legumes, beans, lentils, tofu, and tempeh. Include complex carbohydrates like brown")
# print(data)
