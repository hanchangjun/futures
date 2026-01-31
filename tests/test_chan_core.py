from chan.fractal import find_fractals, FXType
from chan.common import ChanBar
from datetime import datetime

def test_find_top_fractal():
    # Construct a Top Fractal pattern: Up, Top, Down
    # ChanBar(index, date, high, low, elements)
    bars = [
        ChanBar(index=0, date=datetime(2023, 1, 1, 9, 0), high=10, low=5, elements=[]),
        ChanBar(index=1, date=datetime(2023, 1, 1, 9, 1), high=12, low=7, elements=[]), # Top
        ChanBar(index=2, date=datetime(2023, 1, 1, 9, 2), high=11, low=6, elements=[])
    ]
    
    fractals = find_fractals(bars)
    assert len(fractals) == 1
    assert fractals[0].type == FXType.TOP
    assert fractals[0].index == 1
    assert fractals[0].price == 12

def test_find_bottom_fractal():
    # Construct a Bottom Fractal pattern: Down, Bottom, Up
    bars = [
        ChanBar(index=0, date=datetime(2023, 1, 1, 9, 0), high=10, low=5, elements=[]),
        ChanBar(index=1, date=datetime(2023, 1, 1, 9, 1), high=8, low=3, elements=[]), # Bottom
        ChanBar(index=2, date=datetime(2023, 1, 1, 9, 2), high=9, low=4, elements=[])
    ]
    
    fractals = find_fractals(bars)
    assert len(fractals) == 1
    assert fractals[0].type == FXType.BOTTOM
    assert fractals[0].index == 1
    assert fractals[0].price == 3
