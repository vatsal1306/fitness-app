import inspect
import os
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Union, TypedDict


class Response(TypedDict, total=False):
    success: str
    error: str


class Workout(BaseModel):
    name: str = Field(..., description="Workout name.")
    sets: Optional[int] = Field("None", description="Number of sets.")
    reps: Optional[int] = Field("None", description="Number of reps.")
    weight: Optional[int] = Field("None", description="Weigh of equipment to set for current workout.")
    description: Optional[str] = Field("None",
                                       description="Workout description and extra information to take care for this workout.")


class DailyWorkout(BaseModel):
    day: int = Field(..., description="Day number.")
    workouts: List[Workout] = Field(..., description="List of workouts for the day.")


class WorkoutPlan(BaseModel):
    workoutplan: List[DailyWorkout] = Field(..., description="List of daily workouts.")


class Meal(BaseModel):
    name: str = Field(..., description="Meal name.")
    ingredients: List[str] = Field(..., description="List of ingredients.")
    recipe: str = Field(..., description="Meal recipe.")
    calories: int = Field(..., description="Meal calories.")


class DailyMeal(BaseModel):
    breakfast: Meal = Field(..., description="Breakfast")
    lunch: Meal = Field(..., description="Lunch")
    snacks: Meal = Field(..., description="Snacks")
    dinner: Meal = Field(..., description="Dinner")


class WeeklyMeal(BaseModel):
    monday: DailyMeal = Field(..., description="Monday")
    tuesday: DailyMeal = Field(..., description="Tuesday")
    wednesday: DailyMeal = Field(..., description="Wednesday")
    thursday: DailyMeal = Field(..., description="Thursday")
    friday: DailyMeal = Field(..., description="Friday")
    saturday: DailyMeal = Field(..., description="Saturday")
    sunday: DailyMeal = Field(..., description="Sunday")


class Person(BaseModel):
    id: int
    age: int
    gender: Literal["male", "female"]
    height: str
    weight: str
    current_body_type: str
    target_body_type: str
    diet_preference: str
    allergens: str


class Wrappers:
    @staticmethod
    def private_method(func):
        def wrapper(*args, **kwargs):
            frame = inspect.currentframe().f_back
            if frame.f_locals.get('self') is None and func.__name__.startswith('_'):
                raise ValueError("Access to private method is restricted.")
            return func(*args, **kwargs)

        return wrapper

    @staticmethod
    def singleton(cls):
        instances = dict()

        def wrap(*args, **kwargs):
            if cls not in instances:
                instances[cls] = cls(*args, **kwargs)
            return instances[cls]

        return wrap


class Path(str):
    """ Class for path validation and path manipulation. Use Path('valid/path/') for validation. """

    def __new__(cls, val):
        if not isinstance(val, str):
            raise TypeError(f"Expected str, got {type(val).__name__}")
        if not os.path.exists(val):
            raise ValueError(f"Path {val} does not exist.")
        return super().__new__(cls, val)

    @staticmethod
    def get_parent_dir(filepath: str) -> str:
        return "\\".join(filepath.split("\\")[:-1])

    @staticmethod
    def create_dir_if_not_exists(dir_path: str):
        if not os.path.exists(dir_path):
            try:
                os.makedirs(dir_path)
            except OSError as e:
                raise OSError(f"Failed to create directory {dir_path}: {e}")

    @staticmethod
    def create_file_if_not_exists(file_path: str):
        if not os.path.exists(file_path):
            try:
                open(file_path, "w").close()
            except OSError as e:
                raise OSError(f"Failed to create file {file_path}: {e}")
