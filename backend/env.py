import os

from dotenv import load_dotenv


def load_environment():
    backend_dir = os.path.dirname(__file__)
    project_dir = os.path.dirname(backend_dir)
    load_dotenv(os.path.join(project_dir, ".env"))
    load_dotenv(os.path.join(backend_dir, ".env"))


load_environment()