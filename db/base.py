"""
Base declarativa de SQLAlchemy compartida por todos los modelos.
Importar siempre desde aquí para evitar referencias circulares.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
