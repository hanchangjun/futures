import pytest
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.connection import Base
from database import models # Import models to register them
from web.main import app, get_db
from fastapi.testclient import TestClient
from datafeed.base import PriceBar

# Use in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db_session():
    # Debug: Check if tables are registered
    # print("Registered tables:", Base.metadata.tables.keys())
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    del app.dependency_overrides[get_db]

@pytest.fixture
def sample_bars():
    # Create a simple trend: 5 bars up, 5 bars down
    bars = []
    base_price = 100.0
    start_time = datetime(2023, 1, 1, 9, 0)
    
    # Up trend
    for i in range(5):
        bars.append(PriceBar(
            date=start_time.replace(minute=i),
            open=base_price + i,
            high=base_price + i + 1,
            low=base_price + i - 0.5,
            close=base_price + i + 0.8,
            volume=100
        ))
        
    # Down trend
    for i in range(5):
        base = base_price + 5 - i
        bars.append(PriceBar(
            date=start_time.replace(minute=5+i),
            open=base,
            high=base + 0.5,
            low=base - 1,
            close=base - 0.8,
            volume=100
        ))
    return bars
